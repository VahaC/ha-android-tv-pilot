# Android TV Pilot: integration API

This is the contract between the Python integration (`custom_components/android_tv_pilot`) and
the Lovelace card. Names here are fixed; the card and the integration are built against them.

Domain: `android_tv_pilot`.

## media_player entity

The card's `entity`. One per configured TV.

| State     | Meaning                                                                 |
|-----------|-------------------------------------------------------------------------|
| `off`     | Unreachable (deep standby), waking, or reachable with the screen off     |
| `idle`    | Screen on, home screen (launcher) in front                               |
| `playing` | The foreground app's media session is playing (also buffering, FF, RW)   |
| `paused`  | The foreground app's media session is paused                             |
| `on`      | Screen on, an app is in front without a playing/paused media session     |

The entity is never `unavailable` because the TV sleeps: `turn_on` must stay callable.

- `source`: label of the foreground app; `source_list`: labels of the visible (not hidden) apps.
- `select_source` accepts a label (case-insensitive) or a package name. An unknown label makes the
  integration reload the app list once (e.g. right after a cold start) before failing with
  `unknown_app` (websocket code `not_found`).
- Supported: `turn_on`, `turn_off`, `volume_set`, `volume_up`/`volume_down`, `volume_mute`,
  `media_play`, `media_pause`, `media_stop`, `media_next_track`, `media_previous_track`,
  `select_source`, `play_media`.
- `play_media`: `media_content_type: app` + `media_content_id: <package>` launches an app;
  `media_content_type: url` + `media_content_id: <url or deep link>` opens it.
- `volume_level` comes from the remote protocol when connected, else from ADB; each transport keeps
  its own scale. `volume_set` without an external entity uses ADB and the ADB STREAM_MUSIC maximum.
- When an external `volume_entity` is configured, volume up/down/mute/set are forwarded to it and
  `volume_level` / `is_volume_muted` are read from it.

### Extra state attributes

| Attribute          | Type                                        | Notes                                                    |
|--------------------|---------------------------------------------|----------------------------------------------------------|
| `entry_id`         | string                                      | Config entry id; pass it to every websocket command      |
| `power_state`      | `"off" \| "waking" \| "on" \| "asleep"`     | `asleep` = reachable over ADB/remote, screen off         |
| `wake_state`       | `"idle" \| "waking" \| "failed"`            | `waking` from the moment `turn_on` starts on a TV not known to be reachable (back to `idle` if the first probe finds it); `failed` until the next `turn_on` or until the TV becomes reachable by any path |
| `wake_started_at`  | ISO 8601 string or `null`                   | Set while `wake_state` is `waking`                       |
| `wake_timeout`     | number (seconds)                            | Configured wake timeout                                  |
| `app_id`           | string or `null`                            | Foreground package (null unless `power_state` is `on`)   |
| `app_name`         | string or `null`                            | Label of `app_id`                                        |
| `app_activity`     | string or `null`                            | Full activity class name when known (ADB)                |
| `adb_connected`    | bool                                        |                                                          |
| `remote_connected` | bool                                        | Remote protocol (androidtvremote2)                       |
| `volume_entity`    | entity_id or `null`                         | External volume entity                                   |
| `has_wake_button`  | bool                                        | A wake entity is configured (any supported domain; name kept for compatibility) |
| `integration_version` | string                                   | Version of the integration code that is running (from the loader at startup, same value as the card resource `?v=`) |

Example:

```yaml
state: playing
attributes:
  source: YouTube
  source_list: [Netflix, YouTube]
  entry_id: 01JF3Z6V8Q4T0M1N2B3C4D5E6F
  power_state: "on"
  wake_state: idle
  wake_started_at: null
  wake_timeout: 40
  app_id: com.google.android.youtube.tv
  app_name: YouTube
  app_activity: com.google.android.apps.youtube.tv.activity.ShellActivity
  adb_connected: true
  remote_connected: true
  volume_entity: null
  has_wake_button: true
  integration_version: "0.1.1"
```

### Version mismatch

After an update, the browser can keep running the old card until the tab is reloaded, and the new
Python code only runs after Home Assistant restarts. The card compares `integration_version` with
its own built-in version:

- card older than `integration_version`: the tab still has the old card, so the card asks to
  reload the page;
- card newer than `integration_version`: the new files are installed but Home Assistant has not
  restarted yet, so the card asks to restart Home Assistant to finish the update.

`integration_version` is read once from the loaded manifest and is never re-read from disk, so it
always describes the running code. On startup the integration also moves its Lovelace resource
from `...?v=<old>` to `...?v=<integration_version>`.

### Wake entity

