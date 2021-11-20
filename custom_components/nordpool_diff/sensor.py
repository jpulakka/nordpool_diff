from __future__ import annotations

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt

NORDPOOL_ENTITY = "nordpool_entity"
FILTER_LENGTH = "filter_length"
FILTER_TYPE = "filter_type"
RECTANGLE = "rectangle"
TRIANGLE = "triangle"
NAME = "name"
UNIT = "unit"

# https://developers.home-assistant.io/docs/development_validation/
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(NORDPOOL_ENTITY): cv.entity_id,
    vol.Optional(FILTER_LENGTH, default=2): vol.All(vol.Coerce(int), vol.Range(min=2, max=15)),
    vol.Optional(FILTER_TYPE, default=RECTANGLE): vol.In([RECTANGLE, TRIANGLE]),
    vol.Optional(NAME, default=""): cv.string,
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
    name = config[NAME]
    unit = config[UNIT]

    add_entities([NordpoolDiffSensor(hass, nordpool_entity_id, filter_length, filter_type, name, unit)])


class NordpoolDiffSensor(SensorEntity):

    def __init__(self, hass, nordpool_entity_id, filter_length, filter_type, name, unit):
        self._state = None
        self._hass = hass
        self._nordpool_entity_id = nordpool_entity_id
        self._filter = [-1]
        if filter_type == TRIANGLE:
            triangular_number = (filter_length * (filter_length - 1)) / 2
            for i in range(filter_length - 1, 0, -1):
                self._filter += [i / triangular_number]
        else:  # RECTANGLE
            self._filter += [1 / (filter_length - 1)] * (filter_length - 1)
        self._unique = f"nordpool_diff_{filter_type}_{filter_length}"
        self._name = name if name else self._unique
        self._unit = unit

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self):
        return self._unique

    @property
    def icon(self) -> str:
        return "mdi:flash"  # TODO mikä olis hyvä, https://pictogrammers.github.io/@mdi/font/6.4.95/

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        return self._unit

    def update(self) -> None:
        prices = self._get_next_n_hours(len(self._filter))
        filtered = [a * b for a, b in zip(prices, self._filter)]
        self._state = round(sum(filtered), 3)

    def _get_next_n_hours(self, n):
        np = self._hass.states.get(self._nordpool_entity_id)
        prices = np.attributes["today"]
        hour = dt.now().hour
        # Get tomorrow if needed:
        if len(prices) < hour + n and np.attributes["tomorrow_valid"]:
            prices = prices + np.attributes["tomorrow"]
        # Pad if needed, using last element:
        prices = prices + (hour + n - len(prices)) * [prices[-1]]
        return prices[hour: hour + n]
