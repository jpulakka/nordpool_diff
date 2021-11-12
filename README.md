# nordpool_diff custom component for Home Assistant

Requires https://github.com/custom-components/nordpool

Applies non-causal FIR differentiator to Nord Pool SPOT prices, resulting in Home Assistant sensor that:

* Gives positive output when electricity prices are going to increase in the next few hours, compared to current hour
* Gives negative output when electricity prices are going to decrease in the next few hours, compared to current hour
* Gives ~zero output when electricity prices are going to stay ~constant for the next few hours

The resulting number can be used for e.g. temporal heating shifting, to adjust target temperature of a heater so that it
will heat a bit more just before prices will go up (so that we can heat less when prices are high), and let the
temperature go down a bit just before prices will go down (because soon we can heat cheaper).

Apart from potentially saving some money, this can also save the environment, because expensive peaks are produced by
dirtier energy sources.

### Installation

Install and configure https://github.com/custom-components/nordpool first.

Copy the `nordpool_diff` folder to Home Assistant `<config_dir>/custom_components/nordpool_diff/`.

Restart Home Assistant. (Failing to restart before modifying configuration would give "Integration 'nordpool_diff' not
found" error message from the configuration.)

Add the following to your `configuration.yaml` file:

```yaml
sensor:
  - platform: nordpool_diff
    nordpool-entity: sensor.nordpool_kwh_fi_eur_3_095_024
    filter-length: 5
```

Modify the `nordpool-entity` value according to your exact entity value.

FIXME filter-length olkoon N(?), vähintään 1.

_Applying non-causal FIR differentiator to Nord Pool SPOT prices_ is just a fancy way of saying that price of current
hour is subtracted from average price of next few hours.

The `filter-length` value must be an integer, at least 2. Smallest value 2 produces FIR `[-1, 1]`. Value 5 produces
FIR `[-1, 0.25, 0.25, 0.25, 0.25]`. First entry is always -1 and the filter is normalized so that its sum is zero. This
way the characteristic output magnitude is independent of the filter length. Values larger than 8 have the problem that
Nordpool prices typically update 8 hours before midnight (in Finland), so at 15:59 you only know prices for the next 8
hours. But the filter algorithm pads missing data by using the last entry, so the result should still be quite
reasonable.

Restart Home Assistant again to load the configuration. Now you should see XXX.