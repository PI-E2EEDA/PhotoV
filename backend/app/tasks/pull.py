# Task to regularly pull latest data from SolarEdge API for the credentials stored in pull.config.json
import json
from datetime import timedelta
from sqlmodel import asc, desc, select
import asyncio
from datetime import datetime
from solaredge import MonitoringClient
from sqlalchemy.orm.session import Session
from sqlalchemy.orm import create_session
from sqlmodel import create_engine
from app.db import get_database_url, get_async_session
from app.models import Measure, MeasureType
import os

# CONSTANTS
FILE = "pull.config.json"
MAX_QUERIES_PER_DAY = 300

# TASK CODE


def log(message: str):
    with open("/app/pull.logs.txt", mode="a") as log:
        log.write(message)


# We want to pull the latest measures every quarter of an hour, right after a quarter was done.
# This is important to have query quarters when they are not finished, this would give us partial values.
# It will run on every xx:01, xx:16, xx:31, and xx:46 times (hours:minutes)
# We also want to ignore pulling data during the night because of inactivity.
# We have to make sure we are below MAX_QUERIES_PER_DAY per day.
async def start_background_pulling_at_regular_time():
    INTERVAL_M = 15  # 15 minutes of interval. If we need to change this value, we have to make sure to change the rest to follow the conditions in above comments !
    STOP_START_HOUR_INDEX = 0  # stop pulling measures at midnight. Make sure conditions also work below if changed.
    STOP_END_HOUR_INDEX = 6  # restart pulling measures at 6AM. Make sure conditions also work below if changed.
    IDEAL_MINUTES = [1, 16, 31, 46, 61]
    log("Starting background process for regular pull")

    session = get_async_session()
    while True:
        now = datetime.now()
        if now.hour >= STOP_START_HOUR_INDEX and now.hour < STOP_END_HOUR_INDEX:
            sleep_time_hour = STOP_END_HOUR_INDEX - now.hour
            log(
                f"Stopping the background pulling for the night between hour {STOP_START_HOUR_INDEX} and {STOP_END_HOUR_INDEX}. Going to sleep for {sleep_time_hour} hours."
            )
            await asyncio.sleep(sleep_time_hour * 3600)

        # If we are not an ideal time, we need to wait a bit more
        if now.minute not in IDEAL_MINUTES:
            for ideal_minute in IDEAL_MINUTES:
                # The first ideal minute that is above current minute, is the next one
                if now.minute < ideal_minute:
                    sleep_time_until_next_ideal_time = ideal_minute - now.minute
                    log(
                        f"Going to sleep for {sleep_time_until_next_ideal_time} minutes until the next ideal time."
                    )
                    await asyncio.sleep(60 * sleep_time_until_next_ideal_time)
                    log(
                        f"Sleep for {sleep_time_until_next_ideal_time} minutes is done."
                    )
                    break

        now = datetime.now()
        if now.minute not in IDEAL_MINUTES:
            log(
                "Timing issue: this is still not an ideal time to pull latest measures..."
            )
            continue
        log(f"Starting pulling latest measures for all installations at {now}")
        # reload installations in case it has changed in the meantime
        installations = load_pull_config()
        for ins in installations:
            client = setup_api_client(ins)
            await pull_latest_missing_measures(client, session, ins)

        # Make sure that we sleep at least for INTERVAL_M
        await asyncio.sleep(INTERVAL_M * 60)


# By looking at the database to see how much data is missing, it will get the latest measure time
# and pull all missing measures from SolarEdge. This is meant to be run frequently (like every hour)
# but also need to support loading more data in case of API downtime.
async def pull_latest_missing_measures(client, session, installation):
    log(
        f"Pulling latest missing measures for installation id: {installation['installation_id']}"
    )
    count = 0
    # Take the last power and energy measures to retrieve values only from this time and avoid collision with existing data in DB.
    stmt = (
        select(Measure)
        .where(Measure.installation_id == installation["installation_id"])
        .order_by(desc(Measure.time))
        .order_by(
            asc(Measure.type)
        )  # to make sure a consistent order of "power then energy" (this is the order of the postgres enum)
        .limit(2)  # energy + power
    )
    results = await session.execute(stmt)  # ignore this warning
    items = results.scalars().all()
    if len(items) < 2:
        log(
            "Error: latest measures not found. You need to pull the whole history with the pull_history script first !"
        )
        return
    latest_power: Measure = items[0]
    latest_energy: Measure = items[1]
    now = datetime.now()
    if (latest_power.time - datetime.now()).days >= 30:
        log(
            "Error: data is missing since earlier than a month and the pull script doesn't support it. Fix the script."
        )
        return

    # As the SolarEdge API is rounding values to the quarter of an hour, we can just -15minutes to make sure we only retrieve complete quarters and ignore the current one.
    # If we are 15:17, it will be 15:02, which is rounded to 15:00. If it is 13:45, it will be 13:30 which is what we want.
    end = now - timedelta(minutes=15)
    import_power_into_db(
        start=latest_power.time + timedelta(minutes=15),  # skip the existing quarter
        end=end,
        client=client,
        session=session,
        site_id=installation["solaredge_site_id"],
        installation_id=installation["installation_id"],
    )
    import_energy_into_db(
        start=latest_energy.time + timedelta(minutes=15),  # skip the existing quarter
        end=end,
        client=client,
        session=session,
        site_id=installation["solaredge_site_id"],
        installation_id=installation["installation_id"],
    )
    log(f"Pulling {count} measures for installation {installation['installation_id']}")


# Import energy data from SolarEdge API into our database in the measure table.
# We want to map values like this:
# Production -> solar_production, SelfConsumption -> solar_consumption, Purchased -> grid_consumption.
def import_energy_into_db(
    start, end, client: MonitoringClient, session: Session, site_id, installation_id
):
    log(f"Getting energy data for {start} -> {end}")
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
        log("Error: of the metric was not returned by the API !")
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
    log(f"Saved {len(production)} energy entries in DB !")


# Import power data from SolarEdge API into our database in the measure table.
# We want to map values like this:
# Production -> solar_production, SelfConsumption -> solar_consumption, Purchased -> grid_consumption.
def import_power_into_db(
    start, end, client: MonitoringClient, session: Session, site_id, installation_id
):
    log(f"Getting energy data for a month {start} -> {end}")
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
        log("Error: of the metric was not returned by the API !")
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
    log(f"Saved {len(production)} power entries in DB !")


# HELPERS FUNCTIONS


def get_entry_value(entry) -> float:
    val = entry.get("value", 0)
    if val is None:
        return 0
    else:
        return val


# Returns a list of installation from FILE
def load_pull_config():
    folder = os.environ.get("CREDS_FOLDER", "../infra/creds")
    log("Using credentials from " + folder)
    with open(f"{folder}/{FILE}", "r") as f:
        return json.load(f)


def save_json_to_file(json_content: object, file_path: str):
    with open(file_path, "w") as file:
        json.dump(json_content, file)


def solaredge_datetime_format_to_datetime(text: str):
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def solaredge_date_format_to_datetime(text: str):
    return datetime.strptime(text, "%Y-%m-%d")


def setup_api_client(installation):
    return MonitoringClient(api_key=installation["solaredge_api_key"])


def format_date(given_date: datetime):
    return given_date.strftime("%Y-%m-%d %H:%M:%S")


def get_db_sync_session() -> Session:
    engine = create_engine(get_database_url(False))
    return create_session(engine)
