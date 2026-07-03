"""Evolute (app.evassist.ru) API client for Home Assistant."""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from typing import Any, Callable, Optional

import aiohttp

from homeassistant.util import dt as dt_util

from .const import BASE_URL, CAR_SEARCH_URL, COOKIE_ACCESS, COOKIE_REFRESH, REFRESH_URL

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


def _parse_car_info(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten the /car-service/tbox/{car_id}/info response for entity consumption."""
    sensors = raw.get("sensors") or {}
    sensors_data = sensors.get("sensorsData") or {}
    position = sensors.get("positionData") or {}
    prep = raw.get("preparation_script") or {}

    last_online = None
    last_online_raw = raw.get("lastOnlineTime")
    if last_online_raw not in (None, ""):
        try:
            last_online = dt_util.utc_from_timestamp(int(last_online_raw))
        except (ValueError, TypeError):
            last_online = None

    is_parked = bool(raw.get("isParked"))

    return {
        "battery_voltage": sensors_data.get("12VBatteryVoltage"),
        "odometer": sensors_data.get("odometer"),
        "battery_percentage": sensors_data.get("batteryPercentage"),
        "remains_mileage": sensors_data.get("remainsMileage"),
        "ignition": sensors_data.get("ignitionStatus"),
        "fuel_percentage": sensors_data.get("fuelPercentage"),
        "remains_mileage_fuel": sensors_data.get("remainsMileageFuel"),
        "central_lock": sensors_data.get("centralLockingStatus"),
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
        "prep_running": bool(prep.get("running")),
        "prep_available": bool(prep.get("available")),
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

    async def async_get_cars(self) -> list[dict[str, Any]] | None:
        """Return the list of cars for this account, or None on auth failure."""
        body = {
            "limit": 50,
            "offset": 0,
            "addSensors": False,
            "filters": [],
            "includeMaintenance": False,
        }
        result = await self._request("POST", CAR_SEARCH_URL, json_body=body)
        if result is None:
            return None

        cars = []
        for row in result.get("rows", []):
            model = row.get("carModel") or {}
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
                    "name": row.get("vin") or model.get("name") or car_id,
                }
            )
        return cars

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
