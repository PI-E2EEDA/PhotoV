import aioesphomeapi
import asyncio
import signal
import yaml
import httpx  # instead of requests pacakge because it allows async
from datetime import datetime
from pathlib import Path

API_ROUTE_SEND_MEASURE = "smartplugs"
CONFIG_PATH = Path(__file__).parent / "config.yaml"

latest_power = {}  # shared dict : {smartplug_id: last value}

def make_callback(smartplug_id, power_key):
    def on_state(state):
        if state.key == power_key:
            latest_power[smartplug_id] = state.state
    return on_state # return the function specified for a smartplug

async def connect_smartplug(smartplug):
    api = aioesphomeapi.APIClient(smartplug["ip"], smartplug["port"], "")
    try:
        await asyncio.wait_for(api.connect(login=True), timeout=10)
        api.subscribe_states(make_callback(smartplug["id"], smartplug["power_key"]))
        return api
    except asyncio.TimeoutError:
        print(f"Timeout: {smartplug['id']}")
        return None
    except aioesphomeapi.core.SocketAPIError:
        raise ConnectionError(f"Could not connect to {smartplug['ip']}, stopping program")

async def main():
    """Connect to an ESPHome device and get the power measurement"""
    config = None
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    client = httpx.AsyncClient()
    apis = []

    try:
        # Establish connection to the smartplugs and subscribe smartplugs
        results = await asyncio.gather(*[connect_smartplug(p) for p in config["smartplugs"]])
        apis = [api for api in results if api is not None]

        # Define stop and signal handlers
        stop = asyncio.Event()
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, stop.set)
        loop.add_signal_handler(signal.SIGTERM, stop.set)

        # Extract params from config
        base_url = config["api_base_url"]
        installation_id = config["installation_id"]
        api_token = config["api_token"]

        print(f"Started acquisition for installation {installation_id} with {len(apis)} smartplug(s)")

    
        # Send measurements to API
        zero_since = {}  # {smartplug_id: datetime when power first hit 0}
        zero_threshold = config.get("zero_power_threshold_seconds", 300)

        async def send_loop():
            while not stop.is_set():
                await asyncio.sleep(config["acquisition_interval_seconds"])
                for smartplug_id, power_val in latest_power.items():
                    print(f"Smartplug {smartplug_id}: {round(power_val, 2)} W")

                    # Skip sending if power has been 0 for too long
                    if power_val == 0:
                        if smartplug_id not in zero_since:
                            zero_since[smartplug_id] = datetime.now()
                        elapsed = (datetime.now() - zero_since[smartplug_id]).total_seconds()
                        if elapsed >= zero_threshold:
                            print(f"Smartplug {smartplug_id}: 0W for {int(elapsed)}s, skipping")
                            continue
                    else:
                        zero_since.pop(smartplug_id, None)

                    try:
                        response = await client.post(
                            f"{base_url}/{API_ROUTE_SEND_MEASURE}/{installation_id}/",
                            json={
                                "smartplug_id": smartplug_id,
                                "time": datetime.now().isoformat(),
                                "value": round(power_val, 2),
                            },
                            headers={
                                "Authorization": f"Bearer {api_token}",
                            },
                        )
                        if response.status_code == 200:
                            print(f"Smartplug {smartplug_id}: power sent")
                        else:
                            print(f"Smartplug {smartplug_id}: API error {response.status_code} : {response.text}")

                    except httpx.ConnectError:
                        print(f"Could not reach API at {base_url}, will retry next cycle")

        await asyncio.gather(stop.wait(), send_loop()) # In parallel, send_loop and wait stop. Finish when the both are finished

    except ConnectionError as e:
        print(e)

    finally:
        for api in apis:
            await api.disconnect()
        await client.aclose()

asyncio.run(main())