`turn_on` on an unreachable TV triggers the configured wake entity (option key `wake_button`,
kept for compatibility). Supported domains and the action used:

| Domain                      | Action                                                                     |
|-----------------------------|----------------------------------------------------------------------------|
| `button`, `input_button`    | `press`                                                                    |
| `switch`, `input_boolean`   | `turn_on`; if already on: `turn_off`, then `turn_on`                       |
| `script`                    | runs the script and waits for it, at most one re-press interval            |
| `scene`                     | `turn_on`                                                                  |

It is triggered again every re-press interval until the TV answers or the wake timeout passes. A
missing or `unavailable` wake entity fails at once with `wake_entity_unavailable` (websocket code
`failed`, the message names the entity) and sets `wake_state: failed`.

## remote entity

- `turn_on` (optional `activity`: app label or package, launched after the TV is on), `turn_off`.
- `send_command`: commands from the key vocabulary; `num_repeats`, `delay_secs`;
  `hold_secs` > 0 makes every command a long press held for that many seconds.
- `activity_list`: visible app labels; `current_activity`: foreground app label.

## Key vocabulary

```
UP DOWN LEFT RIGHT CENTER BACK HOME MENU SETTINGS POWER WAKEUP SLEEP
VOLUME_UP VOLUME_DOWN MUTE PLAY PAUSE PLAY_PAUSE STOP NEXT PREVIOUS REWIND FAST_FORWARD
CHANNEL_UP CHANNEL_DOWN INFO GUIDE SEARCH ASSIST TV INPUT CAPTIONS DELETE ENTER TAB ESCAPE
0 1 2 3 4 5 6 7 8 9 RED GREEN YELLOW BLUE
```

Names are case-insensitive. Anything else matching `KEYCODE_[A-Z0-9_]+` or a number (0-9999) is
passed straight through as an Android key code. Other strings fail with `not_found`
(websocket) or a translated `unknown_key` error (services).

`KEYCODE_*` pass-through works over both transports. Over the remote protocol the name is sent
as is (androidtvremote2 0.3.3 resolves it in its `RemoteKeyCode` enum, which contains the letter
keys, so the card's Kodi shortcuts `KEYCODE_I`, `KEYCODE_C`, `KEYCODE_M`, `KEYCODE_T` arrive as
Android key codes 37, 31, 41, 48). A name the remote enum does not know falls back to ADB
`input keyevent KEYCODE_...` automatically.

Transport: the remote protocol is used when connected (instant); otherwise ADB
`input keyevent <code>` (long press: `input keyevent --longpress <code>`).

Key actions:

| action  | Remote protocol                         | ADB fallback                    |
|---------|-----------------------------------------|---------------------------------|
| `press` | `SHORT`                                 | `input keyevent`                |
| `long`  | `START_LONG`, wait 1 s, `END_LONG`      | `input keyevent --longpress`    |
| `down`  | one press now, then server-side repeat  | same                            |
| `up`    | stops the repeat of that key            | same                            |

Press-and-hold: the card sends `action: "down"` on press and `action: "up"` on release. The
integration repeats only navigation-type keys (`UP DOWN LEFT RIGHT VOLUME_UP VOLUME_DOWN DELETE
CHANNEL_UP CHANNEL_DOWN REWIND FAST_FORWARD`): first repeat after 0.4 s, then every 0.12 s. Each
repeat awaits the previous press, so presses cannot pile up. Rules:

- One repeat per TV at a time. A new `down` (same or another key) stops the previous repeat and
  starts cleanly.
- `up` stops the repeat only if it is for the key that is repeating; otherwise, and when nothing
  repeats, it is a silent no-op (result `{}`).
- The repeat also stops when the websocket connection that sent the `down` closes, when the TV
  becomes unreachable, on unload/reload, and after 15 s (safety stop if `up` never arrives).
- For non-repeatable keys `down` is a single press and `up` does nothing.

## Services

All services take a target: the media_player or remote entity of the TV. (In YAML a `device_id` target
of the TV also works; the UI picker offers the entities, since hassfest does not allow device filters
on service targets.)

| Service         | Fields                                                     | Notes |
|-----------------|------------------------------------------------------------|-------|
| `send_key`      | `key` (required), `action`: `press`\|`long`\|`down`\|`up` (default `press`) | |
| `send_text`     | `text` (required), `enter`: bool (default false)           | Remote IME first; ADB `input text` fallback (ASCII only, else error `non_ascii_text`) |
| `launch_app`    | `package` (required)                                       | ADB `monkey` (leanback launcher, then launcher); remote protocol fallback |
| `open_url`      | `url` (required), `package` (optional)                     | ADB `am start -a android.intent.action.VIEW` |
| `adb_command`   | `command` (required)                                       | **Admin users only.** Returns `{output}`; exactly one target |
| `refresh_apps`  | none                                                       | Re-reads the app list |

