# Examples on using the filter output for adjusting thermostat

Adjusting thermostat/HVAC consists of basically three parts:
1. `configuration.yaml`, containing all the sensors (including `nordpool_diff`), and the calculations defined as "template sensors",
  computing the desired temperature setpoint based on `nordpool_diff` output and e.g. outdoor and indoor temperature readings.
2. `automations.yaml`, containing trigger to adjust the thermostat/HVAC whenever the set temperature changes.
3. Connection to the thermostat/HVAC itself. Below I'm using https://esphome.io/components/climate/climate_ir.html with `ilp-remote.yaml` configured as follows:

 ```yaml
 esphome:
  name: ilp-remote
  platform: ESP32
  board: esp32dev

# Enable logging
logger:

# Enable Home Assistant API
api:

ota:
  password: !secret ota_password

wifi:
  ssid: !secret wifi_name
  password: !secret wifi_password

  # Enable fallback hotspot (captive portal) in case wifi connection fails
  ap:
    ssid: !secret fallback_ssid
    password: !secret fallback_password

captive_portal:

remote_transmitter:
  pin: GPIO27
  carrier_duty_percent: 50%

sensor:
  - platform: homeassistant
    id: sisalampotila
    entity_id: sensor.sisalampotila

climate:
  - platform: mitsubishi
    name: "ILP"
    sensor: sisalampotila
 ```


Rest of the configuration is set as follows.

`configuration.yaml`:
 ```yaml

sensor:

...here some nordpool and ruuvi configurations, giving sensor.sisalampotila and sensor.ulko_temperature

  - platform: nordpool_diff
    nordpool_entity: sensor.nordpool_kwh_fi_eur_3_095_024
    filter_length: 15
    filter_type: triangle
    normalize: max_min_sqrt_max

...

template:

  - sensor:
    - name: "ILP ulkolämpötilakomponentti"
      unit_of_measurement: "dT"
      state: >
        {% set ulko = states('sensor.ulko_temperature') | float(default=0) %}
        {{ (- 0.1 * ulko) | round(2) }}

  - sensor:
    - name: "ILP sisälämpötilakomponentti"
      unit_of_measurement: "dT"
      state: >
        {% set sisa = states('sensor.sisalampotila') | float(default=22) %}
        {% set ulko = states('sensor.ulko_temperature') | float(default=0) %}
        {{ (((22 + 0.05 * ulko) - sisa) * 1.0) | round(2) }}

  - sensor:
    - name: "ILP hintakomponentti"
      unit_of_measurement: "dT"
      state: >
        {% set npd = states('sensor.nordpool_diff_triangle_15_normalize_max_min_sqrt_max') | float(default=0) %}
        {## Limit price effect at negative side to -3 deg so that heating never completely stops when it's cold  ##}
        {{ [(15*npd) | round(2), -3] | max}}

  - sensor:
    - name: "ILP pyöristämätön ohjaus"
      unit_of_measurement: "°C"
      state: >
        {% set ulko_k = states('sensor.ilp_ulkolampotilakomponentti') | float(default=0) %}
        {% set sisa_k = states('sensor.ilp_sisalampotilakomponentti') | float(default=22) %}
        {% set hinta_k = states('sensor.ilp_hintakomponentti') | float(default=0) %}
        {{ [[(25.5 + ulko_k + sisa_k + hinta_k) | round(2), 31] | min, 16] | max}}

  - sensor:
    - name: "ILP ohjaus"
      unit_of_measurement: "°C"
      state: >
        {## Get our own current/previous state, this works! ##}
        {% set current = states('sensor.ilp_ohjaus') | float(default=25) %}
        {% set tentative = states('sensor.ilp_pyoristamaton_ohjaus') | float(default=25) %}
        {## Hysteresis, prevent jumping back and forth between x and x+1 when control is ~x.5  ##}
        {% if (current - tentative) | abs > 0.66 -%}
          {{ tentative | round(0) }}
        {%- else -%}
          {{ current | round(0) }}
        {%- endif %}

```


`automations.yaml`:
```yaml
- id: '1636432337197'
  alias: Ohjaa ILPiä
  description: ''
  trigger:
  - platform: state
    entity_id: sensor.ilp_ohjaus
  condition: []
  action:
  - service: climate.set_temperature
    target:
      entity_id: climate.ilp
    data:
      temperature: '{{ states.sensor.ilp_ohjaus.state | round(0, default=25) }}'
  mode: single
```
