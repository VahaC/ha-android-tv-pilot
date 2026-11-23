// In-app control profiles.
//
// A profile is picked by the running package (`app_id` attribute). `match` entries are exact
// package names or globs where `*` matches anything ("org.mozilla.*", "com.xiaomi.*browser*");
// the most specific match wins (see logic.pickBest),
// and anything unmatched gets GENERIC_PROFILE.
//
// Each action is one of:
//   keys  - a sequence of key presses (optionally a long press), e.g. seek with DPAD in a player
//   type  - fixed text sent with send_text into the focused field. Not for shortcuts: text goes
//           through the remote IME, so an app's letter shortcuts need `keys` with KEYCODE_* instead
//   text  - asks the user for text, optionally presses keys first (e.g. SEARCH), then send_text
//   link  - asks for text and opens a deep link via open_url; `{query}` is URL-encoded,
//           `{raw}` is inserted as typed (for pasted URLs). `package: "$current"` targets the
//           running app; omit it to let Android choose.
//   numpad - a 0-9 pad (live TV channels)
//
// Deep links marked `// UNVERIFIED` were not confirmed against the app's documentation or
// source; they are reasonable guesses and should be tested on the real TV.

import type { LocalText } from "./i18n";
import { pickBest } from "./logic";
import type { TvKey } from "./types";

interface BaseAction {
  id: string;
  label: LocalText;
  /** mdi icon name, e.g. "mdi:magnify". */
  icon: string;
}

export interface KeysAction extends BaseAction {
  type: "keys";
  keys: TvKey[];
  long?: boolean;
}

export interface TypeAction extends BaseAction {
  type: "type";
  text: string;
  enter?: boolean;
}

export interface TextAction extends BaseAction {
  type: "text";
  placeholder: LocalText;
  /** Keys pressed before the text is sent (e.g. ["SEARCH"]). */
  before?: TvKey[];
  enter?: boolean;
}

export interface LinkAction extends BaseAction {
  type: "link";
  placeholder: LocalText;
  template: string;
  package?: string;
  /** "url" validates and normalises the input as a URL before templating. */
  input?: "query" | "url";
}

export interface NumpadAction extends BaseAction {
  type: "numpad";
}

export type ProfileAction = KeysAction | TypeAction | TextAction | LinkAction | NumpadAction;

export interface AppProfile {
  id: string;
  name: LocalText;
  match: string[];
  actions: ProfileAction[];
}

// ---- reusable action builders -------------------------------------------------------------

const L = (en: string, uk: string): LocalText => ({ en, uk });

const seekBack = (keys: TvKey[] = ["LEFT"]): KeysAction => ({
  id: "seek_back", type: "keys", keys, icon: "mdi:rewind-10", label: L("Seek back", "Назад"),
});
const seekFwd = (keys: TvKey[] = ["RIGHT"]): KeysAction => ({
  id: "seek_fwd", type: "keys", keys, icon: "mdi:fast-forward-10", label: L("Seek forward", "Вперед"),
});
const captions: KeysAction = {
  id: "captions", type: "keys", keys: ["CAPTIONS"], icon: "mdi:subtitles-outline", label: L("Subtitles", "Субтитри"),
};
const searchKeyText: TextAction = {
  id: "search", type: "text", before: ["SEARCH"], enter: true, icon: "mdi:magnify",
  label: L("Search", "Пошук"), placeholder: L("What to search for", "Що шукати"),
};
const info: KeysAction = { id: "info", type: "keys", keys: ["INFO"], icon: "mdi:information-outline", label: L("Info", "Інфо") };
const menu: KeysAction = { id: "menu", type: "keys", keys: ["MENU"], icon: "mdi:dots-vertical", label: L("Options", "Опції") };
const openUrlInApp = (pkg: string): LinkAction => ({
  id: "open_url", type: "link", input: "url", template: "{raw}", package: pkg, icon: "mdi:link-variant",
  label: L("Open link", "Відкрити посилання"), placeholder: L("Paste a video URL", "Вставте посилання на відео"),
});

// ---- profiles -----------------------------------------------------------------------------

