# One off task to run manually on the server to import the whole history of a SolarEdge installation
import psycopg
from sqlalchemy import cast, delete
from sqlalchemy.sql.sqltypes import DateTime
import argparse
import time
from app.tasks.util import print_success, print_error, print_warning
from sqlmodel import asc, select
from datetime import datetime
from solaredge import MonitoringClient
from dateutil.relativedelta import relativedelta
import httpx
from app.models import Measure, MeasureType

from sqlalchemy.orm.session import Session
from app.tasks.pull import (
    FILE,
    MAX_QUERIES_PER_DAY,
    load_pull_config,
    setup_api_client,
    solaredge_date_format_to_datetime,
    solaredge_datetime_format_to_datetime,
    get_db_sync_session,
    format_date,
)


def pull_all_history_month_by_month(installation):
    installation_id = installation["installation_id"]
    print_success(f"Starting import process for installation id {installation_id}")

    client = setup_api_client(installation)
    site_id = installation["solaredge_site_id"]

    # Get site details to extract the installation date, to know until which date we must load data
    details = client.get_site_details(site_id)
    details = details["details"]
    installation_date = solaredge_date_format_to_datetime(details["installationDate"])
    print_success(
        f"Installation {details['name']} was installed on {installation_date}"
    )
    print(f"installation_date => {format_date(installation_date)}")

    if installation_date is None:
        print_error("The installation_date was not found !")
        return

    # Quoting the API docs for the Site Energy route.
    # "Usage limitation: This API is limited [...] to one month when using timeUnit=QUARTER_OF_AN_HOUR or timeUnit=HOUR."
    # We have to import the data by coming back in time month after month, until we have all data since the installation_date !
    print("Printing generated month ranges")
    ranges = generate_month_date_ranges(installation_date, datetime.now())

    for ran in ranges:
        print(format_date(ran[0]), "->", format_date(ran[1]))
    print(f"There is a total of {len(ranges)} months to import :)")
    if len(ranges) > MAX_QUERIES_PER_DAY:
        print_error(
            f"Error: more than {MAX_QUERIES_PER_DAY} months of imports. This is not supported by this script as the API limits to {MAX_QUERIES_PER_DAY} requests per day."
        )
        exit(2)
    confirm = input("Can you confirm the start of the import ? (Y/N) ")
    if confirm.lower() != "y":
        print("Canceled")
        exit(1)
    print("\n--------\n")
    import_history_in_given_ranges(
        client, get_db_sync_session(), site_id, ranges, installation_id
    )


# Generate ranges of entire month starting now and going back in the past. The last range (the oldest month period) can start before the given start date.
# NOTE: we have to slightly change the end date to avoid having issues. The first issue is overlapping ranges. Here is an example
#
# Printing generated month ranges
# 2026-03-12 16:45:25 -> 2026-04-12 16:45:25
# 2026-02-12 16:45:25 -> 2026-03-12 16:45:25
# 2026-01-12 16:45:25 -> 2026-02-12 16:45:25
#
#
# Getting energy data for a month 2026-03-12 16:45:25.228125 -> 2026-04-12 16:45:25.228125
# Saved 2977 energy entries in DB !
# Getting energy data for a month 2026-03-12 16:45:25.228125 -> 2026-04-12 16:45:25.228125
# Saved 2977 power entries in DB !
# Getting energy data for a month 2026-02-12 16:45:25.228125 -> 2026-03-12 16:45:25.228125
# CRASH !!
# ...
# DETAIL:  Key (type, "time", installation_id)=(energy, 2026-03-12 16:45:00, 1) already exists.
# It seems they are rounding time, so we get the same timestamp in 2 contiguous months !
# -> Solution: we need to have the end date to not be on a quarter of an hour. Let's fix the end datetime with time 00:05:00 to avoid this issue.
#
# Actually, they are rounding time the quarter ! Solution -> we take one month minus 1 quarter of data for each range.
#
# The second issue is that reading the value for the quarter 16:45:00-17:00:00 when the current time is 16:47:00
# means we have partial energy values and incomplete power average ! We have to make sure to not import quarters that are not done !
# -> Solution: to be really sure, we go back 2 hours before (15minutes before is not enough because of the minute fix)
#
# Finally, this is the look of ranges when starting the script on 2026-04-12 17:56
# Printing generated month ranges
# 2026-03-12 15:20:00 -> 2026-04-12 15:05:00
# 2026-02-12 15:20:00 -> 2026-03-12 15:05:00
# 2026-01-12 15:20:00 -> 2026-02-12 15:05:00
# ...
def generate_month_date_ranges(
    start: datetime, end: datetime
) -> list[tuple[datetime, datetime]]:
    # The fixes as explained above
    end = end - relativedelta(hours=2)
    end = end.replace(second=0, minute=5)

    ranges: list[tuple[datetime, datetime]] = []
    while (
        end + relativedelta(minutes=15)
    ) > start:  # this check is equivalent at one_month_before > start
        # almost one month before to avoid including the same entry now and in the next range
        one_month_before = (end - relativedelta(months=1)) + relativedelta(minutes=15)
        ranges.append((one_month_before, end))
        end = end - relativedelta(months=1)  # exactly one month before
    return ranges


