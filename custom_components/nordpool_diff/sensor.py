from __future__ import annotations

import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required("nordpool-entity"): str,
    vol.Required("filter-length"): vol.Coerce(int)
})


def setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None
) -> None:
    nordpool_entity_id = config["nordpool-entity"]
    filter_length = config["filter-length"]

    add_entities([NordpoolDiffSensor(hass, nordpool_entity_id, filter_length)])


class NordpoolDiffSensor(SensorEntity):

    def __init__(self, hass, nordpool_entity_id, filter_length):
        # TODO sanity checks for input, good defaults, fail
        self._state = None
        self._hass = hass
        self._nordpool_entity_id = nordpool_entity_id
        self._filter = [-1] + [1 / (filter_length - 1)] * (filter_length - 1)
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
        return "EUR/kWh/h"  # TODO this should depend on nordpool unit

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
