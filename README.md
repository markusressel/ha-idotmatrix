# iDotMatrix for Home Assistant

A [Home Assistant](https://www.home-assistant.io) integration for [iDotMatrix](https://github.com/markusressel/idotmatrix-api-client) pixel displays (16x16, 32x32, 64x64), built on the
[idotmatrix-api-client](https://github.com/markusressel/idotmatrix-api-client) library.

- **Set up from the UI**: displays are discovered automatically (Bluetooth name `IDM-*`) and offered in the integrations page.
- **Bluetooth proxies**: connects through any Bluetooth adapter or [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html) that Home Assistant has, so the display does not have to be near your server.
- **Entities** for the things you want on a dashboard, **actions** for everything else (text, images, GIFs, ...).

> **Status:** new, and tested on a 64x64 only. The 16x16 and 32x32 support is based on the protocol of the official app.

## Installation

### HACS (custom repository)

1. In HACS open the menu, choose *Custom repositories* and add `https://github.com/markusressel/ha-idotmatrix` as an *Integration*.
2. Download *iDotMatrix*, then restart Home Assistant.

### Manual

Copy `custom_components/idotmatrix` into the `custom_components` folder of your Home Assistant configuration and restart.

## Setup

Power the display on, make sure the iDotMatrix phone app is **not** connected to it (the display accepts one Bluetooth connection at a time), then open *Settings > Devices & services*. The display shows up as discovered. Confirm it, and Home Assistant connects once to find out the size of its screen.

If nothing is discovered, add the integration manually. It lists every display that a Bluetooth adapter or proxy can see.

### Options

| Option | Default | |
|---|---|---|
| Close the connection after | 60 s | The display accepts one connection at a time and a Bluetooth proxy has few connection slots, so the connection is closed after it was not used for a while and opened again with the next command. |

## Entities

The display does not report its state, so the state of the entities is assumed (the last thing that was sent) and restored after a restart.

| Entity | What it does |
|---|---|
| Light | Turns the screen on and off, sets the brightness (5-100 %), shows a color on the whole screen and shows effects (rainbows, random pixels, the clock). |
| Switch *Flip display* | Rotates the picture by 180 degrees. |
| Select *Clock style* | Shows the clock in one of 8 styles. |
| Select *Music sync scene* | Lets the display react to sound with its own microphone (scenes 1-5). Show something else to leave it. |
| Text *Message* | Shows the text as scrolling text. Use the `show_text` action for colors and modes. |
| Button *Sync time* | Sets the clock of the display to the time of Home Assistant. This also happens on every connection. |
| Button *Restart* | Resets the display. |
| Button *Freeze or unfreeze* | Freezes the picture (it toggles). |

## Actions

All actions target the light of a display.

| Action | Purpose |
|---|---|
| `idotmatrix.show_text` | Text with font size, mode (marquee, blinking, ...), speed and colors. |
| `idotmatrix.show_image` | A picture from a file or an URL, scaled to the screen (`fit`, `fill`, `stretch`). |
| `idotmatrix.show_gif` | An animated GIF from a file or an URL. |
| `idotmatrix.show_clock` | The clock with style, date, 12/24 hours and color. |
| `idotmatrix.set_effect` | An effect with 2 to 7 colors. |
| `idotmatrix.countdown` | Starts, pauses, restarts or stops the countdown. |
| `idotmatrix.chronograph` | Starts, pauses, resumes or resets the stopwatch. |
| `idotmatrix.scoreboard` | Two scores, 0 to 999. |
| `idotmatrix.set_pixels` | Colors single pixels. |
| `idotmatrix.set_eco` | Dims the display between two times. |
| `idotmatrix.music_sync` | Music sync with the microphone of the display and its sensitivity. |

```yaml
action: idotmatrix.show_text
target:
  entity_id: light.idm_123456
data:
  text: "Dinner is ready"
  mode: marquee
  color_mode: rgb
  color: [255, 160, 0]
```

```yaml
action: idotmatrix.show_image
target:
  entity_id: light.idm_123456
data:
  url: "https://example.com/camera/snapshot.jpg"
  resize_mode: fill
```

Local files have to be in a folder that is listed in
[`allowlist_external_dirs`](https://www.home-assistant.io/docs/configuration/basic/#allowlist_external_dirs).

## Good to know

- The display accepts **one** connection. If the iDotMatrix app is connected, Home Assistant cannot connect, and the other way round. The integration closes its connection when idle.
- Images and GIFs take a second or two to upload.
- The state of the entities is assumed. If someone changes the display with the app or the remote, Home Assistant does not notice.

## Development

```sh
uv venv --python 3.14
uv pip install -r requirements_test.txt -e ../idotmatrix-api-client   # or the released library
uv run --no-sync python -m pytest
```

The library does the protocol work, see its [documentation of the protocol](https://github.com/markusressel/idotmatrix-api-client/blob/main/docs/DEVICE-PROTOCOL.md).

## License

AGPL-3.0, see [LICENSE](LICENSE).
