from __future__ import annotations

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt
from datetime import datetime, timedelta
from math import sqrt

_LOGGER = logging.getLogger(__name__)

NORDPOOL_ENTITY = "nordpool_entity"
ENTSOE_ENTITY = "entsoe_entity"
FILTER_LENGTH = "filter_length"
FILTER_TYPE = "filter_type"
RECTANGLE = "rectangle"
TRIANGLE = "triangle"
RANK = "rank"
INTERVAL = "interval"
NORMALIZE = "normalize"
NO = "no"
MAX = "max"
MAX_MIN = "max_min"
SQRT_MAX = "sqrt_max"
MAX_MIN_SQRT_MAX = "max_min_sqrt_max"
UNIT = "unit"

# https://developers.home-assistant.io/docs/development_validation/
# https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/config_validation.py
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(NORDPOOL_ENTITY, default=""): cv.string,  # Is there a way to require EITHER nordpool OR entsoe being valid cv.entity_id?
    vol.Optional(ENTSOE_ENTITY, default="sensor.average_electricity_price_today"): cv.string,  # hass-entso-e's default entity id
    vol.Optional(FILTER_LENGTH, default=10): vol.All(vol.Coerce(int), vol.Range(min=2, max=20)),
    vol.Optional(FILTER_TYPE, default=TRIANGLE): vol.In([RECTANGLE, TRIANGLE, INTERVAL, RANK]),
    vol.Optional(NORMALIZE, default=NO): vol.In([NO, MAX, MAX_MIN, SQRT_MAX, MAX_MIN_SQRT_MAX]),
    vol.Optional(UNIT, default="EUR/kWh/h"): cv.string
})


def setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None
) -> None:
    nordpool_entity_id = config[NORDPOOL_ENTITY]
    entsoe_entity_id = config[ENTSOE_ENTITY]
    filter_length = config[FILTER_LENGTH]
    filter_type = config[FILTER_TYPE]
    normalize = config[NORMALIZE]
    unit = config[UNIT]

    add_entities([NordpoolDiffSensor(nordpool_entity_id, entsoe_entity_id, filter_length, filter_type, normalize, unit)])

def _with_interval(prices):
    p_min = min(prices)
    p_max = max(prices)
    if not p_max > p_min:
        return 0
    return 1 - 2 * (prices[0]-p_min)/(p_max-p_min)

def _with_rank(prices):
    return 1 - 2 * sorted(prices).index(prices[0]) / (len(prices) - 1)

def _with_filter(filter, normalize):
    return lambda prices : sum([a * b for a, b in zip(prices, filter)]) * normalize(prices)

def _get_next_n_hours_from_nordpool(n, np):
    prices = np.attributes["today"]
    hour = dt.now().hour
    # Get tomorrow if needed:
    if len(prices) < hour + n and np.attributes["tomorrow_valid"]:
        prices = prices + np.attributes["tomorrow"]
    # Nordpool sometimes returns null prices, https://github.com/custom-components/nordpool/issues/125
    # The nulls are typically at (tail of) "tomorrow", so simply removing them is reasonable:
    prices = [x for x in prices if x is not None]
    return prices[hour: hour + n]

def _get_next_n_hours_from_entsoe(n, e):
    prices = []
    if p := e.attributes.get("prices"):
        hour_before_now = dt.utcnow() - timedelta(hours=1)
        for item in p:
            if prices or hour_before_now <= datetime.fromisoformat(item["time"]):
                prices.append(item["price"])
                if len(prices) == n:
                    break
    return prices

class NordpoolDiffSensor(SensorEntity):
    _attr_icon = "mdi:flash"

    def __init__(self, nordpool_entity_id, entsoe_entity_id, filter_length, filter_type, normalize, unit):
        self._nordpool_entity_id = nordpool_entity_id
        self._entsoe_entity_id = entsoe_entity_id
        self._filter_length = filter_length
        if normalize == MAX:
            normalize = lambda prices : 1 / (max(prices) if max(prices) > 0 else 1)
            normalize_suffix = "_normalize_max"
        elif normalize == MAX_MIN:
            normalize = lambda prices : 1 / (max(prices) - min(prices) if max(prices) - min(prices) > 0 else 1)
            normalize_suffix = "_normalize_max_min"
        elif normalize == SQRT_MAX:
            normalize = lambda prices: 1 / sqrt(max(prices) if max(prices) > 0 else 1)
            normalize_suffix = "_normalize_sqrt_max"
        elif normalize == MAX_MIN_SQRT_MAX:
            normalize = lambda prices: sqrt(max(prices) if max(prices) > 0 else 0) \
                                       / (max(prices) - min(prices) if max(prices) - min(prices) > 0 else 1)
            normalize_suffix = "_normalize_max_min_sqrt_max"
        else:  # NO
            normalize = lambda prices : 1
            normalize_suffix = ""
        if filter_type == RANK:
            self._compute = _with_rank
        elif filter_type == INTERVAL:
            self._compute = _with_interval
        elif filter_type == TRIANGLE:
            filter = [-1]
            triangular_number = (filter_length * (filter_length - 1)) / 2
            for i in range(filter_length - 1, 0, -1):
                filter += [i / triangular_number]
            self._compute = _with_filter(filter, normalize)
        else:  # RECTANGLE
            filter = [-1]
            filter += [1 / (filter_length - 1)] * (filter_length - 1)
            self._compute = _with_filter(filter, normalize)
        self._attr_native_unit_of_measurement = unit
        self._attr_name = f"nordpool_diff_{filter_type}_{filter_length}{normalize_suffix}"
        # https://developers.home-assistant.io/docs/entity_registry_index/ : Entities should not include the domain in
        # their Unique ID as the system already accounts for these identifiers:
        self._attr_unique_id = f"{filter_type}_{filter_length}_{unit}{normalize_suffix}"
        self._state = self._next_hour = STATE_UNKNOWN

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        # TODO could also add self._nordpool_entity_id etc. useful properties here.
        return {"next_hour": self._next_hour}

    def update(self):
        prices = self._get_next_n_hours(self._filter_length + 1)  # +1 to calculate next hour
        self._state = round(self._compute(prices[:-1]), 3)
        self._next_hour = round(self._compute(prices[1:]), 3)
        # TODO here could add caching, this really needs to be recalculated only each xx:00 if successful.

    def _get_next_n_hours(self, n):
        prices = []
        # Prefer entsoe:
        if e := self.hass.states.get(self._entsoe_entity_id):
            try:
                prices = _get_next_n_hours_from_entsoe(n, e)
                _LOGGER.debug(f"{n} prices from entsoe {prices}")
            except:
                _LOGGER.exception("_get_next_n_hours_from_entsoe")
        # Fall back to nordpool:
        if (len(prices) < n) and (np := self.hass.states.get(self._nordpool_entity_id)):
            try:
                np_prices = _get_next_n_hours_from_nordpool(n, np)
                _LOGGER.debug(f"{n} prices from nordpool {np_prices}")
                if len(np_prices) > len(prices):
                    prices = np_prices
            except:
                _LOGGER.exception("_get_next_n_hours_from_nordpool")
        # Fail gracefully if nothing works:
        if not prices:
            return n * [0]
        # Pad if needed, using last element.
        prices = prices + (n - len(prices)) * [prices[-1]]
        _LOGGER.debug(f"{n} prices after padding {prices}")
        return prices
