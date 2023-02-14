# Examples on using the filter output for adjusting thermostat

`configuration.yaml`:
 ```yaml

sensor:

...here some nordpool and ruuvi configurations

  - platform: nordpool_diff
    nordpool_entity: sensor.nordpool_kwh_fi_eur_3_095_024
    filter_length: 15
    filter_type: triangle
    normalize: max_min

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
        {## Limit price effect at negative side to -3 deg so that heating never stops when it's cold (ulkokomponentti +2 -> lähtöpiste +27.5)  ##}
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
