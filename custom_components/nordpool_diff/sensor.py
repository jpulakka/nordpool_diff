from __future__ import annotations

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt

NORDPOOL_ENTITY = "nordpool_entity"
FILTER_LENGTH = "filter_length"
FILTER_TYPE = "filter_type"
RECTANGLE = "rectangle"
TRIANGLE = "triangle"
UNIT = "unit"

# https://developers.home-assistant.io/docs/development_validation/
# https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/config_validation.py
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(NORDPOOL_ENTITY): cv.entity_id,
    vol.Optional(FILTER_LENGTH, default=2): vol.All(vol.Coerce(int), vol.Range(min=2, max=15)),
    vol.Optional(FILTER_TYPE, default=RECTANGLE): vol.In([RECTANGLE, TRIANGLE]),
    vol.Optional(UNIT, default="EUR/kWh/h"): cv.string
})


def setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None
) -> None:
    nordpool_entity_id = config[NORDPOOL_ENTITY]
    filter_length = config[FILTER_LENGTH]
    filter_type = config[FILTER_TYPE]
    unit = config[UNIT]

    add_entities([NordpoolDiffSensor(nordpool_entity_id, filter_length, filter_type, unit)])


class NordpoolDiffSensor(SensorEntity):
    _attr_icon = "mdi:flash"

    def __init__(self, nordpool_entity_id, filter_length, filter_type, unit):
        self._state = STATE_UNKNOWN
        self._nordpool_entity_id = nordpool_entity_id
        self._filter = [-1]
        if filter_type == TRIANGLE:
            triangular_number = (filter_length * (filter_length - 1)) / 2
            for i in range(filter_length - 1, 0, -1):
                self._filter += [i / triangular_number]
        else:  # RECTANGLE
            self._filter += [1 / (filter_length - 1)] * (filter_length - 1)
        self._attr_name = f"nordpool_diff_{filter_type}_{filter_length}"
        # https://developers.home-assistant.io/docs/entity_registry_index/ : Entities should not include the domain in
        # their Unique ID as the system already accounts for these identifiers:
        self._attr_unique_id = f"{filter_type}_{filter_length}_{unit}"  # TODO should this rather be a hash?
        self._attr_unit_of_measurement = unit
        self._next_hour = STATE_UNKNOWN

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        # TODO could also add self._nordpool_entity_id etc. useful properties here.
        return {"next_hour": self._next_hour}

    def update(self):
        prices = self._get_next_n_hours(len(self._filter) + 1)  # +1 to calculate next hour
        self._state = round(sum([a * b for a, b in zip(prices, self._filter)]), 3)  # zip cuts off right
        self._next_hour = round(sum([a * b for a, b in zip(prices[1:], self._filter)]), 3)

    def _get_next_n_hours(self, n):
        np = self.hass.states.get(self._nordpool_entity_id)
        prices = np.attributes["today"]
        hour = dt.now().hour
        # Get tomorrow if needed:
        if len(prices) < hour + n and np.attributes["tomorrow_valid"]:
            prices = prices + np.attributes["tomorrow"]
        # Pad if needed, using last element:
        prices = prices + (hour + n - len(prices)) * [prices[-1]]
        return prices[hour: hour + n]
