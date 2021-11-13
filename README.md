# nordpool_diff custom integration for Home Assistant

Requires https://github.com/custom-components/nordpool

Applies non-causal FIR differentiator[^1] to [Nord Pool](https://www.nordpoolgroup.com/) SPOT prices, resulting in
predictive sensor that:

* Gives positive output when electricity prices are going to increase in the next few hours
* Gives negative output when electricity prices are going to decrease in the next few hours
* Gives ~zero output when electricity prices are going to stay ~constant for the next few hours

The output can be used for e.g. temporal shifting of heating, by adjusting target temperature of a heater so that it
will heat a bit more just before prices will go up (so that we can heat less when prices are high), and let the
temperature go down a bit just before prices will go down (because soon we can heat cheaper).

Apart from potentially saving some money, this can also save the environment, because expensive peaks are produced by
dirtier energy sources.

### Installation

1. Install and configure https://github.com/custom-components/nordpool first.
2. Copy the `nordpool_diff` folder to HA `<config_dir>/custom_components/nordpool_diff/`.
3. Restart HA. (Failing to restart before modifying configuration would give "Integration 'nordpool_diff' not found"
   error message from the configuration.)
4. Add the following to your `configuration.yaml` file:

 ```yaml
 sensor:
   - platform: nordpool_diff
     nordpool_entity: sensor.nordpool_kwh_fi_eur_3_095_024
     filter_length: 5
 ```

Modify the `nordpool_entity` value according to your exact entity value.

The `filter_length` value must be an integer, at least 2. Smallest possible value 2 produces FIR `[-1, 1]`. Value 5
produces FIR `[-1, 0.25, 0.25, 0.25, 0.25]`. First entry is always -1 and the filter is normalized so that its sum is
zero. This way the characteristic output magnitude is independent of the filter length. Values larger than 8 have the
problem that prices typically update 8 hours before midnight (in Finland), so at 15:59 you only know prices for the next
8 hours. But the filter algorithm pads missing data by using the last entry, so the result should still be quite
reasonable.

Restart HA again to load the configuration. Now you should see `nordpool_filtered_N` sensor, where `N`
corresponds to `filter_length`. You can set up several `nordpool_diff` entities, each with different `filter_length`.

---

[^1]: Fancy way of saying that the price for the current hour is subtracted from the average price for the next few
hours.