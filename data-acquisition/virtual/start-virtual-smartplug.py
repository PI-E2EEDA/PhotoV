import httpx
import yaml
from datetime import datetime
from pathlib import Path
from solaredge import MonitoringClient

CONFIG_PATH = Path(__file__).parent / "service" / "config.yaml"
API_ROUTE_SEND_MEASURE = "smartplugs"


def get_yaml_config():
    config = None
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
        return config


def setup_api_client(installation):
    # TODO: setup httpx client with cookies in cookies.txt
    # and all headers to simulate a web browser
    client = httpx.Client()
    client.cookies.set(..)
    return MonitoringClient(...)


def get_powerflow_measure_from_solaredge():
    # TODO: implement the request
    print("yep")


def save_smartplug_measure_on_photov(
    config, client: httpx.Client, smartplug_id: int, value: float
):
    base_url = config["api_base_url"]
    installation_id = config["installation_id"]
    api_token = config["api_token"]
    try:
        response = client.post(
            f"{base_url}/{API_ROUTE_SEND_MEASURE}/{installation_id}/",
            json={
                "smartplug_id": smartplug_id,
                "time": datetime.now().isoformat(),
                "value": value,
            },
            headers={
                "Authorization": f"Bearer {api_token}",
            },
        )
        if response.status_code == 200:
            print(f"Smartplug {smartplug_id}: power sent")
        else:
            print(
                f"Smartplug {smartplug_id}: API error {response.status_code} : {response.text}"
            )

    except httpx.ConnectError:
        print(f"Could not reach API at {base_url}, will retry next cycle")


def main():
    config = get_yaml_config()
    client = setup_api_client()
    get_powerflow_measure_from_solaredge()
    save_smartplug_measure_on_photov(config, client)


main()
