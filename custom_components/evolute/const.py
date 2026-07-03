"""Constants for the Evolute integration."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

DOMAIN = "evolute"

CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"

PLATFORMS = ["sensor", "binary_sensor", "button", "device_tracker"]

BASE_URL = "https://app.evassist.ru"
REFRESH_URL = f"{BASE_URL}/id-service/auth/refresh-token"
CAR_SEARCH_URL = f"{BASE_URL}/car-service/car/v2/search"

COOKIE_ACCESS = "evy-platform-access"
COOKIE_REFRESH = "evy-platform-refresh"

UPDATE_INTERVAL_SECONDS = 30

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
}

# Button definitions: (name, command, icon)
# Commands map 1:1 to POST /car-service/tbox/{car_id}/{command}
BUTTON_TYPES = {
    "central_lock_toggle": ("Toggle Central Lock", "centralLockingToggle", "mdi:lock-outline"),
    "heating_toggle": ("Toggle Heating", "heating", "mdi:radiator"),
    "cooling_toggle": ("Toggle Cooling", "cooling", "mdi:snowflake"),
    "trunk_toggle": ("Toggle Trunk", "trunkToggle", "mdi:car-back"),
    "blink": ("Blink & Honk", "blink", "mdi:bullhorn"),
    "prepare_start": ("Start Trip Preparation", "PREPARE", "mdi:car-clock"),
    # CANCEL is not confirmed in captured traffic (PREPARE was never triggered
    # during capture); included by analogy with PREPARE, may not work on all accounts.
    "prepare_cancel": ("Cancel Trip Preparation", "CANCEL", "mdi:car-clock"),
}
