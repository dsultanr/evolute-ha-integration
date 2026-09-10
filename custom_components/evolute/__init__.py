"""The Evolute integration."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import EvoluteClient
from .const import (
    CARD_URL,
    CARD_VERSION,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from .coordinator import EvoluteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
]


async def _setup_www_files(hass: HomeAssistant) -> None:
    """Copy the bundled card resources (SVGs + hold button) into <config>/www/evolute/."""
    try:
        source_dir = Path(__file__).parent / "www" / "evolute"
        dest_dir = Path(hass.config.path("www")) / "evolute"

        if not source_dir.exists():
            return

        def _copy_files() -> int:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_dir.chmod(0o755)
            count = 0
            for pattern in ("*.svg", "*.js"):
                for file in source_dir.glob(pattern):
                    dest_file = dest_dir / file.name
                    shutil.copy2(file, dest_file)
                    dest_file.chmod(0o644)
                    count += 1
            return count

        copied = await hass.async_add_executor_job(_copy_files)
        if copied:
            _LOGGER.info("Installed %d file(s) to www/evolute/", copied)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Failed to set up www/evolute/ files: %s", err)


async def _register_card_resource(hass: HomeAssistant) -> None:
    """Register the hold-button card as a Lovelace resource, if HA allows it.

    Storage-mode dashboards let an integration add its own resource, which is what
    makes the card work without the user editing anything. YAML-mode dashboards keep
    resources read-only, so there we just log the URL to add by hand.
    """
    versioned_url = f"{CARD_URL}?v={CARD_VERSION}"
    try:
        lovelace = hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None)
        if resources is None and isinstance(lovelace, dict):
            resources = lovelace.get("resources")
        if resources is None:
            return

        if not getattr(resources, "loaded", True):
            await resources.async_load()
            resources.loaded = True

        for item in resources.async_items() or []:
            url = item.get("url", "")
            if url.split("?")[0] != CARD_URL:
                continue
            if url != versioned_url:
                await resources.async_update_item(item["id"], {"url": versioned_url})
                _LOGGER.info("Updated Lovelace resource %s", versioned_url)
            return

        await resources.async_create_item({"res_type": "module", "url": versioned_url})
        _LOGGER.info("Registered Lovelace resource %s", versioned_url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.info(
            "Could not register the Evolute card resource automatically (%s). "
            "Add it manually: %s as a JavaScript module",
            err,
            versioned_url,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Evolute from a config entry."""
    await _setup_www_files(hass)
    await _register_card_resource(hass)

    session = async_get_clientsession(hass)

    def _persist_tokens(access_token: str, refresh_token: str) -> None:
        """Persist rotated tokens so a HA restart doesn't require re-pasting them."""
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: refresh_token,
            },
        )

    client = EvoluteClient(
        session,
        entry.data[CONF_ACCESS_TOKEN],
        entry.data[CONF_REFRESH_TOKEN],
        tokens_updated_callback=_persist_tokens,
    )

    cars = await client.async_get_cars()
    if cars is None:
        # Access token may simply have expired since the entry was created; try once.
        if not await client.async_refresh_tokens():
            raise ConfigEntryAuthFailed("Could not authenticate with Evolute")
        cars = await client.async_get_cars()
        if cars is None:
            raise ConfigEntryAuthFailed("Could not authenticate with Evolute")

    coordinator = EvoluteDataUpdateCoordinator(hass, client, cars)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