def import_history_in_given_ranges(
    client: MonitoringClient,
    session: Session,
    site_id: int,
    ranges: list[tuple[datetime, datetime]],
    installation_id: int,
):
    for ran in ranges:
        start = ran[0]
        end = ran[1]
        import_energy_into_db(start, end, client, session, site_id, installation_id)

        import_power_into_db(start, end, client, session, site_id, installation_id)
        # Sleep a short time to avoid spamming too much the API and be able to stop the script in case there are some issues
        time.sleep(1)


# Import energy data from SolarEdge API into our database in the measure table.
# We want to map values like this:
# Production -> solar_production, SelfConsumption -> solar_consumption, Purchased -> grid_consumption.
def import_energy_into_db(
    start, end, client: MonitoringClient, session: Session, site_id, installation_id
):
    print(f"Getting energy data for a month {start} -> {end}")
    energy_details = client.get_energy_details(
        site_id=site_id,
        start_time=start,
        end_time=end,
        time_unit="QUARTER_OF_AN_HOUR",
        meters=["Production", "SelfConsumption", "Purchased"],
    )
    details = energy_details["energyDetails"]
    assert details["unit"] == "Wh"
    production = None
    selfconsumption = None
    purchased = None
    for meter in details["meters"]:
        if meter["type"] == "Production":
            production = meter["values"]
        if meter["type"] == "SelfConsumption":
            selfconsumption = meter["values"]
        if meter["type"] == "Purchased":
            purchased = meter["values"]

    if production is None or selfconsumption is None or purchased is None:
        print_error("Error: of the metric was not returned by the API !")
        exit(3)

    entries_per_datetime = zip(production, selfconsumption, purchased)
    for entry in entries_per_datetime:
        # Safety checks to avoid mixing datetimes !
        assert entry[0]["date"] == entry[1]["date"]
        assert entry[0]["date"] == entry[2]["date"]

        new_measure = Measure(
            id=None,
            type=MeasureType.energy,
            time=solaredge_datetime_format_to_datetime(entry[0]["date"]),
            solar_production=get_entry_value(entry[0]),
            solar_consumption=get_entry_value(entry[1]),
            grid_consumption=get_entry_value(entry[2]),
            installation_id=installation_id,
        )
        session.add(new_measure)

    session.commit()  # save all all added measures inside a transaction
    print_success(f"Saved {len(production)} energy entries in DB !")


# Import power data from SolarEdge API into our database in the measure table.
# We want to map values like this:
# Production -> solar_production, SelfConsumption -> solar_consumption, Purchased -> grid_consumption.
def import_power_into_db(
    start, end, client: MonitoringClient, session: Session, site_id, installation_id
):
    print(f"Getting energy data for a month {start} -> {end}")
    power_details = client.get_power_details(
        site_id=site_id,
        start_time=start,
        end_time=end,
        meters=["Production", "SelfConsumption", "Purchased"],
    )
    details = power_details["powerDetails"]
    assert details["unit"] == "W"
    production = None
    selfconsumption = None
    purchased = None
    for meter in details["meters"]:
        if meter["type"] == "Production":
            production = meter["values"]
        if meter["type"] == "SelfConsumption":
            selfconsumption = meter["values"]
        if meter["type"] == "Purchased":
            purchased = meter["values"]

    if production is None or selfconsumption is None or purchased is None:
        print_error("Error: of the metric was not returned by the API !")
        exit(3)

    entries_per_datetime = zip(production, selfconsumption, purchased)
    for entry in entries_per_datetime:
        # Safety checks to avoid mixing datetimes !
        assert entry[0]["date"] == entry[1]["date"]
        assert entry[0]["date"] == entry[2]["date"]

        new_measure = Measure(
            id=None,
            type=MeasureType.power,
            time=solaredge_datetime_format_to_datetime(entry[0]["date"]),
            solar_production=get_entry_value(entry[0]),
            solar_consumption=get_entry_value(entry[1]),
            grid_consumption=get_entry_value(entry[2]),
            installation_id=installation_id,
        )
        session.add(new_measure)

    session.commit()  # save all all added measures inside a transaction
    print_success(f"Saved {len(production)} power entries in DB !")


