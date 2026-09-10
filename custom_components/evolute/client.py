"""Evolute (app.evassist.ru) API client for Home Assistant."""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from typing import Any, Callable, Optional

import aiohttp

from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    CAR_SEARCH_URL,
    COOKIE_ACCESS,
    COOKIE_REFRESH,
    DISABLED_COMMANDS_KEY,
    REFRESH_URL,
)

_LOGGER = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode a JWT payload without verifying the signature."""
    try:
        payload_b64 = token.split(".")[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload = base64.urlsafe_b64decode(payload_b64 + padding)
        return json.loads(payload)
    except Exception:  # noqa: BLE001
        return {}


def _local_utc_offset_hours() -> int:
    """Return the current UTC offset of the host, in whole hours."""
    offset = datetime.now().astimezone().utcoffset()
    if offset is None:
        return 0
    return int(offset.total_seconds() // 3600)


def _parse_iso_timestamp(raw: Any) -> Any:
    """Parse an ISO-8601 string from the API into an aware datetime, or None."""
    if raw in (None, ""):
        return None
    return dt_util.parse_datetime(str(raw))


def _parse_epoch_ms(raw: Any) -> Any:
    """Parse a millisecond epoch (the API sends it as a string) into a datetime."""
    if raw in (None, ""):
        return None
    try:
        return dt_util.utc_from_timestamp(int(raw) / 1000)
    except (ValueError, TypeError):
        return None


def _parse_car_info(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten the /car-service/tbox/{car_id}/info response for entity consumption."""
    sensors = raw.get("sensors") or {}
    sensors_data = sensors.get("sensorsData") or {}
    position = sensors.get("positionData") or {}
    prep = raw.get("preparation_script") or {}
    chip = sensors.get("chip") or {}
    warnings = raw.get("warnings") or []

    last_online = None
    last_online_raw = raw.get("lastOnlineTime")
    if last_online_raw not in (None, ""):
        try:
            last_online = dt_util.utc_from_timestamp(int(last_online_raw))
        except (ValueError, TypeError):
            last_online = None

    telemetry_time = None
    telemetry_time_raw = sensors.get("time")
    if telemetry_time_raw not in (None, ""):
        try:
            telemetry_time = dt_util.utc_from_timestamp(int(telemetry_time_raw))
        except (ValueError, TypeError):
            telemetry_time = None

    is_parked = bool(raw.get("isParked"))

    # The API reports centralLockingStatus as 1 = locked / 0 = unlocked, while HA's
    # LOCK binary sensor device class is inverted ("on" means unlocked), so flip it
    # here to keep the entity showing Locked when the car is actually locked.
    central_locking = sensors_data.get("centralLockingStatus")
    central_lock_open = None if central_locking is None else not central_locking

    # The remote-control buttons carry the only server-side feedback for heating and
    # cooling: sensorsData has no field for either, but buttons.main[] reports the
    # toggle state the app renders, plus whether the command is currently accepted.
    buttons = raw.get("buttons") or {}
    button_rows: list[dict[str, Any]] = []
    for group in ("main", "climate"):
        rows = buttons.get(group)
        if isinstance(rows, list):
            button_rows.extend(row for row in rows if isinstance(row, dict))
    by_command = {row["command"]: row for row in button_rows if row.get("command")}

    def _button_state(command: str) -> bool | None:
        row = by_command.get(command)
        if row is None:
            return None
        return row.get("state")

    return {
        "battery_voltage": sensors_data.get("12VBatteryVoltage"),
        "odometer": sensors_data.get("odometer"),
        "battery_percentage": sensors_data.get("batteryPercentage"),
        "remains_mileage": sensors_data.get("remainsMileage"),
        "ignition": sensors_data.get("ignitionStatus"),
        "fuel_percentage": sensors_data.get("fuelPercentage"),
        "remains_mileage_fuel": sensors_data.get("remainsMileageFuel"),
        "central_lock": central_lock_open,
        "door_fl": sensors_data.get("doorFLStatus"),
        "door_fr": sensors_data.get("doorFRStatus"),
        "door_rl": sensors_data.get("doorRLStatus"),
        "door_rr": sensors_data.get("doorRRStatus"),
        "trunk": sensors_data.get("trunkStatus"),
        "headlights": sensors_data.get("headLightsStatus"),
        "battery_temp": sensors_data.get("batteryTemp"),
        "coolant_temp": sensors_data.get("coolantTemp"),
        "climate_current_temp": sensors_data.get("climateCurentTemp"),
        "climate_target_temp": sensors_data.get("climateTargetTemp"),
        "climate_fan_speed": sensors_data.get("climateFanSpeed"),
        "inboard_temp": sensors_data.get("inBoardTemp"),
        "outside_temp": sensors_data.get("outsideTemp"),
        "climate_status": sensors_data.get("climateStatus"),
        "climate_front_window": sensors_data.get("climateFWindowStatus"),
        "latitude": position.get("lat"),
        "longitude": position.get("lon"),
        "speed": position.get("speed"),
        "course": position.get("course"),
        "altitude": position.get("height"),
        "satellites": position.get("sats"),
        "hdop": position.get("hdop"),
        "is_online": bool(raw.get("isOnline")),
        "is_parked": is_parked,
        "is_moving": not is_parked,
        "last_online": last_online,
        "telemetry_time": telemetry_time,
        "status_text": chip.get("title"),
        "heating": _button_state("heating"),
        "cooling": _button_state("cooling"),
        "warnings_count": len(warnings),
        "has_warnings": bool(warnings),
        "prep_running": bool(prep.get("running")),
        "prep_available": bool(prep.get("available")),
        "prep_disabled": bool(prep.get("disabled")),
        "prep_error": bool(prep.get("errorStatus")),
        "prep_end_time": prep.get("endTime"),
        "prep_start_time": _parse_epoch_ms(prep.get("startTime")),
        # Not an entity state: consumed by the button platform to grey out a
        # command the backend is currently refusing.
        DISABLED_COMMANDS_KEY: {
            command for command, row in by_command.items() if row.get("disabled")
        },
    }


