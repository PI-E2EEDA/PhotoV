from time import sleep
import questionary
import httpx
import json
from datetime import datetime
from pathlib import Path

VIRTUAL_CONFIG_PATH = Path(__file__).parent / "virtual.json"
API_ROUTE_SEND_MEASURE = "smartplugs"
# IMPORTANT: this is not the same subdomain as the official monitoring API !
SOLAREDGE_INTERNAL_API_BASE_URL = "https://monitoring.solaredge.com"
PHOTOV_API_BASE_URL = "https://api.photov.srd.rs"
SAVE_INTERVAL_S = 10  # like the physical smartplugs


def get_virtual_config():
    with open(VIRTUAL_CONFIG_PATH, "r") as f:
        return json.load(f)


# This request by built by looking at the Firefox Network panel (F12) on the monitoring UI.
# When filtering with "power-flow", we can see a request every 5-6 seconds. With a right-click, copy, copy as CURL, we can extract all the headers.
def get_powerflow_measure_from_solaredge(log_result, inst_config):
    site_id = inst_config["solaredge_site_id"]
    cookies = inst_config["cookies"]

    # Note: The URL is different from the official monitoring API
    url = f"{SOLAREDGE_INTERNAL_API_BASE_URL}/services/dashboard/power-flow/v2/sites/{site_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://monitoring.solaredge.com/one",
        "Origin": "https://monitoring.solaredge.com",
        "X-Requested-With": "XMLHttpRequest",
    }

    cookies = dict(item.strip().split("=", 1) for item in cookies.split(";"))
    params = {
        "components": "grid,consumption"
    }  # we don't need grid but it's better to simulate the web app...

    with httpx.Client() as client:
        response = client.get(url, headers=headers, params=params, cookies=cookies)
        if not response.is_error:
            data = response.json()
            # WARNING: the value is in in kW, we need to convert it !
            current_power_kw = float(data["consumption"]["currentPower"])
            current_power_w = 1000 * current_power_kw
            if log_result:
                now = datetime.now()
                formatted = now.strftime("%Y-%m-%d %H:%M:%S")
                print(f"{formatted}: Power is {current_power_w}W, ", end="", flush=True)
            return current_power_w
        else:
            log_result(f"Request failed with code {response.status_code}")
    return None


def save_smartplug_measure_on_photov(inst_config, smartplug_id: int, value: float):
    installation_id = inst_config["installation_id"]
    api_token = inst_config["photov_api_token"]

    with httpx.Client() as client:
        try:
            response = client.post(
                f"{PHOTOV_API_BASE_URL}/{API_ROUTE_SEND_MEASURE}/{installation_id}/",
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
                print(f"sent adapted measure {value}W for smartplug {smartplug_id}")
            else:
                print(
                    f"Smartplug {smartplug_id}: API error {response.status_code} : {response.text}"
                )

        except httpx.ConnectError:
            print(f"Could not reach API at {PHOTOV_API_BASE_URL}...")


def interactive_start():
    print("Welcome to the interactive start of a virtual smartplug !")
    virtual_config = get_virtual_config()
    names = [installation["name"] for installation in virtual_config]
    inst_name = questionary.select(
        "Choose one of the installations configured in virtual.json",
        choices=names,
    ).ask()
    inst_config = virtual_config[names.index(inst_name)]

    smartplug_names = [smartplug["name"] for smartplug in inst_config["smartplugs"]]
    smartplug_name = questionary.select(
        "Choose the virtual smartplug to start now",
        choices=smartplug_names,
    ).ask()

    chosen_smartplug = inst_config["smartplugs"][smartplug_names.index(smartplug_name)]
    return (inst_config, chosen_smartplug["id"])


def main():
    inst_config, smartplug_id = interactive_start()
    print(
        "Measuring current power flow to determine the baseline power to substract to measures"
    )
    print(
        "If the physical device has already started, you may need to manually take the power flow value before its activation."
    )
    baseline_value = get_powerflow_measure_from_solaredge(False, inst_config)
    if baseline_value is None:
        print("Error: could not get current powerflow !")
        return
    confirmed = questionary.confirm(
        f"Do you want to take this baseline of {baseline_value}W ?",
        default=False,
    ).ask()

    if not confirmed:
        manual_baseline = questionary.text(
            "Can you enter your own baseline in W please ? "
        ).ask()
        baseline_value = float(manual_baseline)

    while True:
        value = get_powerflow_measure_from_solaredge(True, inst_config)
        if value is not None:
            value = value - baseline_value
            # We need to make sure we don't go into the negative if the real baseline is going lower what we chose
            if value < 0:
                value = 0
            save_smartplug_measure_on_photov(inst_config, smartplug_id, value)
        sleep(SAVE_INTERVAL_S)


main()
