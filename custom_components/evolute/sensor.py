"""Sensor platform for Evolute."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPES
from .coordinator import EvoluteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evolute sensors based on a config entry."""
    coordinator: EvoluteDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for car in coordinator.cars:
        for sensor_key, (name, unit, device_class, icon, state_key, state_class) in SENSOR_TYPES.items():
            entities.append(
                EvoluteSensor(
                    coordinator, car, sensor_key, name, unit, device_class, icon, state_key, state_class
                )
            )

    async_add_entities(entities)


class EvoluteSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Evolute sensor."""

    def __init__(
        self,
        coordinator: EvoluteDataUpdateCoordinator,
        car: dict[str, Any],
        sensor_key: str,
        name: str,
        unit: str | None,
        device_class: str | None,
        icon: str | None,
        state_key: str,
        state_class: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._car_id = car["car_id"]
        self._state_key = state_key

        self._attr_name = name
        self._attr_unique_id = f"evolute_{self._car_id}_{sensor_key}"
        self.entity_id = f"sensor.evolute_{self._car_id}_{sensor_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_state_class = state_class

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._car_id)},
            "name": car.get("name") or f"Evolute {self._car_id}",
            "manufacturer": "Evolute",
            "model": car.get("model"),
            "suggested_area": "Garage",
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        car_data = self.coordinator.data.get(self._car_id, {})
        return car_data.get(self._state_key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return bool(self.coordinator.data) and self._car_id in self.coordinator.data
