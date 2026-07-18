import telebot
import json
import os
import time
import re
import logging
from datetime import datetime
from telebot.types import InlineKeyboardMarkup
from ui_kit import (
    Btn as InlineKeyboardButton,  # все существующие style="..." заработают автоматически
    styled_button, get_style, get_icon, get_emoji_prefix,
    set_button_style, BUTTON_REGISTRY, extract_custom_emoji_id, VALID_STYLES,
    save_rich_text, get_rich_text, send_rich_or_plain, send_rich_template_or_plain,
)
from config import TOKEN, ADMIN_ID
from antiflood import is_flooding, should_warn, remaining_block_seconds
import functools

# ============================================================
# 0.1 ЗАЩИТА ОТ СПАМА/ФЛУДА
# ============================================================
def guarded(handler_func):
    """
    Оборачивает обработчик message_handler/callback_query_handler:
    если пользователь флудит (много сообщений/нажатий за короткое время),
    запрос молча игнорируется (с редким предупреждением), сам обработчик
    не выполняется. Админы не ограничиваются.
    """
    @functools.wraps(handler_func)
    def wrapper(update_obj, *args, **kwargs):
        user = getattr(update_obj, 'from_user', None)
        user_id = user.id if user else None

        if user_id and not is_admin(user_id):
            if is_flooding(user_id):
                if should_warn(user_id):
                    left = remaining_block_seconds(user_id)
                    text = f"⏳ Слишком много запросов. Подождите {left} сек. и попробуйте снова."
                    try:
                        if hasattr(update_obj, 'data'):  # CallbackQuery
                            bot.answer_callback_query(update_obj.id, text, show_alert=True)
                        else:  # Message
                            bot.send_message(update_obj.chat.id, text)
                    except Exception:
                        pass
                return

        return handler_func(update_obj, *args, **kwargs)
    return wrapper

# ============================================================
# 1. НАСТРОЙКА
# ============================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = str(ADMIN_ID)

# ============================================================
# 2. РАБОТА С ДАННЫМИ
# ============================================================
def load_data():
    if not os.path.exists('data.json'):
        default_data = {
            "catalog": [
                {"country": "Россия", "price": 500},
                {"country": "Украина", "price": 700},
                {"country": "Казахстан", "price": 400}
            ],
            "orders": [],
            "users": [],
            "accepted_users": [],
            "admins": [],
            "stats": {"visits": 0, "orders_total": 0, "orders_approved": 0, "orders_rejected": 0},
            "settings": {
                "welcome_text": "Добро пожаловать в SIALENS Физ!\n\n📱 Покупайте виртуальные номера легко и быстро.\n\n🔥 Мы предлагаем номера из разных стран по доступным ценам.",
                "legal_text": "📜 <b>Покупая номер в нашем боте, вы соглашаетесь с условиями:</b>\n\n• <a href='https://telegra.ph/Politika-konfidencialnosti-07-17-132'>Политика конфиденциальности</a>\n• <a href='https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17'>Публичная оферта</a>\n\nНажимая кнопку ниже, вы принимаете все условия.",
                "accept_button_text": "✅ Я принимаю условия",
                "approve_text": "✅ ВАШ ПЛАТЕЖ ОДОБРЕН!\n\n📱 Ваш номер: {phone}\n\n🔐 ИНСТРУКЦИЯ:\n1️⃣ Введите номер в Telegram\n2️⃣ Вернитесь в чат с ботом\n3️⃣ Нажмите кнопку «Я вернулся, жду код»\n4️⃣ Я пришлю вам код подтверждения\n\n📌 ПОСЛЕ ПОЛУЧЕНИЯ КОДА:\n• Установите двухфакторную аутентификацию\n• Привяжите почту для восстановления\n• Завершите все активные сессии",
                "reject_text": "❌ Ваш платеж отклонён.\n\nПричина: {reason}",
                "payment_link": "",
                "payment_phone": "+79103552521",
                "buttons": {
                    "buy": "Купить номер",
                    "support": "Связь с поддержкой",
                    "admin": "Админ панель",
                    "back": "Назад",
                    "wait_code": "Я вернулся, жду код"
                },
                "button_styles": {}
            }
        }
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(default_data, f, indent=2, ensure_ascii=False)
        logger.info("✅ Создан новый файл данных")
    
    with open('data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    try:
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("✅ Данные сохранены")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения: {e}")

data = load_data()
data.setdefault('pending', {})

def is_admin(user_id):
    user_id = str(user_id)
    return user_id == ADMIN_ID or user_id in data.get('admins', [])

def set_pending(admin_id, action, **payload):
    """Сохраняет, какого ввода мы ждём от конкретного админа — переживает
    несколько параллельных заказов и перезапуск бота (в отличие от
    register_next_step_handler, который хранится только в памяти и
    перетирается, если админ успевает нажать что-то ещё)."""
    data['pending'][str(admin_id)] = {'action': action, **payload}
    save_data(data)

def clear_pending(admin_id):
    data['pending'].pop(str(admin_id), None)
    save_data(data)

def get_pending(admin_id):
    return data['pending'].get(str(admin_id))


# ============================================================
# 3. /START — ГЛАВНЫЙ ОБРАБОТЧИК
# ============================================================
@bot.message_handler(commands=['start'])
@guarded
def start_handler(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or "нет_юзернейма"
    first_name = message.from_user.first_name or "Без_имени"
    
    logger.info(f"📥 /start от {user_id} - {first_name} (@{username})")
    
    if user_id not in data['users']:
        data['users'].append(user_id)
        data['stats']['visits'] = data['stats'].get('visits', 0) + 1
        save_data(data)
        logger.info(f"🆕 Новый пользователь: {user_id}")
    
    if user_id not in data.get('accepted_users', []):
        show_legal_agreement(message)
        return
    
    show_main_menu(message)

# ============================================================
# 4. ЮРИДИЧЕСКИЙ БЛОК
# ============================================================
def show_legal_agreement(message):
    legal = data['settings']
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("Политика конфиденциальности", url="https://telegra.ph/Politika-konfidencialnosti-07-17-132"),
        InlineKeyboardButton("Публичная оферта", url="https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17")
    )
    markup.add(styled_button(
        data, "accept_rules",
        data['settings'].get('accept_button_text', '✅ Я принимаю условия'),
        callback_data="accept_rules"
    ))
    
    send_rich_or_plain(
        bot, message.chat.id, data, 'legal',
        data['settings'].get('legal_text', '📜 Пожалуйста, ознакомьтесь с условиями и примите их.'),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "accept_rules")
@guarded
def accept_rules(call):
    user_id = str(call.from_user.id)
    logger.info(f"✅ Пользователь {user_id} принял правила")
    
    if user_id not in data.get('accepted_users', []):
        data['accepted_users'].append(user_id)
        save_data(data)
    
    bot.answer_callback_query(call.id, "✅ Условия приняты!")
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    show_main_menu(call.message)

# ============================================================
# 5. ГЛАВНОЕ МЕНЮ
# ============================================================
def show_main_menu(message):
    buttons = data['settings']['buttons']
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        styled_button(data, "buy", buttons['buy'], callback_data="buy_menu"),
        styled_button(data, "support", buttons['support'], url="https://t.me/deverskyi")
    )
    
    if is_admin(message.from_user.id):
        markup.add(styled_button(data, "admin", buttons['admin'], callback_data="admin_panel"))
    
    send_rich_or_plain(
        bot, message.chat.id, data,
        'welcome', data['settings']['welcome_text'],
        reply_markup=markup
    )

