# Virtual smartplug

This little `start-virtual-smartplug.py` is a way to simulate a smartplug for devices that are plugged in the wall. As we cannot use a physical smartplug in between, we need to use the data from SolarEdge when only a specific device is consuming.

## Configure credentials
```
cp virtual.json.example virtual.json
```
You have to configure `virtual.json`.

## Run the script
```
uv run -m virtual.start-virtual-smartplug
```

It starts with an interactive setup to configure
```sh
Welcome to the interactive start of a virtual smartplug !
? Choose one of the installations configured in virtual.json
 »  Home 1
? Choose the virtual smartplug to start now (Use arrow keys)
 » lave-linge-40
   four
   lave-linge-60
Measuring current power flow to determine the baseline power to substract to measures
If the physical device has already started, you may need to manually take the power flow value before its activation.
? Do you want to take this baseline of 130.0W ? Yes
2026-05-02 15:14:06: Power is 110.0W, sent adapted measure 0W for smartplug 5
2026-05-02 15:14:17: Power is 110.0W, sent adapted measure 0W for smartplug 5
...
2026-05-02 15:15:27: Power is 2110.0W, sent adapted measure 2000W for smartplug 5
...
```
