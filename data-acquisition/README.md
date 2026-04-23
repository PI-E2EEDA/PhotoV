# Data acquisition

This file explains all the approach to configure the data acquisition system to  acquire power consumption from multiple [ESPHome Wifi plugs in Swiss format](https://www.swiss-domotique.ch/en/wall-plugs/esphome-wifi-plug-in-swiss-format#ets-rv-product-comments-list-header) such as a raspberry, for example.

## Install the requirements on the data acquistion computer

Install `nmap`:

```bash
sudo apt update && sudo apt install nmap
```

Install `uv` (the python env manager) :

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Configure the connection to the smartplugs

1. Plug the smart plug in
2. If this is the first time or if the network that was configured is no longer available. Connect your phone et computer to the Wi-FI hotspot "Swiss-Domotique_XXXX", wait several seconds and select a wifi and enter the password
3. The smart plug is now connected to the network. You need to retrieve his IP adress by using this command : `nmap -p 6053 XXX.XXX.XXX.XXX/24`. (The port 6053 is the default port for this devices). Check all the adresses listed and the right adress is where the state is `OPEN`. For example, we obtained this :

    ```text
    ➜  data-acquisition git:(main) ✗ nmap -p 6053 192.168.1.0/24
    Starting Nmap 7.94SVN ( https://nmap.org ) at 2026-04-12 15:53 CEST
    Nmap scan report for 192.168.1.1
    Host is up (0.0051s latency).

    PORT     STATE  SERVICE
    6053/tcp closed x11

    Nmap scan report for 192.168.1.29
    Host is up (0.075s latency).

    PORT     STATE  SERVICE
    6053/tcp closed x11

    Nmap scan report for 192.168.1.196
    Host is up (0.0052s latency).

    PORT     STATE  SERVICE
    6053/tcp closed x11

    Nmap scan report for 192.168.1.204
    Host is up (0.019s latency).

    PORT     STATE  SERVICE
    6053/tcp closed x11

    Nmap scan report for 192.168.1.205
    Host is up (0.050s latency).

    PORT     STATE SERVICE
    6053/tcp open  x11

    Nmap done: 256 IP addresses (5 hosts up) scanned in 3.85 seconds
    ```

4. You can now access the integrated webserver a the IP adress found. For example : [http://192.168.1.205](http://192.168.1.205)
5. To retrieve automatically the measures, you first need to print all the informations about the device. Run the script : [print_info.py](./setup/print_info.py). You will have something like this :

    ```text
    data-acquisition git:(main) ✗ uv run main.py
    APIVersion(major=1, minor=12)
    DeviceInfo(uses_password=False, name='swiss-domotique-plug-f26f35', friendly_name='Smart Plug V2 f26f35', mac_address='78:42:1C:F2:6F:35', compilation_time='Sep  3 2025, 09:03:12', model='esp8285', manufacturer='Espressif', has_deep_sleep=False, esphome_version='2025.8.2', project_name='Swiss_Domotique.Smart Plug V2', project_version='v2.0.8', webserver_port=80, legacy_voice_assistant_version=0, voice_assistant_feature_flags=0, legacy_bluetooth_proxy_version=0, bluetooth_proxy_feature_flags=0, zwave_proxy_feature_flags=0, zwave_home_id=0, suggested_area='', bluetooth_mac_address='', api_encryption_supported=False, devices=[], areas=[AreaInfo(area_id=3101035732, name='')], area=AreaInfo(area_id=0, name=''), serial_proxies=[])
    ([BinarySensorInfo(object_id='status', key=939730931, name='Status', disabled_by_default=False, icon='mdi:check-network-outline', entity_category=<EntityCategory.DIAGNOSTIC: 2>, device_id=0, device_class='connectivity', is_status_binary_sensor=True), 

    ...

    SensorInfo(object_id='power', key=2391494160, name='Power', disabled_by_default=False, icon='mdi:power', entity_category=<EntityCategory.NONE: 0>, device_id=0, device_class='power', unit_of_measurement='W', accuracy_decimals=1, force_update=False, state_class=<SensorStateClass.MEASUREMENT: 1>, legacy_last_reset_type=<LastResetType.NONE: 0>), 
    SensorInfo(object_id='energy', key=1345584937, name='Energy', disabled_by_default=False, icon='mdi:lightning-bolt', entity_category=<EntityCategory.NONE: 0>, device_id=0, device_class='energy', unit_of_measurement='kWh', accuracy_decimals=3, force_update=False, state_class=<SensorStateClass.TOTAL_INCREASING: 2>, legacy_last_reset_type=<LastResetType.NONE: 0>), 

    ...

    SelectInfo(object_id='power_on_state', key=46544162, name='Power On State', disabled_by_default=False, icon='mdi:electric-switch', entity_category=<EntityCategory.NONE: 0>, device_id=0, options=['Always Off', 'Always On', 'Restore Power Off State'])], [])
    ```

    From thoses informations, we can extract the sensor infomation about the power : 

    ```text
    SensorInfo(object_id='power', key=2391494160, name='Power', disabled_by_default=False, icon='mdi:power', entity_category=<EntityCategory.NONE: 0>, device_id=0, device_class='power', unit_of_measurement='W', accuracy_decimals=1, force_update=False, state_class=<SensorStateClass.MEASUREMENT: 1>, legacy_last_reset_type=<LastResetType.NONE: 0>), 
    ```

6. With those information, you can now test the connection with the [test script](./setup/get_power_test.py). Once the connection test you can :
    - use the service which send the measurement to the API in the "service" folder
    - create your own script to retrieve the power with the [Python Client for ESPHome native API](https://github.com/esphome/aioesphomeapi). There is no documentation about the API, but you can check the code here to see the available methods of this API : [link](https://github.com/esphome/aioesphomeapi/blob/main/aioesphomeapi/client.py#L252)

## Run the acquisition service

Install the correct python version and the packages for the data acquisition service :

```bash
uv sync
```

Run the service from the `data-acquisition` folder :
```bash
uv run service/acquire.py
```