`adb_command` is intentionally raw: the command is passed to `adb shell` unquoted, so it can do
anything the ADB shell user can do on the TV. It is therefore registered as an admin service:
calls from non-admin users fail with `Unauthorized` (on Home Assistant versions whose admin
service helper lacks response support, the same check is done in the handler). Every other value that reaches a shell (package
names, URLs, text) goes through a single quoting helper and is validated first.

Example:

```yaml
action: android_tv_pilot.adb_command
target:
  entity_id: media_player.living_room_tv
data:
  command: getprop ro.build.version.release
response_variable: result   # result.output == "9\n"
```

## WebSocket commands

All commands take `entry_id` and need a normal authenticated connection (not admin).

### `android_tv_pilot/apps`

```json
{"id": 10, "type": "android_tv_pilot/apps", "entry_id": "01JF..."}
```

```json
{"apps": [
  {"package": "com.netflix.ninja", "label": "Netflix", "color": "#E50914",
   "icon": "mdi:netflix", "icon_url": null, "hidden": false, "system": true},
  {"package": "org.example.player", "label": "Player", "color": "#3F8FBF",
   "icon": null, "icon_url": null, "hidden": false, "system": false}
]}
```

Sorted by label (case-insensitive), user overrides applied. Hidden apps are included with
`hidden: true` (the card decides whether to show them). `icon` is an `mdi:` name or `null`;
`icon_url` comes from user overrides (or a future APK metadata provider). The list is cached and
refreshed when the TV comes online and by `refresh_apps`; if it was never loaded, this command
tries to load it first.

### `android_tv_pilot/send_key`

```json
{"id": 11, "type": "android_tv_pilot/send_key", "entry_id": "01JF...", "key": "UP", "action": "down"}
```

Result `{}`. `action` defaults to `press`.

### `android_tv_pilot/send_text`

```json
{"id": 12, "type": "android_tv_pilot/send_text", "entry_id": "01JF...", "text": "jellyfin", "enter": true}
```

Result `{}`.

### `android_tv_pilot/launch_app`

```json
{"id": 13, "type": "android_tv_pilot/launch_app", "entry_id": "01JF...", "package": "org.jellyfin.androidtv"}
```

Result `{}`.

### `android_tv_pilot/open_url`

```json
{"id": 14, "type": "android_tv_pilot/open_url", "entry_id": "01JF...",
 "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "package": "com.google.android.youtube.tv"}
```

Result `{}`. `package` is optional.

### `android_tv_pilot/screenshot_url`

```json
{"id": 15, "type": "android_tv_pilot/screenshot_url", "entry_id": "01JF..."}
```

```json
{"url": "/api/android_tv_pilot/screenshot/01JF...?authSig=eyJ..."}
```

A path signed with `async_sign_path`, valid for 30 seconds. `GET` it (e.g. as an `<img src>`) to
receive `image/png`. One capture runs at a time and a capture is reused for 2 seconds. The view also
accepts a normal `Authorization: Bearer` header. HTTP errors: 404 unknown entry, 503 TV unreachable
or ADB not connected, 502 the TV returned no image.

### Errors

Errors use the standard websocket error format with these codes:

| Code             | When                                                                       |
|------------------|----------------------------------------------------------------------------|
| `not_found`      | Unknown/unloaded `entry_id`, unknown key, invalid package name or URL      |
| `tv_unreachable` | No transport connected (TV off / deep standby), or the wake timed out      |
| `unsupported`    | Not possible with the connected transports (e.g. non-ASCII text over ADB only, ADB-only command while only the remote protocol is up) |
| `failed`         | The TV answered but the command failed (no launchable activity, intent not resolved, volume command rejected, ...), or a `turn_on` was cancelled by an unload/reload (`wake_cancelled`), or the wake entity is missing/unavailable (`wake_entity_unavailable`, names the entity) |

```json
{"id": 11, "type": "result", "success": false,
 "error": {"code": "tv_unreachable", "message": "The TV is not reachable. Turn it on first."}}
```

The message is the translated text of the error.

## Static files

The card is served from `custom_components/android_tv_pilot/frontend/` at
`/android_tv_pilot_static/`. On setup the integration adds (or updates) the Lovelace resource
`/android_tv_pilot_static/android-tv-pilot-card.js?v=<integration version>` (type `module`) when
Lovelace resources are in storage mode, and otherwise registers the same URL with
`frontend.add_extra_js_url`. A missing card file logs one warning and does not fail setup.
