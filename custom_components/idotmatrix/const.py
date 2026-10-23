"""Constants of the iDotMatrix integration."""

from idotmatrix.screensize import ScreenSize

DOMAIN = "idotmatrix"

CONF_SCREEN_SIZE = "screen_size"
CONF_IDLE_TIMEOUT = "idle_timeout"

# The device accepts one connection at a time (also the one of the official app), and Bluetooth proxies have a
# limited number of connection slots, so the connection is closed when it is not used for a while.
DEFAULT_IDLE_TIMEOUT = 60
MIN_IDLE_TIMEOUT = 5
MAX_IDLE_TIMEOUT = 3600

SCREEN_SIZES = {
    "16x16": ScreenSize.SIZE_16x16,
    "32x32": ScreenSize.SIZE_32x32,
    "64x64": ScreenSize.SIZE_64x64,
}

# The device reports its screen type when connecting, see DeviceInfo of the library. This is the model name.
MANUFACTURER = "iDotMatrix"

# the brightness range of the device in percent
MIN_BRIGHTNESS_PERCENT = 5
MAX_BRIGHTNESS_PERCENT = 100
