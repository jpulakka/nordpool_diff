from __future__ import annotations

import voluptuous as vol
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

# https://developers.home-assistant.io/docs/development_validation/
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(NORDPOOL_ENTITY): str,
    # TODO add sanity checks for filter-length, maybe optional with good default?
    vol.Required(FILTER_LENGTH): vol.Coerce(int),
    # TODO add optional name, adjustable unit
    vol.Optional(FILTER_TYPE, default=RECTANGLE): vol.In([RECTANGLE, TRIANGLE])
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

    add_entities([NordpoolDiffSensor(hass, nordpool_entity_id, filter_length, filter_type)])


class NordpoolDiffSensor(SensorEntity):

    def __init__(self, hass, nordpool_entity_id, filter_length, filter_type):
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
        self._name = f"nordpool_diff_{filter_length}"

    @property
    def name(self) -> str:
        return self._name

    @property
    def icon(self) -> str:
        return "mdi:flash"  # TODO mikä olis hyvä, https://pictogrammers.github.io/@mdi/font/6.4.95/

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        return "EUR/kWh/h"  # TODO this should depend on nordpool unit, or at least make adjustable

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
