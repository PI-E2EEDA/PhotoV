# One off task to run manually on the server to import the whole history of a SolarEdge installation
import argparse
from datetime import datetime
from termcolor import colored
from solaredge import MonitoringClient
from dateutil.relativedelta import relativedelta
import httpx
from models import Measure, MeasureType

from sqlalchemy.orm.session import Session
from pull import (
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


def pull_all_history_month_by_month(installation):
    installation_id = installation["installation_id"]
    print(f"Starting history import process for installation id {installation_id}")

    client = setup_api_client(installation)
    site_id = installation["solaredge_site_id"]

    # Get site details to extract the installation date, to know until which date we must load data
    details = client.get_site_details(site_id)

    installation_date = solaredge_date_format_to_datetime(details["installationDate"])
    print(f"installation_date => {format_date(installation_date)}")

    if installation_date is None:
        print_error("The installation_date was not found !")
        return

    print(
        "Quoting the API docs for the Site Energy route. \n'Usage limitation: This API is limited [...] to one month when using timeUnit=QUARTER_OF_AN_HOUR or timeUnit=HOUR.'\nWe have to import the data by coming back in time month after month, until we have all data since the installation_date !"
    )
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
def generate_month_date_ranges(
    start: datetime, end: datetime
) -> list[tuple[datetime, datetime]]:
    past_date = end
    ranges: list[tuple[datetime, datetime]] = []
    while past_date > start:
        one_month_before = past_date - relativedelta(months=1)
        ranges.append((one_month_before, past_date))
        past_date = past_date - relativedelta(months=1)
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
    print(f"Saved {len(production)} power entries in DB !")


def get_entry_value(entry) -> float:
    val = entry.get("value", 0)
    if val is None:
        return 0
    else:
        return val
