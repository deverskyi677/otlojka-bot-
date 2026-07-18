# ============================================================
# ui_kit.py — цвета и премиум-эмодзи для инлайн-кнопок
# ============================================================
# Bot API 9.4 (февраль 2026) добавил в InlineKeyboardButton два новых поля:
#   style               -> "primary" (синий) | "success" (зелёный) | "danger" (красный)
#   icon_custom_emoji_id -> id премиум/кастомного эмодзи перед текстом кнопки
#
# Библиотека pyTelegramBotAPI (telebot) на момент написания ещё не знает
# про эти поля, поэтому передача style=... в обычный InlineKeyboardButton
# молча игнорируется при сборке JSON. Класс Btn ниже — тонкая обёртка,
# которая гарантированно кладёт оба поля в итоговый dict, отправляемый
# в Telegram. Сервер Bot API их прекрасно понимает уже сейчас.
#
# ВАЖНО про icon_custom_emoji_id: работает только если у владельца бота
# (аккаунт, который создавал бота в BotFather) есть активная подписка
# Telegram Premium, либо у бота куплены доп. юзернеймы на Fragment.
# Если условие не выполнено — Telegram просто не покажет иконку,
# ошибки не будет.

from telebot.types import InlineKeyboardButton as _BaseButton

VALID_STYLES = {"primary", "success", "danger"}


class Btn(_BaseButton):
    """
    Обёртка над InlineKeyboardButton с рабочими style / icon_custom_emoji_id.

    Пример:
        Btn("✅ Принять", callback_data="accept_1", style="success")
        Btn("Каталог", callback_data="buy_menu", style="primary",
            icon_custom_emoji_id="5343123456789012345")
    """

    def __init__(self, text, callback_data=None, url=None,
                 style=None, icon_custom_emoji_id=None, **kwargs):
        if style is not None and style not in VALID_STYLES:
            raise ValueError(f"style должен быть одним из {VALID_STYLES}, получено: {style!r}")

        super().__init__(text, callback_data=callback_data, url=url, **kwargs)
        self.style = style
        self.icon_custom_emoji_id = icon_custom_emoji_id

    def to_dict(self):
        d = super().to_dict()
        if self.style:
            d['style'] = self.style
        if self.icon_custom_emoji_id:
            d['icon_custom_emoji_id'] = self.icon_custom_emoji_id
        return d


# ------------------------------------------------------------
# Реестр "оформляемых" кнопок для админ-панели.
# Ключ -> человекочитаемое название, которое увидит админ в списке.
# Чтобы кнопка появилась в разделе "🎨 Дизайн кнопок", просто добавьте
# её сюда, а в коде постройте через button_kwargs(key, ...) — см. ниже.
# ------------------------------------------------------------
BUTTON_REGISTRY = {
    "buy":          "📱 Купить номер (главное меню)",
    "support":      "📞 Связь с поддержкой (главное меню)",
    "admin":        "🛠 Админ панель (главное меню)",
    "back":         "🔙 Назад (везде)",
    "accept_rules": "✅ Принять условия (юр. блок)",
    "wait_code":    "🔄 Я вернулся, жду код",
}

DEFAULT_STYLES = {
    "buy": "success",
    "support": "primary",
    "admin": "primary",
    "back": "danger",
    "accept_rules": "success",
    "wait_code": "success",
}


def get_style(data, key):
    """Достаёт сохранённый style для кнопки key из data['settings']['button_styles']."""
    styles = data.get('settings', {}).get('button_styles', {})
    entry = styles.get(key, {})
    return entry.get('style', DEFAULT_STYLES.get(key))


def get_icon(data, key):
    """Достаёт сохранённый icon_custom_emoji_id для кнопки key."""
    styles = data.get('settings', {}).get('button_styles', {})
    entry = styles.get(key, {})
    return entry.get('icon_custom_emoji_id')


def get_emoji_prefix(data, key):
    """Достаёт сохранённый обычный юникод-эмодзи (префикс к тексту)."""
    styles = data.get('settings', {}).get('button_styles', {})
    entry = styles.get(key, {})
    return entry.get('emoji_prefix', '')


def set_button_style(data, key, style=None, icon_custom_emoji_id=None, emoji_prefix=None):
    """Сохраняет настройки оформления кнопки key в data['settings']['button_styles']."""
    data.setdefault('settings', {}).setdefault('button_styles', {})
    entry = data['settings']['button_styles'].setdefault(key, {})
    if style is not None:
        entry['style'] = style
    if icon_custom_emoji_id is not None:
        entry['icon_custom_emoji_id'] = icon_custom_emoji_id
    if emoji_prefix is not None:
        entry['emoji_prefix'] = emoji_prefix


def styled_button(data, key, text, callback_data=None, url=None):
    """
    Собирает Btn с текстом (+ юникод-эмодзи префикс, если задан),
    цветом и премиум-иконкой — всё из data['settings']['button_styles'][key].
    """
    prefix = get_emoji_prefix(data, key)
    full_text = f"{prefix} {text}".strip() if prefix else text
    return Btn(
        full_text,
        callback_data=callback_data,
        url=url,
        style=get_style(data, key),
        icon_custom_emoji_id=get_icon(data, key),
    )


