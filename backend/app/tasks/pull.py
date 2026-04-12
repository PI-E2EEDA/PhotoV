# Task to regularly pull latest data from SolarEdge API for the credentials stored in pull.config.json
import json
from datetime import datetime
from solaredge import MonitoringClient
from sqlalchemy.orm.session import Session
from sqlalchemy.orm import create_session
from sqlmodel import create_engine
from db import get_database_url
import os

# CONSTANTS
FILE = "pull.config.json"
MAX_QUERIES_PER_DAY = 300

# TASK CODE


def pull_latest_hour(installation):
    print(
        f"Starting pull_latest_hour for installation id: {installation.installation_id}"
    )
    print(f"Done pull_latest_hour for installation id: {installation.installation_id}")


# HELPERS FUNCTIONS


# Returns a list of installation from FILE
def load_pull_config():
    folder = os.environ.get("CREDS_FOLDER", "../infra/creds")
    print("Using credentials from " + folder)
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
    given_date.strftime("%Y-%m-%d %H:%M:%S")


def get_db_sync_session() -> Session:
    engine = create_engine(get_database_url(False))
    return create_session(engine)
