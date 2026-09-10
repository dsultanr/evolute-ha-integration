"""Shared entity helpers for the Evolute integration."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def build_device_info(car: dict[str, Any]) -> DeviceInfo:
    """Return the device registry entry shared by every entity of one car."""
    model = car.get("model")
    modification = car.get("modification")
    model_year = car.get("model_year")

    info: DeviceInfo = {
        "identifiers": {(DOMAIN, car["car_id"])},
        "name": car.get("name") or f"Evolute {car['car_id']}",
        "manufacturer": "Evolute",
        "model": model,
        "suggested_area": "Garage",
    }
    if modification:
        info["model_id"] = modification
    if car.get("vin"):
        info["serial_number"] = car["vin"]
    if model_year:
        info["hw_version"] = str(model_year)
    return info
