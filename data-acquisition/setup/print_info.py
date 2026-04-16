import aioesphomeapi
import asyncio

SMARTPLUG_IP = "172.20.10.4"

async def main():
    """Connect to an ESPHome device and get details."""

    # Establish connection
    api = aioesphomeapi.APIClient(
        SMARTPLUG_IP,
        6053,
        "",
    )
    await api.connect(login=True)

    # Get API version of the device's firmware
    print(api.api_version)

    # Show device details
    device_info = await api.device_info()
    print(device_info)

    # List all entities of the device
    entities = await api.list_entities_services()
    print(entities)

asyncio.run(main())