# One off task to run manually on the server to import the whole history of a SolarEdge installation
import psycopg
import argparse
import time
from datetime import datetime
from termcolor import colored
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


def colored_print(text, color: str):
    print(colored(text, color))


def print_error(text):
    colored_print(text, "red")


def print_success(text):
    colored_print(text, "green")


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


def main(installation_id):
    installations = load_pull_config()
    for ins in installations:
        if ins["installation_id"] == installation_id:
            pull_all_history_month_by_month(ins)
            return
    print_error(
        f"Sorry but no installation is configured in {FILE} with ID {installation_id}"
    )


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser("pull-history")
        parser.add_argument(
            "--installation-id",
            help=f"The installation ID configured in {FILE} to use when pulling history.",
            type=int,
        )
        args = parser.parse_args()
        main(args.installation_id)
    except httpx.HTTPStatusError as e:
        print_error(e)  # just print http error nicely instead of huge stack trace...
    except psycopg.errors.UniqueViolation as e:
        print_error(e)
