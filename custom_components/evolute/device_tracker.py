"""Device tracker platform for Evolute with GNSS anti-spoofing and velocity validation."""
from __future__ import annotations

import logging
import math
import time
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EvoluteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Outlier & spoofing rejection thresholds
MAX_APPARENT_SPEED_KMH = 150.0  # Reject jumps with calculated velocity > 150 km/h
MAX_TIME_GAP_FOR_RECOVERY_SEC = 600.0  # 10 min time gap accepts new position (reboot/tow)
MAX_CONSECUTIVE_REJECTIONS_BEFORE_RESET = 4  # Accept new position if 4 consecutive polls agree


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two GPS points in meters."""
    r = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


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
    """Representation of an Evolute GPS tracker with anti-spoofing filter."""

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

        # Filter state
        self._filtered_lat: float | None = None
        self._filtered_lon: float | None = None
        self._last_valid_time: float = 0.0
        self._consecutive_rejected: int = 0
        self._gps_spoofed: bool = False

        # Run initial coordinate evaluation if data is present
        self._filter_current_coordinates()

    def _car_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._car_id, {})

    def _filter_current_coordinates(self) -> None:
        """Filter incoming raw GPS coordinates to reject GNSS spoofing and jamming spikes."""
        raw_lat = self._car_data().get("latitude")
        raw_lon = self._car_data().get("longitude")
        if raw_lat is None or raw_lon is None:
            return

        try:
            lat_float = float(raw_lat)
            lon_float = float(raw_lon)
        except (TypeError, ValueError):
            return

        if not (-90.0 <= lat_float <= 90.0 and -180.0 <= lon_float <= 180.0):
            return

        now = time.monotonic()

        # Initial point initialization
        if self._filtered_lat is None or self._filtered_lon is None:
            self._filtered_lat = lat_float
            self._filtered_lon = lon_float
            self._last_valid_time = now
            self._consecutive_rejected = 0
            self._gps_spoofed = False
            return

        dt = max(1.0, now - self._last_valid_time)
        dist = _haversine_distance(self._filtered_lat, self._filtered_lon, lat_float, lon_float)
        speed_kmh = (dist / dt) * 3.6

        data = self._car_data()
        hdop = data.get("hdop", 0.0) or 0.0
        satellites = data.get("satellites", 10) or 10
        try:
            hdop = float(hdop)
            satellites = int(satellites)
        except (ValueError, TypeError):
            hdop, satellites = 0.0, 10

        # Outlier conditions:
        # 1. Impossible speed (> 150 km/h)
        # 2. Large jump (> 300m) with degraded GNSS signal (HDOP > 3.5 or satellites < 5)
        is_speed_outlier = speed_kmh > MAX_APPARENT_SPEED_KMH
        is_signal_outlier = dist > 300.0 and (hdop > 3.5 or satellites < 5)

        if (is_speed_outlier or is_signal_outlier) and dt < MAX_TIME_GAP_FOR_RECOVERY_SEC:
            self._consecutive_rejected += 1
            if self._consecutive_rejected < MAX_CONSECUTIVE_REJECTIONS_BEFORE_RESET:
                _LOGGER.warning(
                    "Evolute GPS outlier/spoofing rejected for car %s: jump %.1f m in %.1f s (apparent speed %.1f km/h, sats: %d, hdop: %.2f)",
                    self._car_id,
                    dist,
                    dt,
                    speed_kmh,
                    satellites,
                    hdop,
                )
                self._gps_spoofed = True
                return  # Keep self._filtered_lat and self._filtered_lon unchanged
            else:
                _LOGGER.info(
                    "Evolute GPS position accepted after %d consecutive cycles for car %s (recovery)",
                    self._consecutive_rejected,
                    self._car_id,
                )

        # Valid point
        self._filtered_lat = lat_float
        self._filtered_lon = lon_float
        self._last_valid_time = now
        self._consecutive_rejected = 0
        self._gps_spoofed = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._filter_current_coordinates()
        super()._handle_coordinator_update()

    @property
    def latitude(self) -> float | None:
        """Return filtered latitude value of the device."""
        return self._filtered_lat

    @property
    def longitude(self) -> float | None:
        """Return filtered longitude value of the device."""
        return self._filtered_lon

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
            and self._filtered_lat is not None
            and self._filtered_lon is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        data = self._car_data()
        attributes: dict[str, Any] = {}
        for key in ("course", "altitude", "satellites", "hdop", "speed"):
            if data.get(key) is not None:
                attributes[key] = data[key]
        attributes["gps_spoofed"] = self._gps_spoofed
        if self._consecutive_rejected > 0:
            attributes["gps_rejected_points"] = self._consecutive_rejected
        return attributes
