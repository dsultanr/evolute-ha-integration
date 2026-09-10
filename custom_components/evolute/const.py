"""Constants for the Evolute integration."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

DOMAIN = "evolute"

# Bump together with manifest.json: it is the cache-buster on the Lovelace resource
# URL, so an old copy of the card is not served after an update.
CARD_VERSION = "1.3.0"
CARD_FILENAME = "evolute-hold-button.js"
CARD_URL = f"/local/evolute/{CARD_FILENAME}"

CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"

PLATFORMS = ["sensor", "binary_sensor", "button", "device_tracker"]

BASE_URL = "https://app.evassist.ru"
REFRESH_URL = f"{BASE_URL}/id-service/auth/refresh-token"
CAR_SEARCH_URL = f"{BASE_URL}/car-service/car/v2/search"

COOKIE_ACCESS = "evy-platform-access"
COOKIE_REFRESH = "evy-platform-refresh"

UPDATE_INTERVAL_SECONDS = 30

# The /car/v2/search fields (service schedule, OTA flag, tracking switch) change on
# a scale of days, so they get their own slow poll instead of riding the 30s loop.
DETAILS_UPDATE_INTERVAL_SECONDS = 15 * 60
DETAILS_RETRY_INTERVAL_SECONDS = 60

# A remote command takes seconds to reach the car and be reflected back in the
# telemetry, so a single refresh right after the press usually still reports the
# old state. Poll a few times on a decaying schedule instead.
COMMAND_REFRESH_DELAYS = (3, 8, 15, 25, 40)

# How long a button keeps reporting "a command is in flight" if the telemetry never
# confirms it. Long enough to cover COMMAND_REFRESH_DELAYS plus some slack.
COMMAND_PENDING_TIMEOUT_SECONDS = 60

# Key under which the coordinator stashes the set of commands the backend is
# currently refusing. Underscore-prefixed so it can never collide with a state key.
DISABLED_COMMANDS_KEY = "_disabled_commands"

# Sensor definitions: (name, unit, device_class, icon, state_key, state_class)
SENSOR_TYPES = {
    "battery_percentage": ("Battery", "%", SensorDeviceClass.BATTERY, "mdi:battery", "battery_percentage", SensorStateClass.MEASUREMENT),
    "remains_mileage": ("Remaining Range", "km", SensorDeviceClass.DISTANCE, "mdi:map-marker-distance", "remains_mileage", SensorStateClass.MEASUREMENT),
    "fuel_percentage": ("Fuel Level", "%", None, "mdi:gas-station", "fuel_percentage", SensorStateClass.MEASUREMENT),
    "remains_mileage_fuel": ("Remaining Range (Fuel)", "km", SensorDeviceClass.DISTANCE, "mdi:gas-station", "remains_mileage_fuel", SensorStateClass.MEASUREMENT),
    "battery_voltage": ("12V Battery Voltage", "V", SensorDeviceClass.VOLTAGE, "mdi:car-battery", "battery_voltage", SensorStateClass.MEASUREMENT),
    "odometer": ("Odometer", "km", SensorDeviceClass.DISTANCE, "mdi:counter", "odometer", SensorStateClass.TOTAL_INCREASING),
    "battery_temp": ("Battery Temperature", "°C", SensorDeviceClass.TEMPERATURE, "mdi:thermometer", "battery_temp", SensorStateClass.MEASUREMENT),
    "coolant_temp": ("Coolant Temperature", "°C", SensorDeviceClass.TEMPERATURE, "mdi:thermometer", "coolant_temp", SensorStateClass.MEASUREMENT),
    "inboard_temp": ("Cabin Temperature", "°C", SensorDeviceClass.TEMPERATURE, "mdi:thermometer", "inboard_temp", SensorStateClass.MEASUREMENT),
    "outside_temp": ("Outside Temperature", "°C", SensorDeviceClass.TEMPERATURE, "mdi:thermometer", "outside_temp", SensorStateClass.MEASUREMENT),
    "climate_current_temp": ("Climate Current Temperature", "°C", SensorDeviceClass.TEMPERATURE, "mdi:thermometer", "climate_current_temp", SensorStateClass.MEASUREMENT),
    "climate_target_temp": ("Climate Target Temperature", "°C", SensorDeviceClass.TEMPERATURE, "mdi:thermometer", "climate_target_temp", SensorStateClass.MEASUREMENT),
    "climate_fan_speed": ("Climate Fan Speed", None, None, "mdi:fan", "climate_fan_speed", SensorStateClass.MEASUREMENT),
    "speed": ("Speed", "km/h", SensorDeviceClass.SPEED, "mdi:speedometer", "speed", SensorStateClass.MEASUREMENT),
    "latitude": ("Latitude", "°", None, "mdi:map-marker", "latitude", SensorStateClass.MEASUREMENT),
    "longitude": ("Longitude", "°", None, "mdi:map-marker", "longitude", SensorStateClass.MEASUREMENT),
    "altitude": ("Altitude", "m", SensorDeviceClass.DISTANCE, "mdi:altimeter", "altitude", SensorStateClass.MEASUREMENT),
    "satellites": ("Satellites", None, None, "mdi:satellite-variant", "satellites", SensorStateClass.MEASUREMENT),
    "hdop": ("GPS HDOP", None, None, "mdi:signal", "hdop", SensorStateClass.MEASUREMENT),
    "course": ("Course", "°", None, "mdi:compass", "course", SensorStateClass.MEASUREMENT),
    "last_online": ("Last Online", None, SensorDeviceClass.TIMESTAMP, "mdi:clock-outline", "last_online", None),
    "telemetry_time": ("Telemetry Time", None, SensorDeviceClass.TIMESTAMP, "mdi:clock-check-outline", "telemetry_time", None),
    "status_text": ("Status", None, None, "mdi:information-outline", "status_text", None),
    "warnings_count": ("Warning Count", None, None, "mdi:alert-circle-outline", "warnings_count", SensorStateClass.MEASUREMENT),
    "prep_end_time": ("Trip Preparation Remaining", None, None, "mdi:timer-outline", "prep_end_time", None),
    "prep_start_time": ("Trip Preparation Started", None, SensorDeviceClass.TIMESTAMP, "mdi:clock-start", "prep_start_time", None),
    # Sourced from the slow /car/v2/search poll rather than tbox telemetry.
    "prep_script_time": ("Trip Preparation Duration", "min", SensorDeviceClass.DURATION, "mdi:timer-cog-outline", "prep_script_time", None),
    "maintenance_status": ("Service Status", None, None, "mdi:wrench-outline", "maintenance_status", None),
    "maintenance_days_left": ("Service Due In", "d", SensorDeviceClass.DURATION, "mdi:calendar-clock", "maintenance_days_left", SensorStateClass.MEASUREMENT),
    "maintenance_km_left": ("Service Due In (Distance)", "km", SensorDeviceClass.DISTANCE, "mdi:wrench-clock", "maintenance_km_left", SensorStateClass.MEASUREMENT),
    "maintenance_date": ("Service Due Date", None, SensorDeviceClass.TIMESTAMP, "mdi:calendar-wrench", "maintenance_date", None),
    "maintenance_mileage": ("Service Due Odometer", "km", SensorDeviceClass.DISTANCE, "mdi:counter", "maintenance_mileage", None),
    "last_sensor_request": ("Last Sensor Request", None, SensorDeviceClass.TIMESTAMP, "mdi:cloud-download-outline", "last_sensor_request", None),
    "last_command_trigger": ("Last Command Sent", None, SensorDeviceClass.TIMESTAMP, "mdi:remote", "last_command_trigger", None),
}

# Binary sensor definitions: (name, device_class, state_key)
BINARY_SENSOR_TYPES = {
    "ignition": ("Ignition", BinarySensorDeviceClass.RUNNING, "ignition"),
    "central_lock": ("Central Lock", BinarySensorDeviceClass.LOCK, "central_lock"),
    "door_fl": ("Driver Door", BinarySensorDeviceClass.DOOR, "door_fl"),
    "door_fr": ("Passenger Door", BinarySensorDeviceClass.DOOR, "door_fr"),
    "door_rl": ("Rear Left Door", BinarySensorDeviceClass.DOOR, "door_rl"),
    "door_rr": ("Rear Right Door", BinarySensorDeviceClass.DOOR, "door_rr"),
    "trunk": ("Trunk", BinarySensorDeviceClass.DOOR, "trunk"),
    "headlights": ("Headlights", BinarySensorDeviceClass.LIGHT, "headlights"),
    "climate": ("Climate", BinarySensorDeviceClass.RUNNING, "climate_status"),
    "climate_front_defrost": ("Front Defrost", BinarySensorDeviceClass.HEAT, "climate_front_window"),
    "online": ("Online", BinarySensorDeviceClass.CONNECTIVITY, "is_online"),
    "moving": ("Moving", BinarySensorDeviceClass.MOVING, "is_moving"),
    "preparing": ("Preparing For Trip", BinarySensorDeviceClass.RUNNING, "prep_running"),
    # heating / cooling have no sensorsData field; their only server-side feedback
    # is the toggle state the app renders in buttons.main[].
    "heating": ("Heating", BinarySensorDeviceClass.RUNNING, "heating"),
    "cooling": ("Cooling", BinarySensorDeviceClass.RUNNING, "cooling"),
    "prep_available": ("Trip Preparation Available", None, "prep_available"),
    "prep_disabled": ("Trip Preparation Blocked", BinarySensorDeviceClass.PROBLEM, "prep_disabled"),
    "prep_error": ("Trip Preparation Error", BinarySensorDeviceClass.PROBLEM, "prep_error"),
    "warnings": ("Warnings", BinarySensorDeviceClass.PROBLEM, "has_warnings"),
    # Sourced from the slow /car/v2/search poll rather than tbox telemetry.
    "update_available": ("Firmware Update Available", BinarySensorDeviceClass.UPDATE, "update_available"),
    "location_enabled": ("Location Reporting", None, "location_enabled"),
}

# Button definitions: (name, command, icon, confirm_key)
# Commands map 1:1 to POST /car-service/tbox/{car_id}/{command}.
# confirm_key names the telemetry key whose change confirms the command landed; it
# lets the button drop its "pending" flag as soon as the car reports back instead of
# waiting for the pending timeout. None means the command has no observable state.
BUTTON_TYPES = {
    "central_lock_toggle": ("Toggle Central Lock", "centralLockingToggle", "mdi:lock-outline", "central_lock"),
    "heating_toggle": ("Toggle Heating", "heating", "mdi:radiator", "heating"),
    "cooling_toggle": ("Toggle Cooling", "cooling", "mdi:snowflake", "cooling"),
    "trunk_toggle": ("Toggle Trunk", "trunkToggle", "mdi:car-back", "trunk"),
    "blink": ("Blink & Honk", "blink", "mdi:bullhorn", None),
    "prepare_start": ("Start Trip Preparation", "PREPARE", "mdi:car-clock", "prep_running"),
    # CANCEL is not confirmed in captured traffic (PREPARE was never triggered
    # during capture); included by analogy with PREPARE, may not work on all accounts.
    "prepare_cancel": ("Cancel Trip Preparation", "CANCEL", "mdi:car-clock", "prep_running"),
}