# ============================================================
# 6. КНОПКА: НАЗАД
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
@guarded
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    show_main_menu(call.message)

# ============================================================
# 7. ПОКУПКА НОМЕРА
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "buy_menu")
@guarded
def buy_menu(call):
    bot.answer_callback_query(call.id)
    logger.info(f"🛒 Покупка: {call.from_user.id}")
    
    if not data.get('catalog'):
        bot.send_message(call.message.chat.id, "❌ Нет доступных номеров")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(
            f"{item['country']} - {item['price']}₽",
            callback_data=f"buy_{idx}",
            style="success"
        ))
    markup.add(styled_button(data, "back", data['settings']['buttons']['back'], callback_data="back_to_menu"))
    
    bot.edit_message_text(
        "🌍 Выберите страну для покупки номера:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_') and call.data != 'buy_menu' and call.data.split('_')[1].isdigit())
@guarded
def buy_selected(call):
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    item = data['catalog'][idx]
    logger.info(f"💳 Выбор: {item['country']} - {item['price']}₽")

    payment_link = data['settings'].get('payment_link', '').strip()
    payment_phone = data['settings'].get('payment_phone', '+79103552521')

    text = (
        f"💳 К оплате: <b>{item['price']}₽</b>\n\n"
        f"📸 После оплаты пришлите СКРИНШОТ (чётко видны сумма и дата).\n\n"
        f"⚠️ Сумму переводите вручную — она в ссылке не проставляется автоматически."
    )

    if payment_link:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(f"Оплатить {item['price']}₽", url=payment_link, style="success"))
        msg = bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=markup)
    else:
        # Ссылка ещё не настроена админом — fallback на номер телефона
        msg = bot.send_message(
            call.message.chat.id,
            text + f"\n\n📱 Переведите на номер: <b>{payment_phone}</b>",
            parse_mode='HTML'
        )

    bot.register_next_step_handler(msg, lambda m: handle_screenshot(m, idx))

def handle_screenshot(msg, idx):
    if not msg.photo:
        bot.send_message(msg.chat.id, "❌ Это не фото. Пришлите скриншот.")
        bot.register_next_step_handler(msg, lambda m: handle_screenshot(m, idx))
        return
    
    order = {
        "id": len(data['orders']) + 1,
        "user_id": str(msg.from_user.id),
        "first_name": msg.from_user.first_name or "Без_имени",
        "username": msg.from_user.username or "нет_юзернейма",
        "country": data['catalog'][idx]['country'],
        "price": data['catalog'][idx]['price'],
        "screenshot": msg.photo[-1].file_id,
        "status": "waiting_approval",
        "phone": None,
        "code_waiting": False,
        "date": time.time()
    }
    data['orders'].append(order)
    data['stats']['orders_total'] = data['stats'].get('orders_total', 0) + 1
    save_data(data)
    
    logger.info(f"📦 Заказ #{order['id']} создан")
    bot.send_message(msg.chat.id, "✅ Скрин отправлен на проверку. Ожидайте уведомления.")
    
    # Отправляем заказ всем админам
    order_idx = len(data['orders']) - 1
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Принять", callback_data=f"accept_{order_idx}", style="success"),
        InlineKeyboardButton("Отклонить", callback_data=f"reject_{order_idx}", style="danger")
    )
    markup.add(InlineKeyboardButton("Написать", callback_data=f"reply_{order_idx}", style="primary"))
    
    admin_ids = [ADMIN_ID] + data.get('admins', [])
    for admin_id in admin_ids:
        try:
            bot.send_photo(
                admin_id,
                order['screenshot'],
                f"🆕 НОВЫЙ ЗАКАЗ #{order['id']}\n\n"
                f"👤 {order['first_name']} (@{order['username']})\n"
                f"🆔 {order['user_id']}\n"
                f"🌍 {order['country']}\n"
                f"💰 {order['price']}₽\n"
                f"📅 {time.ctime(order['date'])}\n\n"
                f"⬇️ Используйте кнопки ниже для обработки:",
                reply_markup=markup
            )
            logger.info(f"📨 Заказ #{order['id']} отправлен админу {admin_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")