def get_entry_value(entry) -> float:
    val = entry.get("value", 0)
    if val is None:
        return 0
    else:
        return val


def clean_import(installation_id):
    get_installation(installation_id)  # just to make sure it exists
    session = get_db_sync_session()
    # We want to see tons of results in batch to avoid filling the RAM. See docs for yield_per:
    # https://docs.sqlalchemy.org/en/21/orm/queryguide/api.html#fetching-large-result-sets-with-yield-per
    stmt = (
        select(Measure)
        .where(Measure.installation_id == installation_id)
        .order_by(asc(Measure.time))
        .execution_options(yield_per=100)
    )
    count = 0
    first = None
    for partition in session.scalars(stmt).partitions():
        for measure in partition:
            if first is None:
                first = measure
            if (
                measure.grid_consumption == 0
                and measure.solar_production == 0
                and measure.solar_consumption == 0
            ):
                count += 1
                continue
            if count == 0:
                print_success("No null measures found on the oldest values !")
                return

            first_useful_measure = measure  # just a way to rename it
            print_success(
                f"Between the start measure at {format_date(first.time)} and the first useful measure at {format_date(first_useful_measure.time)},\nit founds {count} entries with all 3 fields to zero."
            )
            confirm = input(
                f"Can you confirm you want to delete the first {count} entries for installation_id {installation_id} before {format_date(measure.time)} [y/n]: "
            )
            if confirm.lower() != "y":
                print("Canceled")
                exit(1)
            stmt = (
                delete(Measure)
                .where(Measure.time < cast(first_useful_measure.time, DateTime))
                .where(Measure.installation_id == installation_id)
            )
            session.execute(stmt)
            session.commit()
            print_success("Deletion successful !")
            return


def check_import(installation_id):
    get_installation(installation_id)  # just to make sure it exists
    session = get_db_sync_session()
    # We want to see tons of results in batch to avoid filling the RAM. See docs for yield_per: https://docs.sqlalchemy.org/en/21/orm/queryguide/api.html#fetching-large-result-sets-with-yield-per
    stmt = (
        select(Measure)
        .where(Measure.installation_id == installation_id)
        .order_by(asc(Measure.time))
        .order_by(
            asc(Measure.type)
        )  # to make sure a consistent order of "power then energy" (this is the order of the postgres enum)
        .execution_options(yield_per=100)
    )
    print(
        f"Starting global verification process for import on installation_id {installation_id}"
    )
    count = 0
    last_measure = None
    # This is a hack to avoid having 3 "max_*" variables, we reuse the Measure class
    maximums_energy_measures = Measure(
        id=None,
        time=datetime.now(),
        type=MeasureType.energy,
        solar_consumption=0,
        solar_production=0,
        grid_consumption=0,
    )
    maximums_power_measures = Measure(
        id=None,
        time=datetime.now(),
        type=MeasureType.power,
        solar_consumption=0,
        solar_production=0,
        grid_consumption=0,
    )

    missing_quarters_occurences = 0
    min = 0

    in_downtime = False
    in_downtime_starttime = None
    for partition in session.scalars(stmt).partitions():
        for measure in partition:
            check_watt_or_watthour_coherence(
                measure.solar_production, "solar_production"
            )
            check_watt_or_watthour_coherence(
                measure.solar_consumption, "solar_consumption"
            )
            check_watt_or_watthour_coherence(
                measure.grid_consumption, "grid_consumption"
            )

            if measure.type == MeasureType.energy:
                if maximums_energy_measures.grid_consumption < measure.grid_consumption:
                    maximums_energy_measures.grid_consumption = measure.grid_consumption
                if (
                    maximums_energy_measures.solar_consumption
                    < measure.solar_consumption
                ):
                    maximums_energy_measures.solar_consumption = (
                        measure.solar_consumption
                    )
                if maximums_energy_measures.solar_production < measure.solar_production:
                    maximums_energy_measures.solar_production = measure.solar_production

            if measure.type == MeasureType.power:
                if maximums_power_measures.grid_consumption < measure.grid_consumption:
                    maximums_power_measures.grid_consumption = measure.grid_consumption
                if (
                    maximums_power_measures.solar_consumption
                    < measure.solar_consumption
                ):
                    maximums_power_measures.solar_consumption = (
                        measure.solar_consumption
                    )
                if maximums_power_measures.solar_production < measure.solar_production:
                    maximums_power_measures.solar_production = measure.solar_production

            count += 1
            if last_measure is None:
                last_measure = measure
                continue

            # Note: because of the order by, we have power then energy entries in chronological order
            # If this is the power, we have to make sure we are only at the next quarter
            if measure.type == MeasureType.power:
                if last_measure.type == measure.type:
                    print_warning(
                        f"\nTwo consecutive measures have the same type, meaning the energy part of {format_date(last_measure.time)} is missing between {format_measure(last_measure)} and {format_measure(measure)}"
                    )
                if last_measure.time == measure.time:
                    print_warning(
                        f"\nTwo measures have the same time {format_measure(last_measure)} and {format_measure(measure)}"
                    )

                if last_measure.time + relativedelta(minutes=15) != measure.time:
                    print_warning(
                        f"\nThere are {int((measure.time - last_measure.time).total_seconds() / (60 * 60 * 24))} days of missing values, which is {int((measure.time - last_measure.time).total_seconds() / 3600 * 4)} missing quarters between {format_measure(last_measure)} and {format_measure(measure)}"
                    )
                    missing_quarters_occurences += 1

            if measure.type == MeasureType.energy:
                if last_measure.type == measure.type:
                    print_warning(
                        f"\nTwo consecutive measures have the same type, meaning the power part of {format_date(last_measure.time)} is missing between {format_measure(last_measure)} and {format_measure(measure)}"
                    )

                if last_measure.time != measure.time:
                    print_warning(
                        f"\nEnergy entry should have the same time as previous power. Found {format_measure(last_measure)} and {format_measure(measure)}"
                    )

            # Detect installation downtimes
            if (
                measure.grid_consumption == 0
                and measure.solar_production == 0
                and measure.solar_consumption == 0
            ):
                if not in_downtime:
                    in_downtime_starttime = measure.time
                    in_downtime = True
            else:
                if in_downtime:
                    assert in_downtime_starttime is not None
                    print_warning(
                        f"\nDetected installation downtime of {(measure.time - in_downtime_starttime).total_seconds() / 3600} hours from {format_date(in_downtime_starttime)} to {measure.time}"
                    )
                    in_downtime = False

            last_measure = measure

    print_success(f"\n\nFinished analysing {count} entries (quarters of an hour) !")
    print(
        f"\nTotal number of missing quarters occurences: {missing_quarters_occurences}"
    )

    print(f"\nPrinting max values for {int(count / 2)} energy values in Wh")
    print(f"MAX solar_production: {maximums_energy_measures.solar_production}")
    print(f"MAX solar_consumption: {maximums_energy_measures.solar_consumption}")
    print(f"MAX grid_consumption: {maximums_energy_measures.grid_consumption}")

    print(f"\nPrinting max values for {int(count / 2)} power values in W")
    print(f"MAX solar_production: {maximums_power_measures.solar_production}")
    print(f"MAX solar_consumption: {maximums_power_measures.solar_consumption}")
    print(f"MAX grid_consumption: {maximums_power_measures.grid_consumption}")


