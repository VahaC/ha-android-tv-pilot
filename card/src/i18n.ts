// UI strings. English is the source of truth; Ukrainian must cover the same keys
// (the type below makes a missing key a compile error).

const en = {
  card_name: "Android TV Pilot",
  card_description: "A tactile remote for Android TV: power with BLE wake, D-pad or touchpad, apps and in-app controls.",
  entity_missing: "Entity {entity} not found. Check the card configuration.",
  entity_not_pilot: "{entity} is not an Android TV Pilot media player.",
  render_error: "The card could not be drawn. See the browser console for details.",
  version_reload: "A newer version of this card is installed. Reload the page.",
  version_restart: "Restart Home Assistant to finish the update.",
  version_reload_button: "Reload",
  version_dismiss: "Hide this notice",

  power_on: "Turn on",
  power_off: "Turn off",
  power_try_on: "Try to turn on",
  power_retry: "Retry wake",
  state_off: "Off",
  state_on: "On",
  state_asleep: "Asleep",
  state_waking: "Waking up…",
  waking_seconds: "Waking up… {s} s",
  waking_overdue: "Still waking… {s} s",
  waking_hint: "Waking the TV over Bluetooth. This usually takes 5–30 s.",
  wake_failed_title: "The TV did not wake up",
  wake_failed_body: "The Bluetooth wake timed out. Check that the ESP32 is online and close enough to the TV.",
  off_title: "TV is off",
  off_body: "Tap power to wake it.",
  off_no_wake_title: "Deep-standby wake is not configured",
  off_no_wake_body: "This TV has no BLE wake button set up, so it cannot be woken from deep standby. Power it on with its own remote, or add an ESP32 wake button in the integration options.",
  asleep_title: "TV is asleep",
  asleep_body: "The screen is off. Tap power to wake it.",
  conn_adb: "ADB",
  conn_remote: "Remote",
  conn_ok: "connected",
  conn_down: "disconnected",
  no_app: "Home screen",

  nav_dpad: "D-pad",
  nav_touchpad: "Touchpad",
  nav_mode: "Navigation mode",
  key_up: "Up",
  key_down: "Down",
  key_left: "Left",
  key_right: "Right",
  key_center: "OK (hold for long press)",
  key_back: "Back",
  key_home: "Home",
  key_menu: "Menu",
  key_settings: "Settings",
  key_assist: "Assistant",
  key_search: "Search",
  key_info: "Info",
  key_guide: "Guide",
  key_captions: "Subtitles",
  key_input: "Input",
  touchpad_label: "Touchpad. Swipe to move, tap for OK, hold for long press, two-finger tap for Back.",
  touchpad_hint: "Swipe · tap OK · hold · two fingers = Back",

  volume: "Volume",
  volume_up: "Volume up",
  volume_down: "Volume down",
  mute: "Mute",
  unmute: "Unmute",
  play_pause: "Play / pause",
  rewind: "Rewind",
  fast_forward: "Fast forward",
  previous: "Previous",
  next: "Next",
  now_playing: "Now playing",

  apps: "Apps",
  apps_loading: "Loading apps…",
  apps_empty: "No apps to show. Check hidden apps in the card settings.",
  apps_error: "Could not load apps.",
  apps_off: "Apps appear when the TV is on.",
  retry: "Retry",
  launch: "Open {app}",
  running: "running",

  inapp: "In {app}",
  inapp_generic: "Controls",
  inapp_open: "Show controls for {app}",
  inapp_close: "Hide controls",
  send: "Send",
  go: "Go",
  cancel: "Cancel",

  keyboard: "Keyboard",
  keyboard_placeholder: "Type to the focused field on the TV",
  keyboard_send: "Send text",
  keyboard_send_enter: "Send + Enter",
  keyboard_enter: "Enter",
  keyboard_delete: "Delete",
  keyboard_sent: "Sent",
  keyboard_ascii: "Only Latin letters, digits and basic symbols can be typed over ADB. Use the TV's own on-screen keyboard or voice search for other text.",

  screen: "Screen",
  screenshot: "TV screenshot",
  screenshot_refresh: "Tap to refresh",
  screenshot_loading: "Taking a screenshot…",
  screenshot_error: "Screenshot failed",
  screenshot_paused: "Paused while the card is hidden",

  err_tv_unreachable: "The TV is not reachable.",
  err_unsupported: "The TV does not support this.",
  err_not_found: "The integration entry was not found. Reload the integration.",
  err_failed: "Command failed",
  wake_tv: "Wake TV",
  dismiss: "Dismiss",

  // Layouts
  layout_remote: "Remote first",
  layout_apps: "Apps first",
  layout_wide: "Wide",
  layout_remote_help: "Tall phone remote: big pad, apps in a rail, app controls in a pull-up sheet.",
  layout_apps_help: "Launcher style: app grid on top, controls for the running app right under it.",
  layout_wide_help: "Columns for tablets and desktops: apps, remote, app controls side by side.",
  layout_button: "Card layout: {layout}",
  layout_menu: "Card layout",
  layout_use_dashboard: "Use dashboard setting ({layout})",
  layout_this_browser: "Chosen in this browser",

  // Editor
  ed_entity: "TV (Android TV Pilot media player)",
  ed_name: "Name",
  ed_layout: "Layout",
  ed_volume_entity: "Volume entity (overrides the integration's)",
  ed_pinned: "Pinned apps (shown first)",
  ed_hidden: "Hidden apps",
  ed_screenshot: "Show screenshot preview",
  ed_haptics: "Haptic feedback",
  ed_layout_switch: "Show layout button on the card",
};

