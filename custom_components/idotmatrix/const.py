"""Constants of the iDotMatrix integration."""

from idotmatrix.modules.clock import ClockStyle
from idotmatrix.screensize import ScreenSize

DOMAIN = "idotmatrix"

CONF_SCREEN_SIZE = "screen_size"
CONF_IDLE_TIMEOUT = "idle_timeout"

# Every new connection makes the display play a big, bright animation, so the connection is kept open by default
# (0). It can be closed after some idle time, which frees the display for the app of the manufacturer and the
# connection slot of a Bluetooth proxy.
# a display that was connected by the config flow is handed over to the entry that is created, so the connection is
# not closed and opened again (which would play the animation twice)
PENDING_DEVICES = "pending_devices"

DEFAULT_IDLE_TIMEOUT = 0
MIN_IDLE_TIMEOUT = 0
MAX_IDLE_TIMEOUT = 3600

# While the connection is kept open, a silent device is asked for a sign of life this often, so that a link that died
# without Bluetooth noticing (f.e. the display was unplugged) is found.
HEARTBEAT_INTERVAL = 60

# The pause between two uploads of pictures. The display takes them back to back, but a Bluetooth proxy that is still
# busy with the previous one lets the display miss the acknowledgement of a chunk (the upload fails after 5 seconds).
UPLOAD_PAUSE = 1.0

SCREEN_SIZES = {
    "16x16": ScreenSize.SIZE_16x16,
    "32x32": ScreenSize.SIZE_32x32,
    "64x64": ScreenSize.SIZE_64x64,
}

# The device reports its screen type when connecting, see DeviceInfo of the library. This is the model name.
MANUFACTURER = "iDotMatrix"

# what the display shows, as far as Home Assistant knows
MODE_LIGHT = "light"  # a color on the whole screen
MODE_EFFECT = "effect"
MODE_CLOCK = "clock"
MODE_MUSIC = "music"
MODE_CONTENT = "content"  # text, a picture, a GIF, a scoreboard, ...

CLOCK_STYLES = {
    "rgb_swipe_outline": ClockStyle.RGBSwipeOutline,
    "christmas_tree": ClockStyle.ChristmasTree,
    "checkers": ClockStyle.Checkers,
    "color": ClockStyle.Color,
    "hourglass": ClockStyle.Hourglass,
    "alarm_clock": ClockStyle.AlarmClock,
    "outlines": ClockStyle.Outlines,
    "rgb_corners": ClockStyle.RGBCorners,
}

# the brightness range of the device in percent
MIN_BRIGHTNESS_PERCENT = 5
MAX_BRIGHTNESS_PERCENT = 100