def format_measure(measure: Measure):
    return f"'{measure.type.value}: {format_date(measure.time)}'"


def check_watt_or_watthour_coherence(value: float, desc: str):
    if value < 0:
        print_warning(f"\nValue {value} of {desc} is not valid !")


def get_installation(installation_id):
    installations = load_pull_config()
    for ins in installations:
        if ins["installation_id"] == installation_id:
            return ins
    print_error(
        f"Sorry but no installation is configured in {FILE} with ID {installation_id}"
    )


def main():
    try:
        parser = argparse.ArgumentParser("pull-history")
        subcommands = parser.add_subparsers(
            title="command", dest="command", required=True
        )
        pull_parser = subcommands.add_parser(
            "pull", help="Pull all the history from SolarEdge API"
        )
        pull_parser.add_argument(
            "--installation-id",
            help=f"The installation ID. It must be one of the installation_id field in {FILE}.",
            type=int,
        )
        clean_parser = subcommands.add_parser(
            "clean",
            help="Clean the imported data by deleting the oldest null entries",
        )
        clean_parser.add_argument(
            "--installation-id",
            help=f"The installation ID. It must be one of the installation_id field in {FILE}.",
            type=int,
            required=True,
        )
        check_parser = subcommands.add_parser(
            "check",
            help="Perform various check to validate the consistency of the data",
        )
        check_parser.add_argument(
            "--installation-id",
            help=f"The installation ID. It must be one of the installation_id field in {FILE}.",
            type=int,
            required=True,
        )
        # TODO: maybe find a way to remove this redundancy of --installation_id definition...
        args = parser.parse_args()

        # Arguments routing
        if args.command == "pull":
            pull_all_history_month_by_month(get_installation(args.installation_id))
            return
        if args.command == "clean":
            clean_import(args.installation_id)
            return
        if args.command == "check":
            check_import(args.installation_id)
            return

    except httpx.HTTPStatusError as e:
        print_error(e)  # just print http error nicely instead of huge stack trace...
    except psycopg.errors.UniqueViolation as e:
        print_error(e)


if __name__ == "__main__":
    main()
