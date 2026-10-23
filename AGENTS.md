# AGENTS.md

Home Assistant custom integration (domain `idotmatrix`) for iDotMatrix BLE pixel displays (16x16, 32x32, 64x64),
installed through HACS. It is built on the library
[idotmatrix-api-client](https://github.com/markusressel/idotmatrix-api-client), which does all the protocol work. Keep
the protocol out of this repository, and add features to the library first if they need new commands.

## Setup and commands

- Python 3.14 (Home Assistant requires it), venv at `.venv`.
- Install: `uv venv --python 3.14 && uv pip install -r requirements_test.txt idotmatrix-api-client==0.2.0`. To work with
  a local checkout of the library use `-e ../idotmatrix-api-client` instead of the pinned release.
- Tests: `.venv/bin/python -m pytest -q` (or `uv run --no-sync python -m pytest -q`).
- CI (`.github/workflows`): `tests.yml` runs the tests, `validate.yml` runs hassfest and the HACS validation. All three
  have to pass. The HACS check also needs the repository description and topics on GitHub.

## Layout

```
custom_components/idotmatrix/
  __init__.py        setup and unload of a config entry, hand-over of the connection from the config flow
  config_flow.py     Bluetooth discovery (IDM-*), manual step, options flow (idle timeout)
  device.py          IDotMatrixDevice: wraps the library client, connects over the HA Bluetooth stack, idle timeout,
                     assumed state (DeviceState), clock and night mode helpers
  entity.py          base entity: device info, state restore
  light.py           main light (screen, brightness, color, effects) and the clock light
  switch.py select.py button.py number.py time.py text.py   the other entities
  services.py        entity services on the light (show_text, show_image, ...), services.yaml describes them
  const.py           constants, clock styles, modes
  translations/en.json, icons.json, services.yaml, brand/icon.png
tests/               pytest-homeassistant-custom-component, the library client is mocked (tests/conftest.py)
```

## How it works

- **Connection:** `IDotMatrixDevice` creates an `IDotMatrixClient` with `ble_device`, a `BleakTransport` whose
  `connector` is `bleak-retry-connector`'s `establish_connection` (this is what makes Bluetooth proxies work) and
  `install_signal_handlers=False` (Home Assistant handles signals). The library connects on demand when a command is sent.
  Never start a scanner, use `bluetooth.async_ble_device_from_address`.
- **Keep the connection open.** Every new connection makes the display play a big, bright animation. The default idle
  timeout is 0 (never close), the library heartbeat notices a dead link, and the config flow hands its connection to the
  entry (`PENDING_DEVICES`). Do not add code that disconnects or reconnects without a reason.
- **Assumed state.** The display reports nothing, so entities show what was sent last (`DeviceState`) and restore it with
  `RestoreEntity`. `DeviceState.mode` says what is shown (light, effect, clock, music, content). Entities that start
  something (clock style, music sync scene) are unknown while something else is shown, which makes it possible to choose
  the same option again.
- **Errors:** wrap library calls with `IDotMatrixDevice.call()`, which turns library errors into `HomeAssistantError`
  with a translated message and handles the idle timer.
- **One connection only:** the display accepts one Bluetooth connection (also the one of the phone app).

## Conventions

- Everything is `async`, never block the event loop (file access goes through the executor, the library already loads
  images in a thread).
- Every user-visible string is in `translations/en.json` (entity names, errors with `translation_key`, services, selector
  options). A new entity, action or error needs its translation, its icon in `icons.json` and, for actions, its entry in
  `services.yaml`. Hassfest checks this.
- Use the registry APIs of the Home Assistant version in `hacs.json`: `async_get_device_by_connection(connection,
  config_entry_id)` instead of the deprecated `async_get_device`.
- New actions are entity services of the light, registered in `services.py`. Local files must pass
  `hass.config.is_allowed_path`.
- 4-space indent, type hints, Google style docstrings like the rest of the code.
- Do not duplicate library logic. If something is missing there, change the library (a PR in its repository, then a release).

## Tests

- Test the integration through Home Assistant (`hass.services.async_call`, states, `MockConfigEntry`), the fixtures in
  `tests/conftest.py` mock the library client and the Bluetooth stack (`setup` is a configured display).
- Assert what is sent to the library (`client.clock.show.assert_awaited_once_with(...)`) and what Home Assistant shows.
- Tests must not need a display or Bluetooth.

## Library version and releases

- `manifest.json` pins the library (`idotmatrix-api-client==x.y.z`), and `requirements_test.txt`, the test workflow and
  the README mention the same version. Update all of them together when the library changes. The pinned version has to be
  on PyPI before a release of the integration can be installed.
- HACS needs no releases (it follows the latest commit of the default branch). If you create a release, its tag has to
  match `version` in `manifest.json`.

## Boundaries

- Ask before changing entity unique ids (`<address>_<key>`), the domain, or the config entry data, because users
  depend on them (add a config entry migration when you must).
- Do not commit `.venv/` or `.idea/`.
- Never put the Claude Code session link into pull requests, issues, comments or commit messages.
