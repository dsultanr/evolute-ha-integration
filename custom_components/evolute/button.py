"""Button platform for Evolute."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BUTTON_TYPES, DOMAIN
from .coordinator import EvoluteDataUpdateCoordinator
from .entity import build_device_info

_LOGGER = logging.getLogger(__name__)

PENDING_ICON = "mdi:timer-sand"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evolute buttons based on a config entry."""
    coordinator: EvoluteDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for car in coordinator.cars:
        for button_key, (name, command, icon, confirm_key) in BUTTON_TYPES.items():
            entities.append(
                EvoluteButton(coordinator, car, button_key, name, command, icon, confirm_key)
            )

    async_add_entities(entities)


class EvoluteButton(CoordinatorEntity, ButtonEntity):
    """Representation of an Evolute command button."""

    def __init__(
        self,
        coordinator: EvoluteDataUpdateCoordinator,
        car: dict[str, Any],
        button_key: str,
        name: str,
        command: str,
        icon: str,
        confirm_key: str | None,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._car_id = car["car_id"]
        self._command = command
        self._confirm_key = confirm_key
        self._idle_icon = icon

        self._attr_name = name
        self._attr_unique_id = f"evolute_{self._car_id}_{button_key}"
        self.entity_id = f"button.evolute_{self._car_id}_{button_key}"
        self._attr_device_info = build_device_info(car)

    @property
    def _pending(self) -> bool:
        return self.coordinator.is_command_pending(self._car_id, self._command)

    @property
    def icon(self) -> str:
        """Swap in an hourglass while the car has not confirmed the command."""
        return PENDING_ICON if self._pending else self._idle_icon

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.coordinator.is_command_blocked(self._car_id, self._command):
            raise HomeAssistantError(
                f"Evolute command '{self._command}' is currently blocked by the vehicle."
            )

        _LOGGER.info("Sending command %s to car %s", self._command, self._car_id)

        success = await self.coordinator.async_send_command(
            self._car_id, self._command, self._confirm_key
        )
        if not success:
            raise HomeAssistantError(
                f"Evolute command '{self._command}' failed. Check that the vehicle is "
                "online and try again."
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data or self._car_id not in self.coordinator.data:
            return False
        return not self.coordinator.is_command_blocked(self._car_id, self._command)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose command status so a card can render hold/confirm feedback."""
        attributes: dict[str, Any] = {
            "command": self._command,
            "pending": self._pending,
            "blocked": self.coordinator.is_command_blocked(self._car_id, self._command),
        }
        if self._confirm_key:
            attributes["confirm_key"] = self._confirm_key
        return attributes