def _parse_car_details(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten the slow-moving fields of a /car/v2/search row (service, OTA, ...)."""
    maintenance = row.get("maintenance") or {}
    meta = maintenance.get("meta") or {}
    next_service = maintenance.get("next") or {}

    return {
        "maintenance_status": maintenance.get("status"),
        "maintenance_days_left": meta.get("daysLeft"),
        "maintenance_km_left": meta.get("kmLeft"),
        "maintenance_date": _parse_iso_timestamp(next_service.get("date")),
        "maintenance_mileage": next_service.get("mileage"),
        "update_available": bool(row.get("updateAvailable")),
        "location_enabled": bool(row.get("locationStatus")),
        "prep_script_time": row.get("currentScriptTime"),
        "last_sensor_request": _parse_iso_timestamp(row.get("lastSensorRequest")),
        "last_command_trigger": _parse_iso_timestamp(row.get("lastCommandTrigger")),
    }


class EvoluteClient:
    """Client for the Evolute (app.evassist.ru) car API.

    Authentication uses two cookies (evy-platform-access / evy-platform-refresh)
    obtained by the user from their browser session, since the native sign-in
    flow requires solving a Yandex SmartCaptcha before an SMS code can be
    requested.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str,
        refresh_token: str,
        tokens_updated_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._tokens_updated_callback = tokens_updated_callback
        self.auth_failed = False
        self._etags: dict[str, str] = {}
        self._last_info: dict[str, dict[str, Any]] = {}

    @property
    def user_id(self) -> str | None:
        """Return the account id embedded in the current access token, if any."""
        payload = _decode_jwt_payload(self.access_token)
        return payload.get("_id") or payload.get("userId")

    def _cookies(self) -> dict[str, str]:
        return {
            COOKIE_ACCESS: self.access_token,
            COOKIE_REFRESH: self.refresh_token,
        }

    def _headers(self) -> dict[str, str]:
        return {
            "accept": "*/*",
            "content-type": "application/json",
            "user-agent": USER_AGENT,
            "x-app": "web",
            "time-zone": str(_local_utc_offset_hours()),
        }

    async def async_refresh_tokens(self) -> bool:
        """Refresh the access/refresh token pair. Returns False if unrecoverable."""
        try:
            async with self._session.post(
                REFRESH_URL,
                json={"refreshToken": self.refresh_token},
                headers={"content-type": "application/json", "user-agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    self.auth_failed = True
                    _LOGGER.error(
                        "Evolute token refresh rejected (HTTP %s) - refresh token likely expired",
                        resp.status,
                    )
                    return False
                if resp.status != 200:
                    _LOGGER.error("Evolute token refresh failed: HTTP %s", resp.status)
                    return False
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            _LOGGER.error("Evolute token refresh error: %s", err)
            return False

        access = data.get("accessToken")
        refresh = data.get("refreshToken") or self.refresh_token
        if not access:
            _LOGGER.error("Evolute token refresh response missing accessToken")
            return False

        self.access_token = access
        self.refresh_token = refresh
        self.auth_failed = False
        if self._tokens_updated_callback:
            self._tokens_updated_callback(self.access_token, self.refresh_token)
        return True

    async def _async_search_cars(self) -> list[dict[str, Any]] | None:
        """Return the raw /car/v2/search rows for this account, or None on failure."""
        body = {
            "limit": 50,
            "offset": 0,
            # Both flags cost nothing extra on the wire and carry the service /
            # OTA / tracking fields that the tbox info endpoint does not report.
            "addSensors": True,
            "filters": [],
            "includeMaintenance": True,
        }
        result = await self._request("POST", CAR_SEARCH_URL, json_body=body)
        if result is None:
            return None
        return [row for row in result.get("rows", []) if isinstance(row, dict)]

    async def async_get_cars(self) -> list[dict[str, Any]] | None:
        """Return the list of cars for this account, or None on auth failure."""
        rows = await self._async_search_cars()
        if rows is None:
            return None

        cars = []
        for row in rows:
            model = row.get("carModel") or {}
            images = row.get("images") or {}
            car_id = row.get("_id")
            if not car_id:
                continue
            cars.append(
                {
                    "car_id": car_id,
                    "vin": row.get("vin"),
                    "brand": row.get("brand") or "Evolute",
                    "model": model.get("name") or "Evolute",
                    "modification": model.get("modname"),
                    "model_year": model.get("modelYear"),
                    "color": model.get("color"),
                    "image": images.get("side"),
                    "name": row.get("vin") or model.get("name") or car_id,
                }
            )
        return cars

    async def async_get_car_details(self) -> dict[str, dict[str, Any]] | None:
        """Return slow-moving per-car data (service, OTA, tracking), keyed by car id."""
        rows = await self._async_search_cars()
        if rows is None:
            return None
        return {
            row["_id"]: _parse_car_details(row) for row in rows if row.get("_id")
        }

    async def async_get_car_info(self, car_id: str) -> dict[str, Any] | None:
        """Fetch and flatten telemetry for a single car. None on failure."""
        url = f"{BASE_URL}/car-service/tbox/{car_id}/info"

        for attempt in range(2):
            headers = self._headers()
            etag = self._etags.get(car_id)
            if etag:
                headers["if-none-match"] = etag

            try:
                async with self._session.get(
                    url,
                    headers=headers,
                    cookies=self._cookies(),
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status == 304:
                        return self._last_info.get(car_id)

                    if resp.status == 401 and attempt == 0:
                        if not await self.async_refresh_tokens():
                            return None
                        continue

                    if resp.status != 200:
                        _LOGGER.warning(
                            "Evolute tbox info request failed for %s: HTTP %s", car_id, resp.status
                        )
                        return None

                    new_etag = resp.headers.get("etag")
                    if new_etag:
                        self._etags[car_id] = new_etag

                    raw = await resp.json(content_type=None)
                    parsed = _parse_car_info(raw)
                    self._last_info[car_id] = parsed
                    return parsed
            except aiohttp.ClientError as err:
                _LOGGER.warning("Evolute tbox info request error for %s: %s", car_id, err)
                return None

        return None

    async def async_send_command(self, car_id: str, command: str) -> bool:
        """Send a remote command to the car (e.g. heating, cooling, blink)."""
        url = f"{BASE_URL}/car-service/tbox/{car_id}/{command}"
        result = await self._request("POST", url, json_body={})
        return result is not None

    async def _request(
        self, method: str, url: str, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        for attempt in range(2):
            try:
                async with self._session.request(
                    method,
                    url,
                    json=json_body,
                    headers=self._headers(),
                    cookies=self._cookies(),
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        if not await self.async_refresh_tokens():
                            return None
                        continue

                    if resp.status >= 400:
                        _LOGGER.warning("%s %s failed: HTTP %s", method, url, resp.status)
                        return None

                    try:
                        return await resp.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError, json.JSONDecodeError):
                        return {}
            except aiohttp.ClientError as err:
                _LOGGER.warning("%s %s error: %s", method, url, err)
                return None

        return None
