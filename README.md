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
| Close the connection after | 0 (never) | Every new Bluetooth connection makes the display play a big, bright animation, so the connection is **kept open**. Set a number of seconds to close it after that much idle time, which frees the display for the iDotMatrix app and the connection slot of a Bluetooth proxy, at the price of the animation with the next command. |

## Entities

The display does not report its state, so the state of the entities is assumed (the last thing that was sent) and restored after a restart. Home Assistant would show two lightning buttons instead of a toggle for entities that are marked as "assumed", so they are shown as normal toggles.

| Entity | What it does |
|---|---|
| Light | Turns the screen on and off, sets the brightness (5-100 %), shows a color on the whole screen and shows effects (rainbows, random pixels, the clock). |
| Light *Clock* | Turning it on shows the clock (again, if it is shown already). Its color is the color of the clock, which is what the clock style *Color* displays. It is on while the clock is shown. Turning it off turns the screen off, because the display has no state "no clock". |
| Select *Clock style* | Shows the clock in one of 8 styles. The select is unknown while something else is shown, so the same style can be chosen again to get the clock back. |
| Switch *Clock shows date* | Off shows the time only, on lets the clock alternate between time and date. |
| Switch *Clock 24 hour format* | 24 or 12 hours. |
| Button *Show clock* | Shows the clock with the current settings, in one command. |
| Switch *Night mode enabled*, Time *Night mode start* / *end*, Number *Night mode brightness* | Dims the display between the two times. Changing any of them sends all four settings to the display. |
| Select *Music sync scene* | Lets the display react to sound with its own microphone (scenes 1-5). Show something else to leave it. Unknown while something else is shown. |
| Switch *Flip display* | Rotates the picture by 180 degrees. |
| Text *Message* | Shows the text as scrolling text. Use the `show_text` action for colors and modes. |
| Button *Sync time* | Sets the clock of the display to the time of Home Assistant. This also happens on every connection. |
| Button *Restart* | Resets the display. |
| Button *Freeze or unfreeze* | Freezes the picture (it toggles). |

The clock settings (style, date, 24 hours, color) change the display immediately if the clock is shown. Otherwise they are
kept and used the next time the clock is shown.

## Actions

All actions target the light of a display.

| Action | Purpose |
|---|---|
| `idotmatrix.show_text` | Text with font size, mode (marquee, blinking, ...), speed and colors. |
| `idotmatrix.show_image` | A picture from a file, an URL or a media source, scaled to the screen (`fit`, `fill`, `stretch`). |
| `idotmatrix.show_gif` | An animated GIF from a file, an URL or a media source. |
| `idotmatrix.start_slideshow` | The pictures of a folder (a folder of the file system or of a media source) one after another. The folder is read again every round, `recursive: true` includes its subfolders, `store: true` stores the pictures in the slots of the display instead (see below). Showing anything else ends it. |
| `idotmatrix.stop_slideshow` | Ends the slideshow. |
| `idotmatrix.show_clock` | The clock. Style, date, 12/24 hours and color that are not given are taken from the clock entities. |
| `idotmatrix.set_effect` | An effect with 2 to 7 colors. |
| `idotmatrix.countdown` | Starts, pauses, restarts or stops the countdown. |
| `idotmatrix.chronograph` | Starts, pauses, resumes or resets the stopwatch. |
| `idotmatrix.scoreboard` | Two scores, 0 to 999. |
| `idotmatrix.set_pixels` | Colors single pixels. |
| `idotmatrix.set_eco` | The night mode: dims the display between two times. Updates the night mode entities. |
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

`show_image`, `show_gif` and `start_slideshow` can draw a text on top of the picture (`overlay_text`, with
`overlay_position`, `overlay_color`, `overlay_font_size` and `overlay_background`), f.e. a title. The text does not
change while the picture is shown, and one that is too long for the screen is cut.

```yaml
action: idotmatrix.show_image
target:
  entity_id: light.idm_123456
data:
  url: "/api/media_player_proxy/media_player.living_room"
  overlay_text: "Now playing"
  overlay_position: bottom-center
```

```yaml
action: idotmatrix.start_slideshow
target:
  entity_id: light.idm_123456
data:
  media_content_id: "media-source://media_source/local/party"
  interval: 20
  shuffle: true
  recursive: true  # also the subfolders
```

With `store: true` the pictures are not uploaded one after another while the slideshow runs: they are stored in the
slots of the display (it has 12), which then cycles through them by itself, in the order of the slots. The animation
is never interrupted by an upload and Bluetooth is not used afterwards, but the upload takes a while (about 2 s for a
small GIF, up to 15 s for a large one, for each picture), the folder is not read again and only as many pictures as
there are slots are stored. `interval` is the time each picture is shown. `slots` limits the slots that may be
overwritten (all 12 by default, the others are not touched):

```yaml
action: idotmatrix.start_slideshow
target:
  entity_id: light.idm_123456
data:
  media_content_id: "media-source://media_source/local/party"
  recursive: true
  store: true
  slots: ["0", "1", "2", "3", "4", "5"]
  interval: 30
```

An URL that starts with `/` is loaded from Home Assistant itself, which makes it possible to show the cover of a media
player: `url: "{{ state_attr('media_player.living_room', 'entity_picture') }}"`.

Local files have to be in a folder that is listed in
[`allowlist_external_dirs`](https://www.home-assistant.io/docs/configuration/basic/#allowlist_external_dirs).

## Good to know

- The display accepts **one** connection. While Home Assistant is connected, the iDotMatrix app cannot connect, and the other way round. Set the idle timeout in the options if you want to use the app now and then.
- Every new connection makes the display play an animation, which is why the connection is kept open (and checked once a minute, to notice a display that was unplugged). It is opened again with the next command after it was lost. Adding the display opens a single connection that the integration keeps.
- Images and GIFs take a second or two to upload.
- The state of the entities is assumed. If someone changes the display with the app or the remote, Home Assistant does not notice.

## Development

```sh
uv venv --python 3.14
uv pip install -r requirements_test.txt idotmatrix-api-client==0.3.0   # or -e ../idotmatrix-api-client
uv run --no-sync python -m pytest
```

The library does the protocol work, see its [documentation of the protocol](https://github.com/markusressel/idotmatrix-api-client/blob/main/docs/DEVICE-PROTOCOL.md).

## License

AGPL-3.0, see [LICENSE](LICENSE).
