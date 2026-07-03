"""DataUpdateCoordinator for the Evolute integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import EvoluteClient
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class EvoluteDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator polling telemetry for every car on the account."""

    def __init__(
        self, hass: HomeAssistant, client: EvoluteClient, cars: list[dict[str, Any]]
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self.cars = cars

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Poll /car-service/tbox/{car_id}/info for every known car."""
        data: dict[str, dict[str, Any]] = {}

        for car in self.cars:
            car_id = car["car_id"]
            info = await self.client.async_get_car_info(car_id)
            if info is not None:
                data[car_id] = info

        if not data and self.cars:
            if self.client.auth_failed:
                raise ConfigEntryAuthFailed(
                    "Evolute session expired, please re-enter your access/refresh tokens"
                )
            raise UpdateFailed("Unable to reach Evolute (app.evassist.ru)")

        return data
