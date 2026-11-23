# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-11-23

### Added

- Integration: the media player has a new `integration_version` attribute (the running
  integration's version, as used for the card resource `?v=`), so the card can tell a stale
  browser tab from a pending restart.
- Tests: release guard that `manifest.json`, `card/package.json`, `CARD_VERSION` and the built
  bundle carry the same version; tests for the Lovelace resource update `?v=<old>` -> `?v=<new>`.
- README: troubleshooting entry for an outdated or blank card after an update.
- Card: a slim notice when the loaded card and the running integration are different versions:
  "A newer version of this card is installed. Reload the page." with a Reload button, or
  "Restart Home Assistant to finish the update." It can be hidden for the browser session (until
  the next version pair), never shows in the card editor preview and does not block the controls.

### Fixed

- Card: in a sections view the card now fills its whole section by default instead of half of
  it, and cannot be resized narrower than about 9 of 12 columns; the Wide layout takes the full
  section.
- Card: narrow cards (down to about 195 px) no longer squeeze: the off / asleep / failed banner
  puts its button on its own full-width row, the TV name wraps instead of being cut, the
  navigation keys use two rows, the D-pad / touchpad switch shows icons only, and the media keys
  and volume row fit without overflowing.

## [0.1.1] - 2026-11-23

### Fixed

- Card: blank editor preview and an empty section on sections dashboards. Home Assistant assigns
  a `layout` property to every card, which clashed with a read-only property of the card.
- Card: two-letter initials no longer overflow the small app icons.

### Changed

- Card: a rendering error now shows a visible message inside the card instead of an empty space.
- Card: fills the available height in panel views.

## [0.1.0] - 2026-11-23

### Added

- Self-sufficient Android TV integration: talks to the TV over ADB (`adb-shell` >= 0.4.4) and the
  Android TV Remote protocol v2 (`androidtvremote2` >= 0.3.3; minimum versions, so they follow
  the versions Home Assistant core ships; tested with 0.4.4 and 0.3.3); no dependency on the core `androidtv`
  or `androidtv_remote` integrations.
- Config flow: ADB connection with a clear prompt for the "Allow USB debugging" dialog, remote
  protocol pairing with the on-screen code (or ADB only), optional wake entity and wake timing.
- Options flow: wake settings, external volume entity, poll interval, hiding system apps and
  per-app label / icon URL / visibility overrides. Reauth flow for lost ADB or remote credentials.
- `media_player` entity (`off` / `idle` / `playing` / `paused` / `on`) with the attributes the card
  needs (`power_state`, `wake_state`, `app_id`, connection flags, ...), and a `remote` entity.
- Turn on from any state, including deep standby through a wake entity chosen in the UI: a
  `button`, `input_button`, `switch`, `input_boolean`, `script` or `scene` (for example an
  ESP32 BLE wake device), with re-press interval, timeout and a shared in-flight wake. The wake
  forms link to the ESP32 guide and firmware.
- Key routing: remote protocol first, ADB `input keyevent` fallback; long press and press-and-hold
  auto-repeat.
- App discovery over ADB with a bundled catalogue of common Android TV apps (labels, brand colours,
  icons) and fallbacks.
- Services `send_key`, `send_text`, `launch_app`, `open_url`, `adb_command` (with response) and
  `refresh_apps`.
- Websocket API for the card (`apps`, `send_key`, `send_text`, `launch_app`, `open_url`,
  `screenshot_url`) and an authenticated, rate-limited screenshot endpoint.
- Automatic registration of the dashboard card as a Lovelace resource.
- Installable from the Home Assistant Marketplace (2026.11+, "Add from link") or HACS
  (2026.10 and older); manifest `categories` set for the catalog.
- Diagnostics, English and Ukrainian translations.
- Integration icon in `custom_components/android_tv_pilot/brand/` (light and dark, 1x and 2x;
  SVG sources in `docs/brand/`).
- Marketplace / HACS catalog validation (`hacs/action`) and hassfest, tests (ruff, pytest with the Home Assistant harness, card
  typecheck/test/build with a bundle-up-to-date check), Dependabot and issue templates.

### Security

- `adb_command` (raw shell on the TV) is an admin-only service.