def extract_custom_emoji_id(message):
    """
    Если сообщение содержит кастомный/премиум эмодзи, возвращает его custom_emoji_id.
    Иначе — None (значит эмодзи обычный юникодный, unicode-символ уже есть в message.text).
    """
    entities = getattr(message, 'entities', None) or getattr(message, 'caption_entities', None)
    if not entities:
        return None
    for ent in entities:
        if getattr(ent, 'type', None) == 'custom_emoji':
            return getattr(ent, 'custom_emoji_id', None)
    return None


# ------------------------------------------------------------
# RICH TEXT: сохранение/отправка текста с сохранением форматирования
# (жирный, курсив, подчёркнутый, ссылки) и премиум/кастомных эмодзи.
#
# В тексте СООБЩЕНИЯ (в отличие от кнопок) премиум-эмодзи официально
# поддерживаются через MessageEntity типа custom_emoji — Telegram Bot API
# разрешает отправлять сообщения с такими entities без ограничений на
# Premium-статус самого бота (в отличие от icon_custom_emoji_id в кнопках).
#
# Идея: когда админ присылает новый текст, мы сохраняем не просто
# message.text, а ЕЩЁ и message.entities целиком (список форматирования).
# При отправке пользователю бот передаёт эти entities напрямую в
# send_message(..., entities=...), и Telegram отрисовывает ровно то же
# форматирование и эмодзи, что admin ввёл — 1 в 1.
# ------------------------------------------------------------

def save_rich_text(data, key, message):
    """Сохраняет текст сообщения вместе с его форматированием (entities)."""
    text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []
    data.setdefault('settings', {}).setdefault('rich_texts', {})
    data['settings']['rich_texts'][key] = {
        'text': text,
        'entities': [e.to_dict() for e in entities],
    }


def get_rich_text(data, key):
    """Возвращает (text, entities_dict_list) либо (None, None), если не задано."""
    rt = data.get('settings', {}).get('rich_texts', {}).get(key)
    if not rt:
        return None, None
    return rt['text'], rt['entities']


def send_rich_or_plain(bot, chat_id, data, key, fallback_text, **kwargs):
    """
    Отправляет сообщение: если для key сохранён rich_text (с форматированием
    админа) — шлёт его как есть (entities), иначе — обычный fallback_text.
    kwargs пробрасываются в bot.send_message (например reply_markup=...).
    """
    from telebot.types import MessageEntity

    text, entities_dicts = get_rich_text(data, key)
    if text is not None:
        entities = [MessageEntity.de_json(e) for e in entities_dicts] if entities_dicts else None
        return bot.send_message(chat_id, text, entities=entities, **kwargs)
    else:
        return bot.send_message(chat_id, fallback_text, parse_mode='HTML', **kwargs)


def _utf16_len(s):
    return len(s.encode('utf-16-le')) // 2


def format_rich(text, entities_dicts, **substitutions):
    """
    Аналог str.format(**substitutions), но аккуратно сдвигает offset у entities
    (жирный, курсив, премиум-эмодзи и т.д.), чтобы форматирование не съехало
    после подстановки {phone}/{reason}/... Работает в UTF-16 code units,
    как того требует Telegram Bot API.
    """
    import re

    entities = [dict(e) for e in (entities_dicts or [])]
    pattern = re.compile(r'\{(\w+)\}')

    result_parts = []
    last_end = 0
    utf16_delta = 0

    for m in pattern.finditer(text):
        key = m.group(1)
        if key not in substitutions:
            continue

        value = str(substitutions[key])
        placeholder_start_utf16 = _utf16_len(text[:m.start()]) + utf16_delta
        placeholder_len_utf16 = _utf16_len(m.group(0))
        value_len_utf16 = _utf16_len(value)
        delta = value_len_utf16 - placeholder_len_utf16

        result_parts.append(text[last_end:m.start()])
        result_parts.append(value)
        last_end = m.end()

        for e in entities:
            if e['offset'] >= placeholder_start_utf16 + placeholder_len_utf16:
                e['offset'] += delta

        utf16_delta += delta

    result_parts.append(text[last_end:])
    return "".join(result_parts), entities


def send_rich_template_or_plain(bot, chat_id, data, key, fallback_template, substitutions=None, **send_kwargs):
    """
    Как send_rich_or_plain, но с подстановкой {phone}/{reason}/... как в .format(),
    сохраняя форматирование и премиум-эмодзи, даже если они стоят после плейсхолдера.
    substitutions — dict значений для подстановки; send_kwargs (reply_markup и т.п.)
    пробрасываются в bot.send_message.
    """
    from telebot.types import MessageEntity

    substitutions = substitutions or {}
    text, entities_dicts = get_rich_text(data, key)
    if text is not None:
        new_text, new_entities_dicts = format_rich(text, entities_dicts, **substitutions)
        entities = [MessageEntity.de_json(e) for e in new_entities_dicts] if new_entities_dicts else None
        return bot.send_message(chat_id, new_text, entities=entities, **send_kwargs)
    else:
        return bot.send_message(chat_id, fallback_template.format(**substitutions), parse_mode='HTML', **send_kwargs)
