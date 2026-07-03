"""Device tracker platform for Evolute."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EvoluteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evolute device trackers based on a config entry."""
    coordinator: EvoluteDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [EvoluteDeviceTracker(coordinator, car) for car in coordinator.cars]
    async_add_entities(entities)


class EvoluteDeviceTracker(CoordinatorEntity, TrackerEntity):
    """Representation of an Evolute GPS tracker."""

    def __init__(
        self, coordinator: EvoluteDataUpdateCoordinator, car: dict[str, Any]
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._car_id = car["car_id"]

        self._attr_name = car.get("name") or f"Evolute {self._car_id}"
        self._attr_unique_id = f"evolute_{self._car_id}_tracker"
        self.entity_id = f"device_tracker.evolute_{self._car_id}"
        self._attr_icon = "mdi:car"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._car_id)},
            "name": car.get("name") or f"Evolute {self._car_id}",
            "manufacturer": "Evolute",
            "model": car.get("model"),
            "suggested_area": "Garage",
        }

    def _car_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._car_id, {})

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        lat = self._car_data().get("latitude")
        if lat is None:
            return None
        try:
            lat_float = float(lat)
        except (TypeError, ValueError):
            return None
        return lat_float if -90 <= lat_float <= 90 else None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        lon = self._car_data().get("longitude")
        if lon is None:
            return None
        try:
            lon_float = float(lon)
        except (TypeError, ValueError):
            return None
        return lon_float if -180 <= lon_float <= 180 else None

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            bool(self.coordinator.data)
            and self._car_id in self.coordinator.data
            and self.latitude is not None
            and self.longitude is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        data = self._car_data()
        attributes: dict[str, Any] = {}
        for key in ("course", "altitude", "satellites", "hdop", "speed"):
            if data.get(key) is not None:
                attributes[key] = data[key]
        return attributes