# ============================================================
# 8. АДМИН ПАНЕЛЬ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
@guarded
def admin_panel(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    
    bot.answer_callback_query(call.id)
    logger.info(f"🛠 Админ панель: {call.from_user.id}")
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Статистика", callback_data="admin_stats", style="primary"),
        InlineKeyboardButton("Заказы", callback_data="admin_orders", style="primary"),
        InlineKeyboardButton("Пользователи", callback_data="admin_users", style="primary"),
        InlineKeyboardButton("Добавить номер", callback_data="admin_add_number", style="success"),
        InlineKeyboardButton("Удалить номер", callback_data="admin_delete_number", style="danger"),
        InlineKeyboardButton("Текст приветствия", callback_data="admin_edit_welcome", style="primary"),
        InlineKeyboardButton("Тексты бота", callback_data="admin_edit_texts", style="primary"),
        InlineKeyboardButton("Рассылка", callback_data="admin_broadcast", style="primary")
    )
    
    markup.add(InlineKeyboardButton("Дизайн кнопок", callback_data="admin_design", style="success"))

    if str(call.from_user.id) == ADMIN_ID:
        markup.add(
            InlineKeyboardButton("Управление админами", callback_data="admin_manage_admins", style="danger"),
            InlineKeyboardButton("Юридические документы", callback_data="admin_legal", style="primary")
        )
    
    markup.add(InlineKeyboardButton("Выход", callback_data="back_to_menu", style="danger"))
    
    bot.edit_message_text(
        "🛠 АДМИН ПАНЕЛЬ\n\nЗдесь вы можете управлять ботом: просматривать статистику, обрабатывать заказы, редактировать содержимое.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# ============================================================
# 8.1 ДИЗАЙН КНОПОК (ЦВЕТ + ПРЕМИУМ-ЭМОДЗИ)
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_design")
@guarded
def admin_design(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return

    bot.answer_callback_query(call.id)

    markup = InlineKeyboardMarkup(row_width=1)
    for key, label in BUTTON_REGISTRY.items():
        style = get_style(data, key)
        icon = "🖼" if get_icon(data, key) else ""
        dot = {"success": "🟢", "primary": "🔵", "danger": "🔴"}.get(style, "⚪️")
        markup.add(InlineKeyboardButton(
            f"{dot} {label} {icon}",
            callback_data=f"design_pick_{key}",
            style="primary"
        ))
    markup.add(InlineKeyboardButton("Назад", callback_data="admin_panel", style="danger"))

    bot.edit_message_text(
        "🎨 ДИЗАЙН КНОПОК\n\n"
        "🟢 зелёная (success) · 🔵 синяя (primary) · 🔴 красная (danger) · ⚪️ без цвета\n"
        "🖼 — установлен премиум-эмодзи\n\n"
        "Выберите кнопку для настройки:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('design_pick_'))
@guarded
def design_pick(call):
    if not is_admin(call.from_user.id):
        return

    key = call.data.split('design_pick_', 1)[1]
    bot.answer_callback_query(call.id)

    label = BUTTON_REGISTRY.get(key, key)
    current_style = get_style(data, key) or "нет"
    current_emoji = get_emoji_prefix(data, key) or "нет"
    has_icon = "да ✅" if get_icon(data, key) else "нет"

    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("Зелёный", callback_data=f"design_style_{key}_success", style="success"),
        InlineKeyboardButton("Синий", callback_data=f"design_style_{key}_primary", style="primary"),
        InlineKeyboardButton("Красный", callback_data=f"design_style_{key}_danger", style="danger")
    )
    markup.add(InlineKeyboardButton("Убрать цвет", callback_data=f"design_style_{key}_none", style="primary"))
    markup.add(InlineKeyboardButton("Задать эмодзи", callback_data=f"design_emoji_{key}", style="success"))
    markup.add(InlineKeyboardButton("Назад", callback_data="admin_design", style="danger"))

    bot.edit_message_text(
        f"🎨 Настройка кнопки: {label}\n\n"
        f"Текущий цвет: {current_style}\n"
        f"Текущий эмодзи-префикс: {current_emoji}\n"
        f"Премиум-эмодзи установлен: {has_icon}\n\n"
        f"⚠️ Премиум-эмодзи покажется только если у владельца бота есть\n"
        f"активная подписка Telegram Premium.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('design_style_'))
@guarded
def design_style(call):
    if not is_admin(call.from_user.id):
        return

    # Формат callback_data: design_style_<key>_<style>. key может содержать '_', поэтому парсим с конца.
    rest = call.data[len("design_style_"):]
    key, style = rest.rsplit('_', 1)

    style_value = None if style == "none" else style
    set_button_style(data, key, style=style_value)
    save_data(data)

    logger.info(f"🎨 Цвет кнопки {key} изменён на {style_value}")
    bot.answer_callback_query(call.id, "✅ Цвет обновлён!")
    design_pick(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith('design_emoji_'))
@guarded
def design_emoji(call):
    if not is_admin(call.from_user.id):
        return

    key = call.data[len("design_emoji_"):]
    bot.answer_callback_query(call.id)

    msg = bot.send_message(
        call.message.chat.id,
        "😀 Пришлите ОДНО сообщение с нужным эмодзи:\n\n"
        "• Обычный юникод-эмодзи (например 🔥) — станет префиксом текста кнопки.\n"
        "• Премиум/кастомный эмодзи (если у вас есть Telegram Premium) — "
        "будет показан отдельной иконкой на кнопке.\n\n"
        "Чтобы убрать эмодзи, отправьте: -"
    )
    bot.register_next_step_handler(msg, lambda m: design_emoji_save(m, key, call.message.chat.id, call.message.message_id))


def design_emoji_save(msg, key, chat_id, message_id):
    text = (msg.text or msg.caption or "").strip()

    if text == "-":
        set_button_style(data, key, icon_custom_emoji_id="", emoji_prefix="")
        save_data(data)
        bot.send_message(msg.chat.id, "✅ Эмодзи убран.")
    else:
        custom_id = extract_custom_emoji_id(msg)
        if custom_id:
            set_button_style(data, key, icon_custom_emoji_id=custom_id, emoji_prefix="")
            save_data(data)
            bot.send_message(
                msg.chat.id,
                "✅ Премиум-эмодзи сохранён.\n\n"
                "Если он не появится на кнопке — значит у владельца бота нет "
                "активной подписки Telegram Premium (это ограничение Telegram, не бота)."
            )
        else:
            set_button_style(data, key, emoji_prefix=text, icon_custom_emoji_id="")
            save_data(data)
            bot.send_message(msg.chat.id, f"✅ Эмодзи-префикс сохранён: {text}")

    logger.info(f"😀 Эмодзи кнопки {key} обновлён")
    time.sleep(0.3)
    admin_design_after(msg)


def admin_design_after(msg):
    markup = InlineKeyboardMarkup(row_width=1)
    for key, label in BUTTON_REGISTRY.items():
        style = get_style(data, key)
        icon = "🖼" if get_icon(data, key) else ""
        dot = {"success": "🟢", "primary": "🔵", "danger": "🔴"}.get(style, "⚪️")
        markup.add(InlineKeyboardButton(
            f"{dot} {label} {icon}",
            callback_data=f"design_pick_{key}",
            style="primary"
        ))
    markup.add(InlineKeyboardButton("Назад", callback_data="admin_panel", style="danger"))

    bot.send_message(
        msg.chat.id,
        "🎨 ДИЗАЙН КНОПОК — обновлено.\n\nВыберите кнопку для настройки:",
        reply_markup=markup
    )

# ============================================================
# 9. СТАТИСТИКА
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
@guarded
def admin_stats(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    
    total_users = len(data.get('users', []))
    accepted_users = len(data.get('accepted_users', []))
    total_visits = data['stats'].get('visits', 0)
    total_orders = len(data.get('orders', []))
    pending_orders = len([o for o in data.get('orders', []) if o['status'] == 'waiting_approval'])
    approved_orders = len([o for o in data.get('orders', []) if o['status'] == 'approved'])
    rejected_orders = len([o for o in data.get('orders', []) if o['status'] == 'rejected'])
    total_catalog = len(data.get('catalog', []))
    
    text = f"📊 СТАТИСТИКА БОТА\n\n"
    text += f"━━━━━━━━━━━━━━━━━\n"
    text += f"👤 Пользователи:\n"
    text += f"   • Всего: {total_users}\n"
    text += f"   • Приняли правила: {accepted_users}\n"
    text += f"   • Визитов: {total_visits}\n\n"
    text += f"📦 Заказы:\n"
    text += f"   • Всего: {total_orders}\n"
    text += f"   • Ожидают: {pending_orders}\n"
    text += f"   • Одобрено: {approved_orders}\n"
    text += f"   • Отклонено: {rejected_orders}\n\n"
    text += f"🌍 Каталог:\n"
    text += f"   • Номеров: {total_catalog}\n"
    text += f"━━━━━━━━━━━━━━━━━\n"
    text += f"🤖 Бот работает стабильно"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Обновить", callback_data="admin_stats", style="primary"))
    markup.add(InlineKeyboardButton("Назад", callback_data="admin_panel", style="primary"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# 10. ЗАКАЗЫ (АДМИН)
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_orders")
@guarded
def admin_orders(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    
    if not data.get('orders'):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Назад", callback_data="admin_panel", style="primary"))
        bot.edit_message_text("📭 Нет заказов", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for order in data['orders'][-15:]:
        idx = data['orders'].index(order)
        status_emoji = "⏳" if order['status'] == 'waiting_approval' else "✅" if order['status'] == 'approved' else "❌"
        markup.add(InlineKeyboardButton(
            f"#{order['id']} | {order['country']} | {order['price']}₽ {status_emoji}",
            callback_data=f"order_detail_{idx}",
            style="primary"
        ))
    
    markup.add(InlineKeyboardButton("Назад", callback_data="admin_panel", style="primary"))
    
    bot.edit_message_text(
        "📋 ПОСЛЕДНИЕ ЗАКАЗЫ (15):\n\n⏳ - ожидает | ✅ - одобрен | ❌ - отклонён",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('order_detail_'))
@guarded
def order_detail(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[2])
    order = data['orders'][idx]
    
    status_map = {
        "waiting_approval": "⏳ Ожидает проверки",
        "approved": "✅ Одобрен",
        "rejected": "❌ Отклонён",
        "code_sent": "📨 Код отправлен"
    }
    
    markup = InlineKeyboardMarkup(row_width=2)
    if order['status'] == 'waiting_approval':
        markup.add(
            InlineKeyboardButton("Принять", callback_data=f"accept_{idx}", style="success"),
            InlineKeyboardButton("Отклонить", callback_data=f"reject_{idx}", style="danger")
        )
        markup.add(InlineKeyboardButton("Написать", callback_data=f"reply_{idx}", style="primary"))
    
    if order['status'] == 'approved' and not order['code_waiting']:
        markup.add(InlineKeyboardButton("Отправить код", callback_data=f"send_code_{idx}", style="success"))
    
    markup.add(InlineKeyboardButton("Назад", callback_data="admin_orders", style="primary"))
    
    text = f"📦 ЗАКАЗ #{order['id']}\n\n"
    text += f"👤 {order['first_name']} (@{order['username']})\n"
    text += f"🆔 {order['user_id']}\n"
    text += f"🌍 Страна: {order['country']}\n"
    text += f"💰 Цена: {order['price']}₽\n"
    text += f"📅 Дата: {time.ctime(order['date'])}\n"
    text += f"📊 Статус: {status_map.get(order['status'], order['status'])}\n"
    text += f"📱 Номер: {order['phone'] or 'Не выдан'}\n"
    text += f"🔄 Ожидает код: {'Да' if order['code_waiting'] else 'Нет'}"
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# 11. ПРИНЯТЬ ЗАКАЗ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_') and call.data != 'accept_rules' and call.data.split('_')[1].isdigit())
@guarded
def accept_order(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    order = data['orders'][idx]
    
    if order['status'] != 'waiting_approval':
        bot.send_message(call.message.chat.id, "❌ Заказ уже обработан")
        return
    
    logger.info(f"✅ Принятие заказа #{order['id']} от {call.from_user.id}")
    
    msg = bot.send_message(call.message.chat.id, "📱 Введите номер телефона для выдачи:")
    set_pending(call.from_user.id, 'set_phone', idx=idx, chat_id=call.message.chat.id, message_id=call.message.message_id)

def set_phone(msg, idx, chat_id, message_id):
    phone = msg.text.strip()
    if not phone:
        bot.send_message(msg.chat.id, "❌ Номер не может быть пустым")
        return
    
    order = data['orders'][idx]
    order['phone'] = phone
    order['status'] = 'approved'
    data['stats']['orders_approved'] = data['stats'].get('orders_approved', 0) + 1
    save_data(data)
    
    logger.info(f"✅ Заказ #{order['id']} принят, номер {phone}")
    
    bot.edit_message_text(
        f"✅ Заказ #{order['id']} принят.\n📱 Номер {phone} выдан.",
        chat_id,
        message_id
    )
    
    # Отправляем пользователю
    user_id = order['user_id']
    try:
        markup = InlineKeyboardMarkup()
        markup.add(styled_button(
            data, "wait_code",
            data['settings']['buttons']['wait_code'],
            callback_data=f"wait_code_{idx}"
        ))
        
        send_rich_template_or_plain(
            bot, user_id, data, 'approve',
            data['settings'].get('approve_text', ''),
            substitutions={'phone': phone},
            reply_markup=markup
        )
        bot.send_message(msg.chat.id, f"✅ Пользователю отправлен номер: {phone}")
        logger.info(f"📨 Номер {phone} отправлен пользователю {user_id}")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка отправки пользователю: {e}")
        logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")

# ============================================================
# 12. ОТКЛОНИТЬ ЗАКАЗ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
@guarded
def reject_order(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    order = data['orders'][idx]
    
    if order['status'] != 'waiting_approval':
        bot.send_message(call.message.chat.id, "❌ Заказ уже обработан")
        return
    
    logger.info(f"❌ Отклонение заказа #{order['id']} от {call.from_user.id}")
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите причину отказа:")
    set_pending(call.from_user.id, 'set_reject', idx=idx, chat_id=call.message.chat.id, message_id=call.message.message_id)

def set_reject(msg, idx, chat_id, message_id):
    reason = msg.text.strip()
    order = data['orders'][idx]
    order['status'] = 'rejected'
    data['stats']['orders_rejected'] = data['stats'].get('orders_rejected', 0) + 1
    save_data(data)
    
    logger.info(f"❌ Заказ #{order['id']} отклонён, причина: {reason}")
    
    bot.edit_message_text(
        f"❌ Заказ #{order['id']} отклонён.\nПричина: {reason}",
        chat_id,
        message_id
    )
    
    try:
        send_rich_template_or_plain(
            bot, order['user_id'], data, 'reject',
            data['settings'].get('reject_text', ''),
            substitutions={'reason': reason}
        )
        logger.info(f"📨 Отказ отправлен пользователю {order['user_id']}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки отказа: {e}")

# ============================================================
# 13. НАПИСАТЬ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
@guarded
def reply_to_user(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    logger.info(f"✏️ Написать пользователю: заказ #{data['orders'][idx]['id']}")
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите сообщение для покупателя:")
    set_pending(call.from_user.id, 'reply_to_user', idx=idx)

def send_reply(msg, idx):
    user_id = data['orders'][idx]['user_id']
    try:
        bot.send_message(user_id, f"📩 Сообщение от администратора:\n\n{msg.text}")
        bot.send_message(msg.chat.id, "✅ Сообщение отправлено")
        logger.info(f"📨 Сообщение отправлено пользователю {user_id}")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка: {e}")
        logger.error(f"❌ Ошибка отправки сообщения: {e}")

# ============================================================
# 14. ОТПРАВИТЬ КОД
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('send_code_'))
@guarded
def send_code(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[2])
    logger.info(f"📨 Отправить код: заказ #{data['orders'][idx]['id']}")
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите код подтверждения:")
    set_pending(call.from_user.id, 'send_code', idx=idx)

def send_code_to_user(msg, idx):
    code = msg.text.strip()
    order = data['orders'][idx]
    order['code_waiting'] = False
    order['status'] = 'code_sent'
    save_data(data)
    
    try:
        bot.send_message(order['user_id'], f"📨 Ваш код подтверждения:\n\n<b>{code}</b>", parse_mode='HTML')
        bot.send_message(msg.chat.id, "✅ Код отправлен")
        logger.info(f"📨 Код отправлен пользователю {order['user_id']}")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка: {e}")
        logger.error(f"❌ Ошибка отправки кода: {e}")

# ============================================================
# 15. ЖДУ КОД
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('wait_code_'))
@guarded
def wait_code(call):
    bot.answer_callback_query(call.id, "🔄 Ожидайте код от администратора")
    idx = int(call.data.split('_')[2])
    
    order = data['orders'][idx]
    order['code_waiting'] = True
    save_data(data)
    
    logger.info(f"🔄 Пользователь ждёт код: заказ #{order['id']}")
    
    bot.send_message(call.message.chat.id, "✅ Вы уведомлены. Администратор отправит код в этот чат.")
    
    admin_ids = [ADMIN_ID] + data.get('admins', [])
    for admin_id in admin_ids:
        try:
            bot.send_message(admin_id, f"🔄 Пользователь @{order['username']} ждёт код для заказа #{order['id']}")
        except:
            pass

# ============================================================
# 16. ДОБАВИТЬ НОМЕР
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_number")
@guarded
def add_number(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    logger.info(f"➕ Добавление номера: {call.from_user.id}")
    
    msg = bot.send_message(
        call.message.chat.id,
        "✏️ Введите страну и цену\n\n"
        "📌 Форматы:\n"
        "• Россия - 500\n"
        "• США-1500\n"
        "• Германия 700\n\n"
        "💡 Пример: Россия - 500"
    )
    bot.register_next_step_handler(msg, lambda m: add_catalog_item(m, call.message.chat.id, call.message.message_id))

def add_catalog_item(msg, chat_id, message_id):
    try:
        text = msg.text.strip()
        parts = re.split(r'[-–—]', text)
        
        if len(parts) == 2:
            country = parts[0].strip()
            price = int(re.sub(r'[^0-9]', '', parts[1].strip()))
        else:
            words = text.split()
            if len(words) >= 2:
                country = ' '.join(words[:-1])
                price = int(re.sub(r'[^0-9]', '', words[-1]))
            else:
                raise ValueError("Неверный формат")
        
        if price <= 0:
            raise ValueError("Цена должна быть больше 0")
        
        data['catalog'].append({"country": country, "price": price})
        save_data(data)
        
        logger.info(f"✅ Добавлен номер: {country} - {price}₽")
        
        bot.edit_message_text(
            f"✅ Номер успешно добавлен!\n\n"
            f"🌍 Страна: {country}\n"
            f"💰 Цена: {price}₽\n"
            f"📦 Всего в каталоге: {len(data['catalog'])}",
            chat_id,
            message_id
        )
        time.sleep(0.5)
        admin_panel_after(msg)
        
    except ValueError as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка: {e}\n\nИспользуйте формат:\n• Россия - 500\n• США-1500")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Неизвестная ошибка: {e}")

def admin_panel_after(msg):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Статистика", callback_data="admin_stats", style="primary"),
        InlineKeyboardButton("Заказы", callback_data="admin_orders", style="primary"),
        InlineKeyboardButton("Пользователи", callback_data="admin_users", style="primary"),
        InlineKeyboardButton("Добавить номер", callback_data="admin_add_number", style="success"),
        InlineKeyboardButton("Удалить номер", callback_data="admin_delete_number", style="danger"),
        InlineKeyboardButton("Текст приветствия", callback_data="admin_edit_welcome", style="primary"),
        InlineKeyboardButton("Тексты бота", callback_data="admin_edit_texts", style="primary"),
        InlineKeyboardButton("Рассылка", callback_data="admin_broadcast", style="primary")
    )
    if str(msg.from_user.id) == ADMIN_ID:
        markup.add(
            InlineKeyboardButton("Управление админами", callback_data="admin_manage_admins", style="danger"),
            InlineKeyboardButton("Юридические документы", callback_data="admin_legal", style="primary")
        )
    markup.add(InlineKeyboardButton("Выход", callback_data="back_to_menu", style="danger"))
    
    bot.send_message(msg.chat.id, "🛠 АДМИН ПАНЕЛЬ", reply_markup=markup)

# ============================================================
# 17. УДАЛИТЬ НОМЕР
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_number")
@guarded
def delete_number(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    
    if not data.get('catalog'):
        bot.send_message(call.message.chat.id, "❌ Нет номеров для удаления")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(
            f"{item['country']} - {item['price']}₽",
            callback_data=f"delete_catalog_{idx}",
            style="danger"
        ))
    markup.add(InlineKeyboardButton("Назад", callback_data="admin_panel", style="primary"))
    
    bot.edit_message_text(
        "🗑 ВЫБЕРИТЕ НОМЕР ДЛЯ УДАЛЕНИЯ:\n\n"
        f"📦 Всего номеров: {len(data['catalog'])}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_catalog_'))
@guarded
def delete_catalog_item(call):
    if not is_admin(call.from_user.id):
        return
    
    idx = int(call.data.split('_')[2])
    item = data['catalog'].pop(idx)
    save_data(data)
    
    logger.info(f"🗑 Удалён номер: {item['country']} - {item['price']}₽")
    
    bot.answer_callback_query(call.id, f"✅ Удалено: {item['country']}")
    admin_panel_after(call)

# ============================================================
# 18. ТЕКСТ ПРИВЕТСТВИЯ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_welcome")
@guarded
def edit_welcome(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    logger.info(f"✏️ Редактирование приветствия: {call.from_user.id}")
    
    current = data['settings'].get('welcome_text', '')
    msg = bot.send_message(
        call.message.chat.id,
        f"✏️ Введите НОВЫЙ ТЕКСТ ПРИВЕТСТВИЯ:\n\n"
        f"📌 Текущий текст:\n{current}\n\n"
        f"💡 Можно использовать жирный/курсив/подчёркнутый через обычное "
        f"форматирование Telegram (выделите текст и нажмите Bold/Italic в поле ввода), "
        f"а также премиум-эмодзи — вставьте его прямо в сообщение. "
        f"Всё сохранится ровно так, как вы напишете."
    )
    set_pending(call.from_user.id, 'set_welcome', chat_id=call.message.chat.id, message_id=call.message.message_id)

def set_welcome(msg, chat_id, message_id):
    save_rich_text(data, 'welcome', msg)
    data['settings']['welcome_text'] = msg.text or msg.caption or ''  # текстовый fallback для мест без rich-рендера
    save_data(data)
    
    logger.info(f"✅ Приветствие обновлено: {msg.from_user.id}")
    
    bot.send_message(
        chat_id,
        f"✅ Текст приветствия обновлён (с форматированием и эмодзи, как вы ввели)!"
    )

# ============================================================
# 19. ТЕКСТЫ БОТА
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_texts")
@guarded
def admin_edit_texts(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("Текст одобрения", callback_data="edit_text_approve", style="primary"),
        InlineKeyboardButton("Текст отказа", callback_data="edit_text_reject", style="primary"),
        InlineKeyboardButton("Текст правил", callback_data="edit_text_legal", style="primary"),
        InlineKeyboardButton("Текст кнопки правил", callback_data="edit_text_accept_btn", style="primary"),
        InlineKeyboardButton("Ссылка/номер для оплаты", callback_data="admin_payment_link", style="success"),
        InlineKeyboardButton("Назад", callback_data="admin_panel", style="primary")
    )
    
    bot.edit_message_text(
        "🛠 РЕДАКТИРОВАНИЕ ТЕКСТОВ БОТА\n\n"
        "Выберите, какой текст хотите изменить:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_payment_link")
@guarded
def admin_payment_link(call):
    if not is_admin(call.from_user.id):
        return

    bot.answer_callback_query(call.id)

    current_link = data['settings'].get('payment_link', '')
    current_phone = data['settings'].get('payment_phone', '+79103552521')

    text = (
        "💳 ОПЛАТА\n\n"
        f"🔗 Текущая ссылка на оплату (СБП):\n{current_link or '❌ не задана'}\n\n"
        f"📱 Резервный номер для перевода (если ссылка не задана):\n{current_phone}\n\n"
        "Как получить личную СБП-ссылку:\n"
        "СберБанк Онлайн → профиль → «Получить перевод» / «Мои реквизиты» "
        "→ «Ссылка или QR-код для перевода мне» → скопировать ссылку.\n\n"
        "Пришлите новую ссылку следующим сообщением (или «-», чтобы убрать и вернуться к номеру телефона):"
    )

    msg = bot.send_message(call.message.chat.id, text)
    bot.register_next_step_handler(msg, set_payment_link)


def set_payment_link(msg):
    if not is_admin(msg.from_user.id):
        return

    value = msg.text.strip()

    if value == "-":
        data['settings']['payment_link'] = ""
        save_data(data)
        bot.send_message(msg.chat.id, "✅ Ссылка убрана. Будет использоваться номер телефона.")
    elif value.startswith("http://") or value.startswith("https://"):
        data['settings']['payment_link'] = value
        save_data(data)
        bot.send_message(msg.chat.id, f"✅ Ссылка на оплату сохранена:\n{value}")
    else:
        # Если прислали не ссылку — считаем, что это резервный номер телефона
        data['settings']['payment_phone'] = value
        save_data(data)
        bot.send_message(msg.chat.id, f"✅ Резервный номер для перевода сохранён: {value}")

    logger.info(f"💳 Реквизиты оплаты обновлены админом {msg.from_user.id}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_text_'))
@guarded
def edit_text_field(call):
    if not is_admin(call.from_user.id):
        return
    
    key = call.data.split('_')[2]
    mapping = {
        "approve": "approve_text",
        "reject": "reject_text",
        "legal": "legal_text",
        "accept": "accept_button_text"
    }
    
    field = mapping.get(key, key)
    current = data['settings'].get(field, '')
    
    bot.answer_callback_query(call.id, "✏️ Введите новый текст")
    
    names = {
        "approve": "текст одобрения",
        "reject": "текст отказа",
        "legal": "юридический текст",
        "accept": "текст кнопки принятия"
    }
    
    msg = bot.send_message(
        call.message.chat.id,
        f"✏️ Введите НОВЫЙ {names.get(key, 'текст').upper()}:\n\n"
        f"📌 Текущий:\n{current}\n\n"
        f"💡 Используйте {{phone}} для подстановки номера (в тексте одобрения)\n"
        f"💡 Используйте {{reason}} для подстановки причины (в тексте отказа)\n"
        f"💡 Форматирование (жирный/курсив) и премиум-эмодзи сохранятся именно так, как вы напишете"
    )
    set_pending(call.from_user.id, 'set_text_field', field=field, rich_key=key, chat_id=call.message.chat.id, message_id=call.message.message_id)

def set_text_field(msg, field, rich_key, chat_id, message_id):
    save_rich_text(data, rich_key, msg)
    data['settings'][field] = msg.text or msg.caption or ''
    save_data(data)
    
    logger.info(f"✅ Текст обновлён: {field} от {msg.from_user.id}")
    
    bot.send_message(chat_id, "✅ Текст обновлён (с форматированием и эмодзи, как вы ввели)!")

# ============================================================
# 20. ПОЛЬЗОВАТЕЛИ (АДМИН)
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_users")
@guarded
def admin_users(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    
    users = data.get('users', [])
    accepted = data.get('accepted_users', [])
    
    text = "👥 СПИСОК ПОЛЬЗОВАТЕЛЕЙ:\n\n"
    text += f"━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Всего: {len(users)}\n"
    text += f"✅ Приняли правила: {len(accepted)}\n"
    text += f"━━━━━━━━━━━━━━━━━\n\n"
    
    for i, user_id in enumerate(users[-20:]):
        is_accepted = "✅" if user_id in accepted else "⬜"
        text += f"{is_accepted} {user_id}\n"
    
    if len(users) > 20:
        text += f"\n... и ещё {len(users) - 20} пользователей"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Назад", callback_data="admin_panel", style="primary"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# 21. РАССЫЛКА
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
@guarded
def broadcast(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    logger.info(f"📢 Рассылка: {call.from_user.id}")
    
    msg = bot.send_message(
        call.message.chat.id,
        "📢 Введите текст для РАССЫЛКИ:\n\n"
        "💡 Сообщение будет отправлено ВСЕМ пользователям бота.\n"
        "⚠️ Отправьте текст, и начнётся рассылка."
    )
    bot.register_next_step_handler(msg, lambda m: send_broadcast(m, call.message.chat.id, call.message.message_id))

def send_broadcast(msg, chat_id, message_id):
    text = msg.text
    users = data.get('users', [])
    total = len(users)
    sent = 0
    failed = 0
    
    bot.edit_message_text(
        f"📢 Начинаю рассылку...\n\n"
        f"👤 Всего пользователей: {total}\n"
        f"⏳ Отправка...",
        chat_id,
        message_id
    )
    
    for user_id in users:
        try:
            bot.send_message(user_id, f"📢 {text}")
            sent += 1
            time.sleep(0.05)
        except Exception as e:
            failed += 1
            logger.error(f"❌ Ошибка отправки {user_id}: {e}")
    
    logger.info(f"✅ Рассылка завершена: отправлено {sent}, не доставлено {failed}")
    
    bot.edit_message_text(
        f"✅ РАССЫЛКА ЗАВЕРШЕНА!\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}\n"
        f"👤 Всего: {total}",
        chat_id,
        message_id
    )

# ============================================================
# 22. УПРАВЛЕНИЕ АДМИНАМИ (ТОЛЬКО ГЛАВНЫЙ)
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_manage_admins")
@guarded
def admin_manage_admins(call):
    if str(call.from_user.id) != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id)
    
    admins = data.get('admins', [])
    
    text = "👑 УПРАВЛЕНИЕ АДМИНАМИ\n\n"
    text += f"━━━━━━━━━━━━━━━━━\n"
    text += f"👑 Главный админ: {ADMIN_ID}\n"
    text += f"━━━━━━━━━━━━━━━━━\n\n"
    text += "📋 Дополнительные админы:\n"
    
    if admins:
        for admin_id in admins:
            text += f"🆔 {admin_id}\n"
    else:
        text += "❌ Нет дополнительных админов\n"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("Добавить админа", callback_data="add_admin", style="success"),
        InlineKeyboardButton("Удалить админа", callback_data="remove_admin", style="danger"),
        InlineKeyboardButton("Назад", callback_data="admin_panel", style="primary")
    )
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_admin")
@guarded
def add_admin(call):
    if str(call.from_user.id) != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id, "🆔 Введите ID")
    
    msg = bot.send_message(
        call.message.chat.id,
        "🆔 Введите Telegram ID нового админа:\n\n"
        "💡 Как найти ID: @userinfobot"
    )
    bot.register_next_step_handler(msg, lambda m: add_admin_id(m, call.message.chat.id, call.message.message_id))

def add_admin_id(msg, chat_id, message_id):
    try:
        new_id = str(msg.text).strip()
        
        if new_id == ADMIN_ID:
            bot.send_message(msg.chat.id, "❌ Это главный админ, его нельзя добавить")
            return
        
        if 'admins' not in data:
            data['admins'] = []
        
        if new_id in data['admins']:
            bot.send_message(msg.chat.id, "❌ Этот админ уже добавлен")
            return
        
        data['admins'].append(new_id)
        save_data(data)
        
        logger.info(f"✅ Добавлен админ: {new_id}")
        
        bot.edit_message_text(
            f"✅ Админ успешно добавлен!\n\n"
            f"🆔 ID: {new_id}",
            chat_id,
            message_id
        )
        time.sleep(0.5)
        admin_manage_admins_after(msg)
        
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "remove_admin")
@guarded
def remove_admin(call):
    if str(call.from_user.id) != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id)
    
    admins = data.get('admins', [])
    if not admins:
        bot.send_message(call.message.chat.id, "❌ Нет дополнительных админов")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for admin_id in admins:
        markup.add(InlineKeyboardButton(
            f"{admin_id}",
            callback_data=f"remove_admin_{admin_id}",
            style="danger"
        ))
    markup.add(InlineKeyboardButton("Назад", callback_data="admin_manage_admins", style="primary"))
    
    bot.edit_message_text(
        "🗑 ВЫБЕРИТЕ АДМИНА ДЛЯ УДАЛЕНИЯ:\n\n"
        f"📋 Всего админов: {len(admins)}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_admin_'))
@guarded
def remove_admin_id(call):
    if str(call.from_user.id) != ADMIN_ID:
        return
    
    admin_id = call.data.split('_')[2]
    
    if admin_id in data.get('admins', []):
        data['admins'].remove(admin_id)
        save_data(data)
        
        logger.info(f"🗑 Удалён админ: {admin_id}")
        
        bot.answer_callback_query(call.id, f"✅ Админ {admin_id} удалён")
        admin_manage_admins_after(call)
    else:
        bot.answer_callback_query(call.id, "❌ Админ не найден")

def admin_manage_admins_after(msg):
    admins = data.get('admins', [])
    
    text = "👑 УПРАВЛЕНИЕ АДМИНАМИ\n\n"
    text += f"━━━━━━━━━━━━━━━━━\n"
    text += f"👑 Главный админ: {ADMIN_ID}\n"
    text += f"━━━━━━━━━━━━━━━━━\n\n"
    text += "📋 Дополнительные админы:\n"
    
    if admins:
        for admin_id in admins:
            text += f"🆔 {admin_id}\n"
    else:
        text += "❌ Нет дополнительных админов\n"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("Добавить админа", callback_data="add_admin", style="success"),
        InlineKeyboardButton("Удалить админа", callback_data="remove_admin", style="danger"),
        InlineKeyboardButton("Назад", callback_data="admin_panel", style="primary")
    )
    
    bot.send_message(msg.chat.id, text, reply_markup=markup)

# ============================================================
# 23. ЮРИДИЧЕСКИЕ ДОКУМЕНТЫ (ТОЛЬКО ГЛАВНЫЙ)
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_legal")
@guarded
def admin_legal(call):
    if str(call.from_user.id) != ADMIN_ID:
        return
    
    bot.answer_callback_query(call.id)
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("Текст правил", callback_data="legal_edit_text", style="primary"),
        InlineKeyboardButton("Текст кнопки", callback_data="legal_edit_btn", style="primary"),
        InlineKeyboardButton("Ссылка политики", callback_data="legal_edit_privacy", style="primary"),
        InlineKeyboardButton("Ссылка оферты", callback_data="legal_edit_offer", style="primary"),
        InlineKeyboardButton("Назад", callback_data="admin_panel", style="primary")
    )
    
    bot.edit_message_text(
        "⚖️ НАСТРОЙКА ЮРИДИЧЕСКОГО БЛОКА\n\n"
        f"📝 Текст правил:\n{data['settings'].get('legal_text', '')[:100]}...\n\n"
        f"📌 Кнопка: {data['settings'].get('accept_button_text', '')}\n"
        f"🔗 Политика: https://telegra.ph/Politika-konfidencialnosti-07-17-132\n"
        f"🔗 Оферта: https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('legal_edit_'))
@guarded
def legal_edit(call):
    if str(call.from_user.id) != ADMIN_ID:
        return
    
    key = call.data.split('_')[2]
    mapping = {
        "text": "legal_text",
        "btn": "accept_button_text",
        "privacy": "privacy_url",
        "offer": "offer_url"
    }
    
    field = mapping.get(key, key)
    current = data['settings'].get(field, '')
    
    names = {
        "text": "ТЕКСТ ПРАВИЛ",
        "btn": "ТЕКСТ КНОПКИ",
        "privacy": "ССЫЛКУ НА ПОЛИТИКУ",
        "offer": "ССЫЛКУ НА ОФЕРТУ"
    }
    
    bot.answer_callback_query(call.id, f"✏️ Введите {names.get(key, '')}")
    
    hint = "\n\n💡 Поддерживает HTML: <b>жирный</b>, <a href='ссылка'>текст</a>" if key in ['text', 'btn'] else ""
    
    msg = bot.send_message(
        call.message.chat.id,
        f"✏️ Введите НОВУЮ {names.get(key, '')}:\n\n"
        f"📌 Текущая:\n{current}{hint}"
    )
    bot.register_next_step_handler(msg, lambda m: set_legal_field(m, field, call.message.chat.id, call.message.message_id))

def set_legal_field(msg, field, chat_id, message_id):
    data['settings'][field] = msg.text
    save_data(data)
    
    logger.info(f"✅ Юридический текст обновлён: {field}")
    
    bot.edit_message_text(
        f"✅ Обновлено!\n\n"
        f"📌 Новое значение:\n{msg.text[:200]}...",
        chat_id,
        message_id
    )

# ============================================================
# 23.1 ПРИЁМ ВВОДА ОТ АДМИНА (заказы: номер/код/отказ/ответ)
# ============================================================
# ВАЖНО: этот обработчик матчит ЛЮБОЕ текстовое сообщение (func=lambda m: True),
# поэтому он должен быть зарегистрирован ПОСЛЕДНИМ — telebot вызывает первый
# подошедший по фильтрам обработчик и на этом останавливается. Если поставить
# этот хендлер раньше /start или других команд — он будет перехватывать их
# первым, и они перестанут работать вообще.
@bot.message_handler(func=lambda m: True, content_types=['text'])
@guarded
def route_pending_admin_input(message):
    """Единая точка приёма текстового ввода от админа для заказов:
    номер телефона, причина отказа, код, ответ покупателю."""
    admin_id = message.from_user.id
    if not is_admin(admin_id):
        return

    pending = get_pending(admin_id)
    if not pending:
        return  # админ просто что-то написал вне сценария — игнорируем

    action = pending['action']
    clear_pending(admin_id)

    if action == 'set_phone':
        set_phone(message, pending['idx'], pending['chat_id'], pending['message_id'])
    elif action == 'set_reject':
        set_reject(message, pending['idx'], pending['chat_id'], pending['message_id'])
    elif action == 'send_code':
        send_code_to_user(message, pending['idx'])
    elif action == 'reply_to_user':
        send_reply(message, pending['idx'])
    elif action == 'set_welcome':
        set_welcome(message, pending['chat_id'], pending['message_id'])
    elif action == 'set_text_field':
        set_text_field(message, pending['field'], pending['rich_key'], pending['chat_id'], pending['message_id'])

# ============================================================
# 24. ЗАПУСК
# ============================================================
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 SIALENS Физ бот запускается...")
    print(f"👤 Главный админ: {ADMIN_ID}")
    print(f"👥 Доп. админы: {data.get('admins', [])}")
    print(f"📦 В каталоге: {len(data.get('catalog', []))} номеров")
    print(f"📋 Всего заказов: {len(data.get('orders', []))}")
    print(f"👤 Всего пользователей: {len(data.get('users', []))}")
    print("=" * 50)
    print("✅ Бот готов к работе!")
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"❌ Ошибка в polling: {e}")
            time.sleep(10)
            print("🔄 Перезапуск...")