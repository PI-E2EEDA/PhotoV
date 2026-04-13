import aioesphomeapi
import asyncio
import signal

POWER_KEY = 2391494160

async def main():
    """Connect to an ESPHome device and get the power measurement"""

    # Establish connection
    api = aioesphomeapi.APIClient(
        "192.168.1.205",
        6053,
        "",
    )
    await api.connect(login=True)

    def on_state(state):
        if state.key == POWER_KEY :
            print(type(state))
            print(state.state)
            print(state)

    api.subscribe_states(on_state)

    # Clean end when the process is stopped
    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop.set)
    loop.add_signal_handler(signal.SIGTERM, stop.set)

    await stop.wait()
    await api.disconnect()

asyncio.run(main())