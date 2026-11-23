# Android TV Pilot card

A Lovelace card for the Android TV Pilot integration: power with BLE wake progress, a D-pad or
touchpad, volume and media keys, an app launcher, per-app quick actions ("control inside apps"),
a keyboard and an optional screenshot preview.

The card is a single ES module served by the integration:
`custom_components/android_tv_pilot/frontend/android-tv-pilot-card.js`.

## Configuration

```yaml
type: custom:android-tv-pilot-card
entity: media_player.living_room_tv
layout: a
pinned_apps:
  - org.jellyfin.androidtv
  - com.google.android.youtube.tv
hidden_apps:
  - com.android.vending
show_screenshot: false
```

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | string | — | `custom:android-tv-pilot-card` |
| `entity` | string | — (required) | The integration's `media_player`. It must have the `entry_id` attribute. |
| `name` | string | entity friendly name | Title shown in the header. |
| `layout` | `a` \| `b` \| `c` | `a` | A = remote first, B = apps first, C = wide / tablet. See [Layouts](#layouts). |
| `volume_entity` | string | the entity's `volume_entity` attribute | A `media_player` (soundbar, receiver) that takes the volume buttons. Overrides the integration's setting. |
| `pinned_apps` | list of packages | `[]` | Shown first, in this order. Pinning also shows an app the integration marked `hidden`. |
| `hidden_apps` | list of packages | `[]` | Never shown in the launcher. Apps flagged `system` (preinstalled YouTube, Netflix, Play Store) are shown; only `hidden` apps and this list are left out. |
| `show_screenshot` | bool | `false` | Adds a tap-to-refresh screenshot of the TV screen. |
| `haptics` | bool | `true` | Sends HA `haptic` events (`light`, `selection`, `success`, `failure`) on key presses. |
| `prototype_switch` | bool | `true` | Shows the temporary A/B/C layout switch inside the card (see below). |

The visual editor (card settings in the dashboard) covers every option; the app pickers list the
apps reported by the TV, and accept any package name typed in by hand.

### Volume

- With a volume entity (from `volume_entity` in the card or in the integration options), the
  buttons call `media_player.volume_up` / `volume_down` / `volume_mute` on that entity and the
  card shows its level. If that entity supports `volume_set`, the level is a slider.
- Without one, the buttons send the `VOLUME_UP` / `VOLUME_DOWN` / `MUTE` keys to the TV and the
  card shows the TV entity's `volume_level` as a read-only meter.

## What each state looks like

| `power_state` / `wake_state` | Card |
| --- | --- |
| `on` | Everything enabled. The header shows the running app in its brand colour, and the whole card takes that colour as its accent. |
| `waking` (or `wake_state: waking`) | Shown the moment you tap power (before the server answers, for up to 10 s), so the button cannot be double-tapped. Power button shows a progress ring; a banner says "Waking up… 12 s" with a progress bar computed from `wake_started_at` and `wake_timeout`. Controls stay visible but are disabled. |
| `wake_state: failed` and `power_state: off` | Red banner "The TV did not wake up" with a **Retry wake** button (calls `media_player.turn_on` again). |
| `off`, `has_wake_button: true` | "TV is off" banner with **Turn on**. |
| `off`, `has_wake_button: false` | Warning "Deep-standby wake is not configured" with what to do; the power button reads "Try to turn on". |
| `asleep` | "TV is asleep" banner with **Turn on**. |

Failed TV commands (WebSocket) show a short toast at the bottom of the card; failed service calls (power, volume entity) only give haptic feedback, because HA already shows its own error. `tv_unreachable` adds a **Wake TV**
button. `unsupported` from `send_text` (for example Cyrillic text over ADB) appears inline under the
text field instead.

## Layouts

All three layouts use the same building blocks; only their arrangement differs.

- **A — Remote first.** Tall phone-style remote: navigation pad on top, then BACK / HOME / MENU /
  SETTINGS / SEARCH / ASSISTANT, volume, media keys and an app rail. In-app controls, the keyboard
  and the screenshot live in a bottom sheet; tap the bar at the bottom of the card to open it.
- **B — Apps first.** Launcher-style app grid on top, the running app's controls directly under it,
  then a compact pad next to the navigation keys, volume, media keys and a folded keyboard.
- **C — Wide / tablet.** Columns: apps (+ screenshot) | pad, keys, volume, media | in-app controls +
  keyboard. Three columns from about 940 px of card width, two from 620 px, one below that. In a
  sections dashboard it asks for the full width.

### Temporary layout switch

While `prototype_switch` is on, a dashed strip at the top of the card lets you flip between A, B and
C on real data. The choice is stored in this browser only (localStorage key
`android-tv-pilot:layout`) and overrides `layout` from the config until you press **Use config**,
which appears while an override is active. Changing `layout` in the card config clears the stored
choice, so the editor always wins.
Set `prototype_switch: false` to hide it. All code for the switch is marked
`PROTOTYPE (2026-11-23)` and will be removed once a layout is chosen.

### Navigation modes

The D-pad / Touchpad toggle above the pad is remembered per browser
(`android-tv-pilot:nav-mode`).

- **D-pad**: press and hold an arrow to repeat. The card sends `down` when you press and `up` when
  you let go; the integration does the repeating and waits for each press, so nothing queues up on a
  slow ADB link. `up` is also sent when the pointer is cancelled or loses capture, the button loses
  focus, the page is hidden, the window loses focus, the card is removed, and when the TV stops being
  on. The same applies to the volume, rewind / fast-forward, delete and channel ± buttons. Hold OK
  for a long press (`action: long`); a ring fills while you hold.
- **Touchpad**: every 30 px of drag sends one step, so a long drag scrolls; resting the finger after
  a swipe keeps repeating. A new step is dropped (not queued) while the previous one is still being
  sent, so the cursor stops when your finger does. Tap = OK, hold = long OK, two-finger tap or the corner button = BACK.
  With a keyboard: arrows, Enter/Space = OK, Backspace/Escape = BACK.

## In-app controls (profiles)

The panel titled "In <app>" is driven by `card/src/app-profiles.ts`. The card picks a profile by
the `app_id` attribute (the running package):

1. An exact package match wins.
2. Otherwise the matching glob with the most literal characters; `*` matches anything, anywhere
   (`"org.mozilla.*"`, `"com.xiaomi.*browser*"`).
3. Otherwise the generic profile (search key, type text, play/pause, stop, subtitles, options).

Shipped profiles: YouTube, SmartTube, YouTube Music, Netflix, Jellyfin, Plex, Kodi, VLC, Spotify,
Prime Video, Browser (Chrome, Firefox, TV Bro and others), Live TV, Settings.

### Action types

| Type | What it does | Fields |
| --- | --- | --- |
| `keys` | Sends keys in order (140 ms apart). Keys from the contract vocabulary or raw `KEYCODE_*` names. A single repeatable key (seek, channel ±) is held with `down` / `up`. | `keys`, optional `long: true` |
| `type` | Sends fixed text into the focused field. Not for shortcuts: text goes through the remote IME, so use `keys` with `KEYCODE_*` for an app's letter shortcuts. | `text`, optional `enter` |
| `text` | Asks for text, optionally presses keys first (e.g. `SEARCH`), then `send_text`. | `placeholder`, `before`, `enter` |
| `link` | Asks for text and calls `open_url` with a filled template. `{query}` is URL-encoded; `{raw}` is inserted as typed (with `input: "url"` the value is checked and `https://` is added to bare hosts). `package: "$current"` sends the running app's package. | `template`, `placeholder`, `package`, `input` |
| `numpad` | Opens a 0–9 pad (for channel numbers). | — |

Labels are either a plain string or `{ en: "...", uk: "..." }`.

### Adding a profile

1. Add an entry to `PROFILES` in `card/src/app-profiles.ts`:

   ```ts
   {
     id: "my_app",
     name: "My App",
     match: ["com.example.myapp", "com.example.myapp.*"],
     actions: [
       {
         id: "search", type: "link", icon: "mdi:magnify",
         label: { en: "Search", uk: "Пошук" },
         placeholder: { en: "What to search for", uk: "Що шукати" },
         template: "https://example.com/search?q={query}", // UNVERIFIED until tested on the TV
         package: "$current",
       },
       { id: "subs", type: "keys", keys: ["CAPTIONS"], icon: "mdi:subtitles-outline", label: { en: "Subtitles", uk: "Субтитри" } },
     ],
   },
   ```

2. Keys must come from the integration's key vocabulary (`TvKey` in `card/src/types.ts`).
3. Mark any deep link you have not confirmed in the app's documentation or manifest with
   `// UNVERIFIED`.
4. Run `npm test` (checks matching and that action ids are unique) and `npm run build`.

### Deep links that are not verified

These are reasonable guesses and need a test on the real TV:

- YouTube: `https://www.youtube.com/results?search_query={query}` opened in the YouTube TV app.
- SmartTube: the manifest accepts any `youtube.com` path, but reading `search_query` from
  `/results` is not confirmed.
- YouTube Music: `https://music.youtube.com/search?q={query}`.
- Netflix: `https://www.netflix.com/search?q={query}`.
- Spotify: `spotify:search:{query}` in the TV app.
- VLC: opening an `http(s)` stream URL with `package: org.videolan.vlc`.

Kodi's shortcuts (`KEYCODE_I` info, `KEYCODE_C` context menu, `KEYCODE_M` OSD, `KEYCODE_T`
subtitles, long-press Up/Down for audio track / subtitle) were taken from Kodi's
`system/keymaps/keyboard.xml`. They are sent as key events, not text.

## Screenshot

With `show_screenshot: true` the card asks `android_tv_pilot/screenshot_url` for a signed PNG URL.
It refreshes every 10 s while the card is on screen and the browser tab is visible, never more often
than every 5 s automatically, and pauses otherwise. In layout A nothing is requested unless the
bottom sheet is open on the Screen tab. Tapping the picture refreshes it (at most once a
second).

## Development

```bash
cd card
npm install
npm run demo       # review harness on http://localhost:5179 (add ?bundle to load the built file)
npm run typecheck  # tsc --noEmit
npm test           # vitest: profile matching, templating, wake progress, swipe detection
npm run build      # writes custom_components/android_tv_pilot/frontend/android-tv-pilot-card.js
```

The demo (`card/demo`) runs the card against a mock `hass`: a power state machine
(off → waking → on after 6–12 s), 17 mock apps, mocked WebSocket commands that log to the on-page
console, buttons to force each state (including `failed`), a `tv_unreachable` switch, apps
loading/empty/error modes, a soundbar volume entity, light/dark theme, English/Ukrainian and card
width presets (320, 390, 768, 1180 px). The HA editor (`ha-form`) is not available in the demo.