export const GENERIC_PROFILE: AppProfile = {
  id: "generic",
  name: L("Controls", "Керування"),
  match: [],
  actions: [
    { id: "search_key", type: "keys", keys: ["SEARCH"], icon: "mdi:magnify", label: L("Search", "Пошук") },
    { id: "type", type: "text", enter: false, icon: "mdi:form-textbox", label: L("Type text", "Ввести текст"), placeholder: L("Text for the focused field", "Текст для вибраного поля") },
    { id: "play_pause", type: "keys", keys: ["PLAY_PAUSE"], icon: "mdi:play-pause", label: L("Play / pause", "Пуск / пауза") },
    { id: "stop", type: "keys", keys: ["STOP"], icon: "mdi:stop", label: L("Stop", "Стоп") },
    captions,
    menu,
  ],
};

export const PROFILES: AppProfile[] = [
  {
    id: "youtube",
    name: "YouTube",
    match: ["com.google.android.youtube.tv", "com.google.android.youtube.tvkids"],
    actions: [
      {
        id: "search", type: "link", icon: "mdi:magnify", label: L("Search", "Пошук"),
        placeholder: L("Search YouTube", "Пошук на YouTube"),
        // UNVERIFIED: YouTube for Android TV handles youtube.com watch links; handling of /results is not documented.
        template: "https://www.youtube.com/results?search_query={query}",
        package: "com.google.android.youtube.tv",
      },
      openUrlInApp("com.google.android.youtube.tv"),
      captions,
      seekBack(["LEFT"]),
      seekFwd(["RIGHT"]),
      { id: "skip_back", type: "keys", keys: ["LEFT", "LEFT", "LEFT"], icon: "mdi:rewind-30", label: L("Back 30 s", "Назад 30 с") },
      { id: "skip_fwd", type: "keys", keys: ["RIGHT", "RIGHT", "RIGHT"], icon: "mdi:fast-forward-30", label: L("Forward 30 s", "Вперед 30 с") },
    ],
  },
  {
    id: "smarttube",
    name: "SmartTube",
    // Stable builds use com.teamsmart.videomanager.tv, beta builds com.liskovsoft.smarttubetv.beta.
    match: ["com.teamsmart.videomanager.tv", "com.liskovsoft.smarttubetv*", "com.liskovsoft.smartyoutubetv2*"],
    actions: [
      {
        id: "search", type: "link", icon: "mdi:magnify", label: L("Search", "Пошук"),
        placeholder: L("Search YouTube", "Пошук на YouTube"),
        // Manifest checked: SplashActivity accepts http(s)://(www.)youtube.com/.* (any path).
        // UNVERIFIED: that the app reads search_query from /results and opens the search screen.
        template: "https://www.youtube.com/results?search_query={query}",
        package: "$current",
      },
      // Verified at manifest level: youtube.com / youtu.be links open in SmartTube.
      openUrlInApp("$current"),
      captions,
      seekBack(["LEFT"]),
      seekFwd(["RIGHT"]),
      { id: "options", type: "keys", keys: ["MENU"], icon: "mdi:tune-variant", label: L("Player options", "Опції плеєра") },
    ],
  },
  {
    id: "youtube_music",
    name: "YouTube Music",
    match: ["com.google.android.youtube.tvmusic", "com.google.android.apps.youtube.music"],
    actions: [
      {
        id: "search", type: "link", icon: "mdi:magnify", label: L("Search", "Пошук"),
        placeholder: L("Song, artist or album", "Пісня, виконавець чи альбом"),
        // UNVERIFIED: music.youtube.com search links on the Android TV app.
        template: "https://music.youtube.com/search?q={query}",
        package: "$current",
      },
      { id: "prev", type: "keys", keys: ["PREVIOUS"], icon: "mdi:skip-previous", label: L("Previous", "Попередня") },
      { id: "next", type: "keys", keys: ["NEXT"], icon: "mdi:skip-next", label: L("Next", "Наступна") },
      { id: "play_pause", type: "keys", keys: ["PLAY_PAUSE"], icon: "mdi:play-pause", label: L("Play / pause", "Пуск / пауза") },
    ],
  },
  {
    id: "netflix",
    name: "Netflix",
    match: ["com.netflix.ninja", "com.netflix.mediaclient"],
    actions: [
      {
        id: "search", type: "link", icon: "mdi:magnify", label: L("Search", "Пошук"),
        placeholder: L("Title, person or genre", "Назва, актор чи жанр"),
        // UNVERIFIED: Netflix documents /title/<id> links; /search?q= on the TV app is not documented.
        template: "https://www.netflix.com/search?q={query}",
        package: "com.netflix.ninja",
      },
      seekBack(["LEFT"]),
      seekFwd(["RIGHT"]),
      { id: "audio_subs", type: "keys", keys: ["DOWN"], icon: "mdi:subtitles-outline", label: L("Audio & subtitles", "Аудіо й субтитри") },
      { id: "skip_intro", type: "keys", keys: ["CENTER"], icon: "mdi:debug-step-over", label: L("Skip intro (OK)", "Пропустити заставку (OK)") },
    ],
  },
  {
    id: "jellyfin",
    name: "Jellyfin",
    match: ["org.jellyfin.androidtv", "org.jellyfin.mobile"],
    actions: [
      searchKeyText,
      seekBack(["REWIND"]),
      seekFwd(["FAST_FORWARD"]),
      captions,
      { ...menu, label: L("Player menu", "Меню плеєра") },
      info,
    ],
  },
  {
    id: "plex",
    name: "Plex",
    match: ["com.plexapp.android", "com.plexapp.*"],
    actions: [
      searchKeyText,
      seekBack(["LEFT"]),
      seekFwd(["RIGHT"]),
      captions,
      { ...menu, label: L("Player options", "Опції плеєра") },
    ],
  },
  {
    id: "kodi",
    name: "Kodi",
    match: ["org.xbmc.kodi", "org.xbmc.*"],
    // Letter shortcuts come from Kodi's system/keymaps/keyboard.xml (checked on the master branch):
    // i = Info, c = ContextMenu (global), m = OSD, t = ShowSubtitles (FullscreenVideo),
    // long-press Up = AudioNextLanguage, long-press Down = NextSubtitle (FullscreenVideo).
    // The letters are sent as real key events (KEYCODE_*, passed through by the integration);
    // send_text goes through the remote IME and never reaches Kodi's keymap.
    actions: [
      { id: "info", type: "keys", keys: ["KEYCODE_I"], icon: "mdi:information-outline", label: L("Info", "Інфо") },
      { id: "context", type: "keys", keys: ["KEYCODE_C"], icon: "mdi:dots-vertical", label: L("Context menu", "Контекстне меню") },
      { id: "osd", type: "keys", keys: ["KEYCODE_M"], icon: "mdi:tune-variant", label: L("Player OSD", "Панель плеєра") },
      { id: "subs_toggle", type: "keys", keys: ["KEYCODE_T"], icon: "mdi:subtitles-outline", label: L("Subtitles on/off", "Субтитри ув./вимк.") },
      { id: "subs_next", type: "keys", keys: ["DOWN"], long: true, icon: "mdi:subtitles", label: L("Next subtitle", "Наступні субтитри") },
      { id: "audio_next", type: "keys", keys: ["UP"], long: true, icon: "mdi:account-voice", label: L("Next audio track", "Наступна доріжка") },
      searchKeyText,
    ],
  },
  {
    id: "vlc",
    name: "VLC",
    match: ["org.videolan.vlc"],
    actions: [
      {
        id: "open_stream", type: "link", input: "url", template: "{raw}", package: "org.videolan.vlc",
        icon: "mdi:play-network", label: L("Open stream", "Відкрити потік"),
        // UNVERIFIED: VLC registers ACTION_VIEW for http(s) media; not checked for this exact build.
        placeholder: L("Media or stream URL", "Посилання на медіа чи потік"),
      },
      seekBack(["LEFT"]),
      seekFwd(["RIGHT"]),
      captions,
      { ...menu, label: L("Tracks & options", "Доріжки й опції") },
    ],
  },
  {
    id: "spotify",
    name: "Spotify",
    match: ["com.spotify.tv.android", "com.spotify.music"],
    actions: [
      {
        id: "search", type: "link", icon: "mdi:magnify", label: L("Search", "Пошук"),
        placeholder: L("Song, artist or podcast", "Пісня, виконавець чи подкаст"),
        // UNVERIFIED: spotify:search: URIs are documented for desktop/mobile, not for the TV app.
        template: "spotify:search:{query}",
        package: "$current",
      },
      { id: "prev", type: "keys", keys: ["PREVIOUS"], icon: "mdi:skip-previous", label: L("Previous", "Попередня") },
      { id: "next", type: "keys", keys: ["NEXT"], icon: "mdi:skip-next", label: L("Next", "Наступна") },
      { id: "play_pause", type: "keys", keys: ["PLAY_PAUSE"], icon: "mdi:play-pause", label: L("Play / pause", "Пуск / пауза") },
    ],
  },
  {
    id: "prime_video",
    name: "Prime Video",
    match: ["com.amazon.amazonvideo.livingroom", "com.amazon.avod*"],
    actions: [
      searchKeyText,
      seekBack(["LEFT"]),
      seekFwd(["RIGHT"]),
      { id: "audio_subs", type: "keys", keys: ["UP"], icon: "mdi:subtitles-outline", label: L("Audio & subtitles", "Аудіо й субтитри") },
    ],
  },
  {
    id: "browser",
    name: L("Browser", "Браузер"),
    match: [
      "com.android.chrome", "com.chrome.*", "org.mozilla.*", "com.opera.*", "com.brave.browser",
      "com.phlox.tvwebbrowser", "com.tvwebbrowser*", "com.cloudmosa.puffinTV", "com.vewd.*", "com.xiaomi.*browser*",
    ],
    actions: [
      {
        id: "open_url", type: "link", input: "url", template: "{raw}", package: "$current",
        icon: "mdi:web", label: L("Open address", "Відкрити адресу"), placeholder: L("Any URL, e.g. example.com", "Будь-яка адреса, напр. example.com"),
      },
      {
        id: "web_search", type: "link", template: "https://www.google.com/search?q={query}", package: "$current",
        icon: "mdi:magnify", label: L("Web search", "Пошук в інтернеті"), placeholder: L("Search the web", "Пошук в інтернеті"),
      },
      { id: "tab", type: "keys", keys: ["TAB"], icon: "mdi:keyboard-tab", label: L("Next field", "Наступне поле") },
      { id: "type", type: "text", enter: true, icon: "mdi:form-textbox", label: L("Type + Enter", "Текст + Enter"), placeholder: L("Text for the page", "Текст для сторінки") },
    ],
  },
  {
    id: "live_tv",
    name: L("Live TV", "Телебачення"),
    match: [
      "com.google.android.tv", "com.android.tv", "com.mitv.tvplayer*", "com.xiaomi.mitv.tvplayer*",
      "com.droidlogic.tvinput*", "com.mediatek.wwtv.tvcenter",
    ],
    actions: [
      { id: "ch_up", type: "keys", keys: ["CHANNEL_UP"], icon: "mdi:chevron-up-box-outline", label: L("Channel +", "Канал +") },
      { id: "ch_down", type: "keys", keys: ["CHANNEL_DOWN"], icon: "mdi:chevron-down-box-outline", label: L("Channel −", "Канал −") },
      { id: "guide", type: "keys", keys: ["GUIDE"], icon: "mdi:television-guide", label: L("Guide", "Телепрограма") },
      info,
      { id: "input", type: "keys", keys: ["INPUT"], icon: "mdi:video-input-hdmi", label: L("Input", "Джерело") },
      { id: "numpad", type: "numpad", icon: "mdi:dialpad", label: L("Channel number", "Номер каналу") },
    ],
  },
  {
    id: "settings",
    name: L("Settings", "Налаштування"),
    match: ["com.android.tv.settings", "com.android.settings", "com.xiaomi.mitv.settings*"],
    actions: [
      { id: "type", type: "text", enter: false, icon: "mdi:form-textbox", label: L("Type into field", "Ввести в поле"), placeholder: L("Wi-Fi password, name…", "Пароль Wi-Fi, назва…") },
      { id: "home", type: "keys", keys: ["HOME"], icon: "mdi:home-outline", label: L("Leave settings", "Вийти з налаштувань") },
      { id: "input", type: "keys", keys: ["INPUT"], icon: "mdi:video-input-hdmi", label: L("Input", "Джерело") },
    ],
  },
];

/** The profile for the running package, or the generic one. */
export function profileFor(appId: string | null | undefined): AppProfile {
  return pickBest(PROFILES, appId, GENERIC_PROFILE);
}
