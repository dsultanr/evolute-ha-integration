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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evolute buttons based on a config entry."""
    coordinator: EvoluteDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for car in coordinator.cars:
        for button_key, (name, command, icon) in BUTTON_TYPES.items():
            entities.append(EvoluteButton(coordinator, car, button_key, name, command, icon))

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
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._car_id = car["car_id"]
        self._command = command

        self._attr_name = name
        self._attr_unique_id = f"evolute_{self._car_id}_{button_key}"
        self.entity_id = f"button.evolute_{self._car_id}_{button_key}"
        self._attr_icon = icon

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._car_id)},
            "name": car.get("name") or f"Evolute {self._car_id}",
            "manufacturer": "Evolute",
            "model": car.get("model"),
            "suggested_area": "Garage",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Sending command %s to car %s", self._command, self._car_id)

        success = await self.coordinator.client.async_send_command(self._car_id, self._command)
        if not success:
            raise HomeAssistantError(
                f"Evolute command '{self._command}' failed. Check that the vehicle is "
                "online and try again."
            )

        # The command's physical effect can take several seconds; request a
        # fresh poll so entities reflect the new state a little sooner.
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return bool(self.coordinator.data) and self._car_id in self.coordinator.data
