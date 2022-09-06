# nordpool_diff custom component for Home Assistant

Requires https://github.com/custom-components/nordpool

[Nord Pool](https://www.nordpoolgroup.com/) gives you spot prices, but making good use of those prices is not easy.
This component provides various algorithms whose output can be used for deciding when to turn water heater or
car charger on/off, or for adjusting target temperature of a heater so that it will heat more just before prices
will go up (to allow heating less when prices are high), and heat less just before prices will go down.

Apart from potentially saving some money, this kind of temporal shifting of consumption can also save the environment,
because expensive peaks are produced by dirtier energy sources. Also helps solving Europe's electricity crisis.

## Installation

1. Install and configure https://github.com/custom-components/nordpool first.
2. Copy the `nordpool_diff` folder to HA `<config_dir>/custom_components/nordpool_diff/`
3. Restart HA. (Skipping restarting before modifying configuration would give "Integration 'nordpool_diff' not found"
   error message from the configuration.)
4. Add the following to your `configuration.yaml` file:

    ```yaml
    sensor:
      - platform: nordpool_diff
        nordpool_entity: sensor.nordpool_kwh_fi_eur_3_095_024
    ```

   Modify the `nordpool_entity` value according to your exact nordpool entity ID.

5. Restart HA again to load the configuration. Now you should see `nordpool_diff_triangle_10` sensor, where
   the `triangle_10` part corresponds to default values of optional parameters, explained below.

## Optional parameters

Optional parameters to configure include `filter_length`, `filter_type`, `unit` and `normalize`, defaults are `10`, `triangle`,
`EUR/kWh/h` and `no`, respectively:

 ```yaml
 sensor:
   - platform: nordpool_diff
     nordpool_entity: sensor.nordpool_kwh_fi_eur_3_095_024
     filter_length: 10
     filter_type: triangle
     unit: EUR/kWh/h
     normalize: no
 ```

`unit` can be any string. The default is EUR/kWh/h to reflect that the sensor output loosely speaking reflects change
rate (1/h) of hourly price (EUR/kWh).

`filter_length` value must be an integer between 2...20, and `filter_type` must be either `triangle`, `rectangle`,
`rank` or `interval`. They are best explained by examples. You can set up several `nordpool_diff` entities,
each with different parameters, plot them in Lovelace, and pick what you like best. Here is an example:

![Diff example](diff_example.png)

## Triangle and rectangle

`filter_type: triangle` and `filter_type: rectangle` are linear filters. They apply non-causal FIR differentiator[^1] to spot prices,
resulting in a predictive sensor that gives positive output when the price of electricity for the current hour is cheaper
compared to the next few hours (and negative output in the opposite case).

For illustrative purposes, the following FIRs have been reflected about the time axis; the first multiplier corresponds to
current hour and the next multipliers correspond to upcoming hours.

Smallest possible `filter_length: 2` creates FIR `[-1, 1]`. That is, price for the current hour is subtracted from the
price of the next hour. In this case `filter_type: rectangle` and `filter_type: triangle` are identical.

`filter_length: 3`, `filter_type: rectangle` creates FIR `[-1, 1/2, 1/2]`

`filter_length: 3`, `filter_type: triangle` creates FIR `[-1, 2/3, 1/3]`

`filter_length: 4`, `filter_type: rectangle` creates FIR `[-1, 1/3, 1/3, 1/3]`

`filter_length: 4`, `filter_type: triangle` creates FIR `[-1, 3/6, 2/6, 1/6]`

`filter_length: 5`, `filter_type: rectangle` creates FIR `[-1, 1/4, 1/4, 1/4, 1/4]`

`filter_length: 5`, `filter_type: triangle` creates FIR `[-1, 4/10, 3/10, 2/10, 1/10]`

And so on. With rectangle, the right side of the filter is "flat". With triangle, the right side is weighting soon
upcoming hours more than the farther away "tail" hours. First entry is always -1 and the filter is normalized so that
its sum is zero. This way the characteristic output magnitude is independent of the settings.

### Normalize

With linear filters `filter_type: triangle` and `filter_type: rectangle`, magnitude of output is proportional to
magnitude of input = price (variations) of electricity. Between 2021-2022, that has increased tenfold, so the characteristic
output magnitude of the filter has also increased tenfold. That causes problems in proportional controllers; if a heater target
used to be adjusted roughly +-2 deg C, it's not reasonable for that to become +-20 deg C, no matter how the electricity prices evolve.

To compensate for that, `normalize` was introduced. Current options include `normalize: no` (no normalization, default),
`normalize: max` (output of the filter is divided by maximum price of the next `filter_length` hours), and `normalize: max_min`
(output of the filter is divided by maximum minus minimum price of the next `filter_length` hours). These work reasonably when
`filter_length` is 10 or more, making the output magnitude less dependent of current overall electricity price.
And might fail spectacularly if price or its variation is very low for long time.

## Rank and interval

With `filter_type: rank`, the current price is ranked amongst the next `filter_length` prices. The lowest price is given
a value of `1`, the highest price is given the value of `-1`, and the other prices are equally distributed in this 
interval.

With `filter_type: interval`, the current price is placed inside the interval of the next `filter_length` prices. The
lowest price is given a value of `1`, the highest price is given the value of `-1`, and the current price is linearly
placed inside this interval.

If the current price is the lowest or highest price for the next `filter_length` prices, both filter types will output
`1` or `-1`, respectively.  If the next three prices are `1.4`, `1` and `2`, the `rank` filter will output `0` and the
`interval` filter will output `0.2`.

Since the output magnitude of the `rank` and `interval` filters are always between -1 and +1, independent of magnitude
of price variation, it may be more appropriate (than the linear FIR filters) for simple thresholding and controlling
binary things can only be turned on/off, such as water heaters. `normalize` setting has no effect on `rank` nor `interval`.

## Attributes

Apart from the principal value, the sensor provides an attribute `next_hour`, which can be useful when we're close to
hour boundary and making decisions about turning something on or off; if it's xx:59 and the principal value is above some
threshold but the next hour value is below the threshold, and we would like to avoid short "on" cycles, then we maybe
shouldn't turn the thing on at xx:59 if we would turn it off only after 1 minute. This can be avoided by taking the next
hour value into account.

[^1]: Fancy way of saying that the price for the current hour is subtracted from the average price for the next few
hours.