export type StringKey = keyof typeof en;
type Table = Record<StringKey, string>;

const uk: Table = {
  card_name: "Android TV Pilot",
  card_description: "Тактильний пульт для Android TV: увімкнення через BLE, D-pad або тачпад, застосунки й керування всередині них.",
  entity_missing: "Сутність {entity} не знайдено. Перевірте налаштування картки.",
  entity_not_pilot: "{entity} не є медіаплеєром Android TV Pilot.",
  render_error: "Не вдалося показати картку. Подробиці в консолі браузера.",
  version_reload: "Встановлено новішу версію цієї картки. Перезавантажте сторінку.",
  version_restart: "Перезапустіть Home Assistant, щоб завершити оновлення.",
  version_reload_button: "Перезавантажити",
  version_dismiss: "Сховати це повідомлення",

  power_on: "Увімкнути",
  power_off: "Вимкнути",
  power_try_on: "Спробувати увімкнути",
  power_retry: "Розбудити ще раз",
  state_off: "Вимкнено",
  state_on: "Увімкнено",
  state_asleep: "Сплячий режим",
  state_waking: "Прокидається…",
  waking_seconds: "Прокидається… {s} с",
  waking_overdue: "Досі прокидається… {s} с",
  waking_hint: "Будимо телевізор через Bluetooth. Зазвичай це займає 5–30 с.",
  wake_failed_title: "Телевізор не прокинувся",
  wake_failed_body: "Час очікування Bluetooth-пробудження вичерпано. Перевірте, що ESP32 онлайн і стоїть достатньо близько до телевізора.",
  off_title: "Телевізор вимкнено",
  off_body: "Натисніть кнопку живлення, щоб розбудити його.",
  off_no_wake_title: "Пробудження з глибокого сну не налаштовано",
  off_no_wake_body: "Для цього телевізора немає BLE-кнопки пробудження, тож розбудити його з глибокого сну не вийде. Увімкніть його рідним пультом або додайте кнопку пробудження ESP32 у параметрах інтеграції.",
  asleep_title: "Телевізор спить",
  asleep_body: "Екран вимкнено. Натисніть кнопку живлення, щоб розбудити.",
  conn_adb: "ADB",
  conn_remote: "Пульт",
  conn_ok: "підключено",
  conn_down: "не підключено",
  no_app: "Головний екран",

  nav_dpad: "D-pad",
  nav_touchpad: "Тачпад",
  nav_mode: "Режим навігації",
  key_up: "Вгору",
  key_down: "Вниз",
  key_left: "Ліворуч",
  key_right: "Праворуч",
  key_center: "OK (утримуйте для довгого натискання)",
  key_back: "Назад",
  key_home: "Додому",
  key_menu: "Меню",
  key_settings: "Налаштування",
  key_assist: "Асистент",
  key_search: "Пошук",
  key_info: "Інформація",
  key_guide: "Телепрограма",
  key_captions: "Субтитри",
  key_input: "Джерело",
  touchpad_label: "Тачпад. Проведіть, щоб рухатися, торкніться для OK, утримуйте для довгого натискання, торкніться двома пальцями — Назад.",
  touchpad_hint: "Свайп · дотик OK · утримання · два пальці = Назад",

  volume: "Гучність",
  volume_up: "Гучніше",
  volume_down: "Тихіше",
  mute: "Вимкнути звук",
  unmute: "Увімкнути звук",
  play_pause: "Відтворення / пауза",
  rewind: "Перемотати назад",
  fast_forward: "Перемотати вперед",
  previous: "Попереднє",
  next: "Наступне",
  now_playing: "Зараз грає",

  apps: "Застосунки",
  apps_loading: "Завантаження застосунків…",
  apps_empty: "Немає застосунків для показу. Перевірте приховані застосунки в налаштуваннях картки.",
  apps_error: "Не вдалося завантажити застосунки.",
  apps_off: "Застосунки з'являться, коли телевізор увімкнеться.",
  retry: "Повторити",
  launch: "Відкрити {app}",
  running: "запущено",

  inapp: "У {app}",
  inapp_generic: "Керування",
  inapp_open: "Показати керування для {app}",
  inapp_close: "Сховати керування",
  send: "Надіслати",
  go: "Перейти",
  cancel: "Скасувати",

  keyboard: "Клавіатура",
  keyboard_placeholder: "Текст у поле, вибране на телевізорі",
  keyboard_send: "Надіслати текст",
  keyboard_send_enter: "Надіслати + Enter",
  keyboard_enter: "Enter",
  keyboard_delete: "Стерти",
  keyboard_sent: "Надіслано",
  keyboard_ascii: "Через ADB можна набирати лише латиницю, цифри й базові символи. Для іншого тексту скористайтеся екранною клавіатурою телевізора або голосовим пошуком.",

  screen: "Екран",
  screenshot: "Знімок екрана телевізора",
  screenshot_refresh: "Торкніться, щоб оновити",
  screenshot_loading: "Робимо знімок…",
  screenshot_error: "Не вдалося зробити знімок",
  screenshot_paused: "Призупинено, поки картку не видно",

  err_tv_unreachable: "Телевізор недоступний.",
  err_unsupported: "Телевізор цього не підтримує.",
  err_not_found: "Запис інтеграції не знайдено. Перезавантажте інтеграцію.",
  err_failed: "Команда не виконалася",
  wake_tv: "Розбудити",
  dismiss: "Закрити",

  layout_remote: "Спершу пульт",
  layout_apps: "Спершу застосунки",
  layout_wide: "Широкий",
  layout_remote_help: "Високий пульт як на телефоні: великий джойстик, застосунки в стрічці, керування застосунком у висувній панелі.",
  layout_apps_help: "Як лаунчер: сітка застосунків угорі, керування запущеним застосунком одразу під нею.",
  layout_wide_help: "Колонки для планшета й комп'ютера: застосунки, пульт і керування застосунком поруч.",
  layout_button: "Макет картки: {layout}",
  layout_menu: "Макет картки",
  layout_use_dashboard: "Як на панелі ({layout})",
  layout_this_browser: "Вибрано в цьому браузері",

  ed_entity: "Телевізор (медіаплеєр Android TV Pilot)",
  ed_name: "Назва",
  ed_layout: "Макет",
  ed_volume_entity: "Сутність гучності (замість тієї, що в інтеграції)",
  ed_pinned: "Закріплені застосунки (показуються першими)",
  ed_hidden: "Приховані застосунки",
  ed_screenshot: "Показувати знімок екрана",
  ed_haptics: "Тактильний відгук",
  ed_layout_switch: "Показувати кнопку макета на картці",
};

const tables: Record<string, Table> = { en, uk };

export type Lang = "en" | "uk";

export function pickLanguage(language: string | undefined): Lang {
  return language && language.toLowerCase().startsWith("uk") ? "uk" : "en";
}

export type Translate = (key: StringKey, vars?: Record<string, string | number>) => string;

export function translator(lang: Lang): Translate {
  const table = tables[lang] ?? en;
  return (key, vars) => {
    let text = table[key] ?? en[key] ?? key;
    if (vars) for (const [name, value] of Object.entries(vars)) text = text.split(`{${name}}`).join(String(value));
    return text;
  };
}

/** A label carried by a profile: either a plain string or one per language. */
export type LocalText = string | { en: string; uk?: string };

export function local(text: LocalText, lang: Lang): string {
  if (typeof text === "string") return text;
  return (lang === "uk" && text.uk) || text.en;
}
