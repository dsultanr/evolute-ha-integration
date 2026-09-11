"""DataUpdateCoordinator for the Evolute integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import EvoluteClient
from .const import (
    COMMAND_PENDING_TIMEOUT_SECONDS,
    COMMAND_REFRESH_DELAYS,
    DETAILS_RETRY_INTERVAL_SECONDS,
    DETAILS_UPDATE_INTERVAL_SECONDS,
    DISABLED_COMMANDS_KEY,
    DOMAIN,
    UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class PendingCommand:
    """A command that was accepted by the API but not yet visible in telemetry."""

    confirm_key: str | None
    baseline: Any
    expires_at: float


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
        self._details: dict[str, dict[str, Any]] = {}
        self._details_next_fetch = 0.0
        self._pending: dict[str, dict[str, PendingCommand]] = {}
        self._burst_cancels: list[Any] = []

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Poll /car-service/tbox/{car_id}/info for every known car."""
        await self._async_update_details()

        data: dict[str, dict[str, Any]] = {}

        for car in self.cars:
            car_id = car["car_id"]
            info = await self.client.async_get_car_info(car_id)
            if info is not None:
                # Details are merged underneath so a stale slow poll can never mask
                # fresh telemetry with the same key.
                data[car_id] = {**self._details.get(car_id, {}), **info}

        if not data and self.cars:
            if self.client.auth_failed:
                raise ConfigEntryAuthFailed(
                    "Evolute session expired, please re-enter your access/refresh tokens"
                )
            raise UpdateFailed("Unable to reach Evolute (app.evassist.ru)")

        self._resolve_pending(data)
        return data

    async def _async_update_details(self) -> None:
        """Refresh the slow-moving /car/v2/search fields when they are due."""
        now = monotonic()
        if now < self._details_next_fetch:
            return

        details = await self.client.async_get_car_details()
        if details is None:
            # Back off briefly rather than retrying on every 30s telemetry poll.
            self._details_next_fetch = now + DETAILS_RETRY_INTERVAL_SECONDS
            return

        self._details = details
        self._details_next_fetch = now + DETAILS_UPDATE_INTERVAL_SECONDS

    # --- command dispatch -------------------------------------------------

    async def async_send_command(
        self, car_id: str, command: str, confirm_key: str | None
    ) -> bool:
        """Send a command and track it until the car confirms it in telemetry."""
        current = (self.data or {}).get(car_id, {})
        baseline = current.get(confirm_key) if confirm_key else None

        success = await self.client.async_send_command(car_id, command)
        if not success:
            return False

        # Only a command with an observable telemetry key is worth waiting for.
        # Blink changes nothing we can read, so it is done the moment the API
        # accepts it - marking it pending would just spin an indicator for
        # nothing and re-poll telemetry that cannot have changed.
        if confirm_key is None:
            return True

        self._pending.setdefault(car_id, {})[command] = PendingCommand(
            confirm_key=confirm_key,
            baseline=baseline,
            expires_at=monotonic() + COMMAND_PENDING_TIMEOUT_SECONDS,
        )
        self.async_update_listeners()
        self._schedule_command_refreshes()
        return True

    @callback
    def _schedule_command_refreshes(self) -> None:
        """Re-poll a few times after a command instead of waiting for the 30s tick."""
        self._cancel_command_refreshes()
        for delay in COMMAND_REFRESH_DELAYS:
            self._burst_cancels.append(
                async_call_later(self.hass, delay, self._async_burst_refresh)
            )

    @callback
    def _cancel_command_refreshes(self) -> None:
        for cancel in self._burst_cancels:
            cancel()
        self._burst_cancels.clear()

    async def _async_burst_refresh(self, _now: Any) -> None:
        await self.async_request_refresh()

    def _resolve_pending(self, data: dict[str, dict[str, Any]]) -> None:
        """Drop pending commands that the car has confirmed or that timed out."""
        now = monotonic()
        for car_id, commands in list(self._pending.items()):
            car_data = data.get(car_id, {})
            for command, pending in list(commands.items()):
                confirmed = (
                    pending.confirm_key is not None
                    and car_data.get(pending.confirm_key) != pending.baseline
                )
                if confirmed or now >= pending.expires_at:
                    del commands[command]
            if not commands:
                del self._pending[car_id]

        if not self._pending:
            self._cancel_command_refreshes()

    def is_command_pending(self, car_id: str, command: str) -> bool:
        """Return True while a sent command has not yet shown up in telemetry."""
        return command in self._pending.get(car_id, {})

    def is_command_blocked(self, car_id: str, command: str) -> bool:
        """Return True if the backend currently reports the command as disabled."""
        disabled = (self.data or {}).get(car_id, {}).get(DISABLED_COMMANDS_KEY)
        return bool(disabled) and command in disabled

    async def async_shutdown(self) -> None:
        """Cancel any scheduled post-command refreshes on unload."""
        self._cancel_command_refreshes()
        await super().async_shutdown()
