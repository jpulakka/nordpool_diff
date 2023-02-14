# nordpool_diff custom component for Home Assistant

Electricity spot prices can be fetched from [ENTSO-E](https://transparency.entsoe.eu/) and [Nord Pool](https://www.nordpoolgroup.com/)
into Home Assistant, but making good use of those prices is not easy.
This component provides various algorithms whose output can be used for deciding when to turn water heater or
car charger on/off, or for adjusting target temperature of a heater so that it will heat more just before prices
will go up (to allow heating less when prices are high), and heat less just before prices will go down.

Apart from potentially saving some money, this kind of temporal shifting of consumption can also save the environment,
because expensive peaks are produced by dirtier energy sources. Also helps solving Europe's electricity crisis.

The output is most suitable for fine-tuning continuously adjustable things (thermostats), or it can be thresholded
to control binary things that can be switched on/off anytime, such as water heaters. So far it is not directly
suitable for controlling things that require N contiguous hours to work, such as washing machines. Also, there are
no guarantees about how many hours per day the output will stay above some threshold, even if typical price variations
may make the output typically behave this or that way most of the time.

## ENTSO-E vs. Nord Pool

This component was initially (in 2021) created to support https://github.com/custom-components/nordpool, hence the name.
But after that (in 2022) https://github.com/JaccoR/hass-entso-e became available. Besides being 100 % legal to use[^1],
ENTSO-E also covers wider range of markets than Nord Pool.

Since v0.2.0 hass-entso-e is preferred and default, but nordpool still works, and can also be used as an automatic fallback
mechanism to complement hass-entso-e when ENTSO-E API is down. The logic is as follows:
1. Look up prices from hass-entso-e, if exists.
2. If less than N upcoming hours available, then look up prices from nordpool too, if exists.
3. Use whichever (hass-entso-e or nordpool) provided more upcoming hours.

## Installation

1. Install `hass-entso-e` (https://github.com/JaccoR/hass-entso-e). When configuring it, you can leave "Name" blank.
2. Optionally: Install `nordpool` (https://github.com/custom-components/nordpool). You can also use just `nordpool` and not `hass-entso-e`, if you want to.
3. Install `nordpool_diff`, either using HACS or manually
     1. HACS
         1. Go to HACS -> Integrations
         2. Click the three dots on the top right and select `Custom Repositories`
         3. Enter `https://github.com/jpulakka/nordpool_diff` as repository, select the category `Integration` and click Add
         4. A new custom integration shows up for installation (Nordpool Diff) - install it
         5. Restart Home Assistant
      2. Manually
         1. Copy the `nordpool_diff` folder to HA `<config_dir>/custom_components/nordpool_diff/`
         2. Restart HA. (Skipping restarting before modifying configuration would give "Integration 'nordpool_diff' not found" error message from the configuration.)
4. Configure `nordpool_diff`. Add the following to your `configuration.yaml` file:
    ```yaml
    sensor:
      - platform: nordpool_diff
    ```
5. Restart HA again to load the configuration. Now you should see `nordpool_diff_triangle_10` sensor, where
   the `triangle_10` part corresponds to default values of optional parameters, explained below.

## Optional parameters

### Entsoe entity
The Entsoe entity holds the prices. 
If you left the "Name" empty when configuring hass-entso-e, it will be named `sensor.average_electricity_price_today`, and will be found automatically by this setup.
If you have different entity ID, you need to specify it, for example:

 ```yaml
 sensor:
   - platform: nordpool_diff
     entsoe_entity: sensor.average_electricity_price_today
 ```

### Nordpool entity
By default, Nordpool will not be used as a source for price information. If you want to use Nordpool, you must specify the entity ID, for example:
 ```yaml
 sensor:
   - platform: nordpool_diff
     nordpool_entity: sensor.nordpool_kwh_fi_eur_3_095_024
 ```

### Unit
`unit` defines what will be used as the unit for the sensor in Home Assistant. The default is `EUR/kWh/h` to reflect that the sensor output loosely speaking reflects change rate (1/h) of hourly price (EUR/kWh). Example:
 
 ```yaml
 sensor:
   - platform: nordpool_diff
     unit: EUR/kWh/h
 ```

### Filter length
The filter length tells now many hours into the future that will be taken into account when defining the filter output.

`filter_length` must be an integer between 2...20, and if not specified will default to 10. Example:

 ```yaml
 sensor:
   - platform: nordpool_diff
     filter_length: 10
 ```

### Filter type (triangle and rectangle)
`filter_type` can be one of `triangle`, `rectangle`, `rank` or `interval`. If not set, it will default to `triangle`.
They are best understood by examples. You can set up several `nordpool_diff` entities,
each with different parameters, plot them in the dashboard, and pick what you like best.
Here is an example:

![Diff example](diff_example.png)

`filter_type: triangle` and `filter_type: rectangle` are linear filters. They apply non-causal FIR differentiator[^2] to spot prices,
resulting in a predictive sensor that gives positive output when the price of electricity for the current hour is cheaper
compared to the next few hours (and negative output in the opposite case).

For illustrative purposes, the following FIRs reflect the time axis; the first multiplier corresponds to
current hour and the next multipliers correspond to upcoming hours.

`filter_length: 2`
This is the smallest possible filter length. The price for the current hour is subtracted from the price of the next hour.
For example, if the current current price and the price of the next hour is exactly the same, the value will be zero.
With `filter_length: 2`, the filter types `rectangle` and `triangle` will yield identical filters:
* `filter_type: rectangle` creates FIR `[-1, 1]`
* `filter_type: triangle` creates FIR `[-1, 1]`

`filter_length: 3`,
With filter length of 3, we start to see how `triangle` puts more weight on the price of the next hour than the second-next hour.
With `rectangle`, both future hours are weighted equally.
* `filter_type: rectangle` creates FIR `[-1, 1/2, 1/2]`
* `filter_type: triangle` creates FIR `[-1, 2/3, 1/3]`

`filter_length: 4`,
* `filter_type: rectangle` creates FIR `[-1, 1/3, 1/3, 1/3]`
* `filter_type: triangle` creates FIR `[-1, 3/6, 2/6, 1/6]`

`filter_length: 5`,
* `filter_type: rectangle` creates FIR `[-1, 1/4, 1/4, 1/4, 1/4]`
* `filter_type: triangle` creates FIR `[-1, 4/10, 3/10, 2/10, 1/10]`

And so on. With rectangle, the right side of the filter is "flat". With triangle, the right side is weighting soon
upcoming hours more than the farther away "tail" hours. First entry is always -1 and the filter is normalized so that
its sum is zero. This way the characteristic output magnitude is independent of the settings.

#### Normalize
Normalize is relevant if you are using `filter_type: rectangle` or `filter_type: triangle`,
and is highly recommended to be used if you use those filters for anything else than thresholding on 0.
When using normalize, you should use a `filter_length` of 10 or more, for it to work well.

`filter_type: rectangle` or `filter_type: triangle` have a magnitude of output that is proportional to the magnitude of the input,
being the price (variations) of electricity. Between 2021-2022, that increased tenfold, so the characteristic
output of the filter also increased tenfold. That caused problems in proportional controllers; if a heater target
used to be adjusted roughly +-2 deg C, it's not reasonable for that to become +-20 deg C, no matter how the electricity prices evolve.

To compensate for that, `normalize` was introduced. Options include:
* `normalize: no` = no normalization, default.
* `normalize: max` = output of the filter is divided by maximum price of the next `filter_length` hours.
* `normalize: max_min` = output of the filter is divided by maximum minus minimum price of the next `filter_length` hours.
* `normalize: sqrt_max` = output of the filter is divided by square root of maximum price of the next `filter_length` hours. This provides "somewhat scale-free normalization" where the output magnitude depends on price magnitude, but not linearly so.
* `normalize: max_min_sqrt_max` = output of the filter is multiplied by square root of maximum price of the next `filter_length` hours and divided by maximum minus minimum price of the next `filter_length` hours. This is maybe the best ("somewhat scale-free") normalization. Think about it this way:
  * Raw output of the FIR differentiator is proportional to price *variation*.
  * Divide by maximum minus minimum price (= price variation; could also use e.g. standard deviation), to get scale-free output.
  * Multiply by square root of maximum price (could also use e.g. average, but max is good enough and besides less likely negative), to introduce scale. So now 9x price gives 3x output.

Possible edge cases of price staying exactly constant, zero or negative for long time are handled gracefully.

### Filter type (rank and interval)

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
binary things can only be turned on/off, such as water heaters. The `normalize` parameter has no effect on `rank` nor `interval`.

## Attributes

Apart from the principal value, the sensor provides an attribute `next_hour`, which can be useful when we're close to
hour boundary and making decisions about turning something on or off; if it's xx:59 and the principal value is above some
threshold but the next hour value is below the threshold, and we would like to avoid short "on" cycles, then we maybe
shouldn't turn the thing on at xx:59 if we would turn it off only after 1 minute. This can be avoided by taking the next
hour value into account.

## Debug logging

Add the following to `configuration.yaml`:

 ```yaml
logger:
  default: info
  logs:
    custom_components.nordpool_diff.sensor: debug
```

[^1]: [Nord Pool API documentation](https://www.nordpoolgroup.com/en/trading/api/) states
_If you are a Nord Pool customer, using our trading APIs is for free. All others must become a customer to use our APIs._
Which apparently means that almost nobody should be using it, even though the API is technically public and appears to work without any tokens.
It's more correct to use [ENTSO-E](https://transparency.entsoe.eu/) which is intended to be used by anyone.

[^2]: Fancy way of saying that the price for the current hour is subtracted from the average price for the next few
hours.
