import telebot
from config import TOKEN, ADMIN_ID
import json
import os
import time
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

bot = telebot.TeleBot(TOKEN)
SUPPORT_LINK = "https://t.me/deverskyi"

def load_data():
    if not os.path.exists('data.json'):
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump({
                "catalog": [],
                "orders": [],
                "stats": {"users": [], "visits": 0},
                "settings": {
                    "welcome": "Добро пожаловать в SIALENS Физ!",
                    "buttons": {
                        "buy": {"text": "📱 Купить номер", "color": "#0088cc"},
                        "support": {"text": "📞 Связь с поддержкой", "color": "#0088cc"},
                        "admin": {"text": "🛠 Админ панель", "color": "#ff0000"},
                        "back": {"text": "🔙 Назад", "color": "#0088cc"},
                        "wait_code": {"text": "🔄 Я вернулся, жду код", "color": "#0088cc"}
                    }
                }
            }, f, ensure_ascii=False, indent=2)
    with open('data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

data = load_data()

def save_data():
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Функция для плавного выполнения (задержка 0.4 сек)
def smooth_execute(func, *args, **kwargs):
    time.sleep(0.4)
    func(*args, **kwargs)

# Функция для создания кнопки с цветом (сохраняем цвет в JSON)
def create_button(text, callback_data=None, url=None, color="#0088cc"):
    # В Telegram нельзя менять цвет кнопок, но сохраняем в JSON
    if callback_data:
        return InlineKeyboardButton(text, callback_data=callback_data)
    else:
        return InlineKeyboardButton(text, url=url)

# ============================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id not in data['stats']['users']:
        data['stats']['users'].append(user_id)
    data['stats']['visits'] += 1
    save_data()
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(data['settings']['buttons']['buy']['text'], callback_data='buy'),
        InlineKeyboardButton(data['settings']['buttons']['support']['text'], url=SUPPORT_LINK)
    )
    if str(message.from_user.id) == str(ADMIN_ID):
        markup.add(InlineKeyboardButton(data['settings']['buttons']['admin']['text'], callback_data='admin_panel'))
    
    bot.send_message(message.chat.id, data['settings']['welcome'], reply_markup=markup)

# ============================================================
# КНОПКА: КУПИТЬ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'buy')
def buy_menu(call):
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(buy_menu_after_delay, call)).start()

def buy_menu_after_delay(call):
    if not data['catalog']:
        bot.send_message(call.message.chat.id, "❌ Нет доступных номеров")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(
            f"{item['country']} - {item['price']}₽",
            callback_data=f"buy_{idx}"
        ))
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='back_to_start'))
    
    bot.edit_message_text("🌍 Выберите страну:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# КНОПКА: ВЫБОР СТРАНЫ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def select_country(call):
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(select_country_after_delay, call)).start()

def select_country_after_delay(call):
    idx = int(call.data.split('_')[1])
    item = data['catalog'][idx]
    
    msg = bot.send_message(call.message.chat.id, 
        f"💳 Оплатите {item['price']}₽ на номер:\n<b>+79103552521</b> (Сбербанк)\n\n"
        "📸 После оплаты пришлите СКРИНШОТ платежа.",
        parse_mode='HTML'
    )
    bot.register_next_step_handler(msg, lambda m: handle_screenshot(m, idx))

def handle_screenshot(msg, idx):
    if not msg.photo:
        bot.send_message(msg.chat.id, "❌ Это не фото. Пришлите скриншот.")
        bot.register_next_step_handler(msg, lambda m: handle_screenshot(m, idx))
        return
    
    file_id = msg.photo[-1].file_id
    order = {
        "id": len(data['orders']) + 1,
        "user_id": str(msg.from_user.id),
        "username": msg.from_user.username or "Нет юзернейма",
        "first_name": msg.from_user.first_name,
        "country": data['catalog'][idx]['country'],
        "price": data['catalog'][idx]['price'],
        "screenshot": file_id,
        "status": "waiting_approval",
        "phone": None,
        "code_waiting": False,
        "date": time.time()
    }
    data['orders'].append(order)
    save_data()
    
    bot.send_message(msg.chat.id, "✅ Скрин отправлен на проверку. Ожидайте.")
    
    order_idx = len(data['orders']) - 1
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Принять", callback_data=f"accept_order_{order_idx}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_order_{order_idx}")
    )
    markup.add(
        InlineKeyboardButton("✏️ Написать", callback_data=f"reply_order_{order_idx}")
    )
    
    bot.send_photo(ADMIN_ID, file_id, 
        f"🆕 НОВЫЙ ЗАКАЗ #{order['id']}\n"
        f"👤 {msg.from_user.first_name} (@{msg.from_user.username})\n"
        f"🌍 {data['catalog'][idx]['country']}\n"
        f"💰 {data['catalog'][idx]['price']}₽",
        reply_markup=markup
    )

# ============================================================
# КНОПКА: НАЗАД
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_start')
def back_to_start(call):
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(start, call.message)).start()

# ============================================================
# КНОПКА: АДМИН ПАНЕЛЬ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_panel')
def admin_panel(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(admin_panel_after_delay, call)).start()

def admin_panel_after_delay(call):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Статистика", callback_data='admin_stats'),
        InlineKeyboardButton("📋 Заказы", callback_data='admin_orders_list'),
        InlineKeyboardButton("➕ Добавить номер", callback_data='admin_add_number'),
        InlineKeyboardButton("🗑 Удалить номер", callback_data='admin_delete_number'),
        InlineKeyboardButton("✏️ Редактировать кнопки", callback_data='admin_edit_buttons_list'),
        InlineKeyboardButton("📝 Текст приветствия", callback_data='admin_edit_welcome'),
        InlineKeyboardButton("💬 Рассылка", callback_data='admin_broadcast'),
        InlineKeyboardButton("🔙 Выход", callback_data='back_to_start')
    )
    bot.edit_message_text("🛠 АДМИН ПАНЕЛЬ", call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# КНОПКА: СТАТИСТИКА
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_stats')
def admin_stats(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(admin_stats_after_delay, call)).start()

def admin_stats_after_delay(call):
    total_users = len(data['stats']['users'])
    total_visits = data['stats']['visits']
    total_orders = len(data['orders'])
    pending_orders = len([o for o in data['orders'] if o['status'] == 'waiting_approval'])
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_panel'))
    
    bot.edit_message_text(
        f"📊 СТАТИСТИКА\n\n"
        f"👤 Всего юзеров: {total_users}\n"
        f"👀 Визитов: {total_visits}\n"
        f"📦 Всего заказов: {total_orders}\n"
        f"⏳ Ожидают: {pending_orders}",
        call.message.chat.id, call.message.message_id,
        reply_markup=markup
    )

# ============================================================
# КНОПКА: СПИСОК ЗАКАЗОВ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_orders_list')
def admin_orders_list(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(admin_orders_list_after_delay, call)).start()

def admin_orders_list_after_delay(call):
    if not data['orders']:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_panel'))
        bot.edit_message_text("📭 Нет заказов", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for order in data['orders'][-10:]:
        status_emoji = "⏳" if order['status'] == 'waiting_approval' else "✅" if order['status'] == 'approved' else "❌"
        markup.add(InlineKeyboardButton(
            f"#{order['id']} {order['country']} - {order['price']}₽ {status_emoji}",
            callback_data=f"order_detail_{data['orders'].index(order)}"
        ))
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_panel'))
    
    bot.edit_message_text("📋 ПОСЛЕДНИЕ ЗАКАЗЫ:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# КНОПКА: ДЕТАЛИ ЗАКАЗА
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('order_detail_'))
def order_detail(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(order_detail_after_delay, call)).start()

def order_detail_after_delay(call):
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
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_order_{idx}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_order_{idx}")
        )
        markup.add(InlineKeyboardButton("✏️ Написать", callback_data=f"reply_order_{idx}"))
    
    if order['status'] == 'approved' and not order['code_waiting']:
        markup.add(InlineKeyboardButton("📨 Отправить код", callback_data=f"send_code_{idx}"))
    
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_orders_list'))
    
    bot.edit_message_text(
        f"📦 ЗАКАЗ #{order['id']}\n\n"
        f"👤 {order['first_name']} (@{order['username']})\n"
        f"🆔 {order['user_id']}\n"
        f"🌍 {order['country']}\n"
        f"💰 {order['price']}₽\n"
        f"📅 {time.ctime(order['date'])}\n"
        f"📊 Статус: {status_map.get(order['status'], order['status'])}\n"
        f"📱 Номер: {order['phone'] or 'Не выдан'}\n"
        f"🔄 Ожидает код: {'Да' if order['code_waiting'] else 'Нет'}",
        call.message.chat.id, call.message.message_id,
        reply_markup=markup
    )

# ============================================================
# КНОПКА: ПРИНЯТЬ ЗАКАЗ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_order_'))
def accept_order(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(accept_order_after_delay, call)).start()

def accept_order_after_delay(call):
    idx = int(call.data.split('_')[2])
    order = data['orders'][idx]
    
    if order['status'] != 'waiting_approval':
        bot.send_message(call.message.chat.id, "❌ Этот заказ уже обработан")
        return
    
    msg = bot.send_message(call.message.chat.id, "📱 Введите номер телефона для выдачи:")
    bot.register_next_step_handler(msg, lambda m: set_phone(m, idx, call.message.chat.id, call.message.message_id))

def set_phone(msg, idx, chat_id, message_id):
    phone = msg.text
    data['orders'][idx]['phone'] = phone
    data['orders'][idx]['status'] = 'approved'
    save_data()
    
    bot.edit_message_text(
        f"✅ Заказ #{data['orders'][idx]['id']} принят. Номер {phone} выдан.",
        chat_id, message_id
    )
    
    user_id = data['orders'][idx]['user_id']
    wait_btn = data['settings']['buttons']['wait_code']
    
    try:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(wait_btn['text'], callback_data=f"wait_code_{idx}"))
        
        bot.send_message(user_id, 
            f"✅ Ваш заказ одобрен!\n\n"
            f"📱 Номер: {phone}\n\n"
            f"🔐 ИНСТРУКЦИЯ:\n"
            f"1. Введите номер в Telegram\n"
            f"2. Вернитесь в чат с ботом\n"
            f"3. Нажмите «{wait_btn['text']}»\n"
            f"4. Я пришлю вам код подтверждения\n\n"
            f"📌 После получения кода:\n"
            f"• Установите двухфакторную аутентификацию\n"
            f"• Привяжите почту для восстановления\n"
            f"• Завершите все активные сессии",
            reply_markup=markup
        )
    except:
        pass

# ============================================================
# КНОПКА: ОТКЛОНИТЬ ЗАКАЗ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_order_'))
def reject_order(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(reject_order_after_delay, call)).start()

def reject_order_after_delay(call):
    idx = int(call.data.split('_')[2])
    order = data['orders'][idx]
    
    if order['status'] != 'waiting_approval':
        bot.send_message(call.message.chat.id, "❌ Этот заказ уже обработан")
        return
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите причину отказа:")
    bot.register_next_step_handler(msg, lambda m: set_reject(m, idx, call.message.chat.id, call.message.message_id))

def set_reject(msg, idx, chat_id, message_id):
    reason = msg.text
    data['orders'][idx]['status'] = 'rejected'
    save_data()
    
    bot.edit_message_text(
        f"❌ Заказ #{data['orders'][idx]['id']} отклонён.\nПричина: {reason}",
        chat_id, message_id
    )
    
    user_id = data['orders'][idx]['user_id']
    try:
        bot.send_message(user_id, f"❌ Ваш заказ отклонён.\nПричина: {reason}")
    except:
        pass

# ============================================================
# КНОПКА: НАПИСАТЬ ПОКУПАТЕЛЮ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_order_'))
def reply_to_user(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(reply_to_user_after_delay, call)).start()

def reply_to_user_after_delay(call):
    idx = int(call.data.split('_')[2])
    msg = bot.send_message(call.message.chat.id, "✏️ Введите сообщение для покупателя:")
    bot.register_next_step_handler(msg, lambda m: send_reply(m, idx))

def send_reply(msg, idx):
    text = msg.text
    user_id = data['orders'][idx]['user_id']
    try:
        bot.send_message(user_id, f"📩 Сообщение от администратора:\n\n{text}")
        bot.send_message(msg.chat.id, "✅ Сообщение отправлено")
    except:
        bot.send_message(msg.chat.id, "❌ Не удалось отправить сообщение")

# ============================================================
# КНОПКА: ОТПРАВИТЬ КОД
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_code_'))
def send_code(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(send_code_after_delay, call)).start()

def send_code_after_delay(call):
    idx = int(call.data.split('_')[2])
    msg = bot.send_message(call.message.chat.id, "✏️ Введите код подтверждения:")
    bot.register_next_step_handler(msg, lambda m: send_code_to_user(m, idx))

def send_code_to_user(msg, idx):
    code = msg.text
    user_id = data['orders'][idx]['user_id']
    data['orders'][idx]['code_waiting'] = False
    data['orders'][idx]['status'] = 'code_sent'
    save_data()
    
    try:
        bot.send_message(user_id, f"📨 Ваш код подтверждения:\n\n<b>{code}</b>\n\nВведите его в Telegram.", parse_mode='HTML')
        bot.send_message(msg.chat.id, "✅ Код отправлен")
    except:
        bot.send_message(msg.chat.id, "❌ Не удалось отправить код")

# ============================================================
# КНОПКА: ЖДУ КОД
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('wait_code_'))
def wait_code(call):
    bot.answer_callback_query(call.id, "🔄 Ожидайте код от администратора")
    threading.Thread(target=smooth_execute, args=(wait_code_after_delay, call)).start()

def wait_code_after_delay(call):
    idx = int(call.data.split('_')[1])
    data['orders'][idx]['code_waiting'] = True
    save_data()
    
    bot.send_message(call.message.chat.id, "✅ Вы уведомлены. Администратор отправит код в этот чат.")
    bot.send_message(ADMIN_ID, f"🔄 Пользователь ждёт код для заказа #{data['orders'][idx]['id']}")

# ============================================================
# КНОПКА: ДОБАВИТЬ НОМЕР
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_add_number')
def add_number(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(add_number_after_delay, call)).start()

def add_number_after_delay(call):
    msg = bot.send_message(call.message.chat.id, "✏️ Введите страну и цену (например: Россия - 500):")
    bot.register_next_step_handler(msg, lambda m: add_catalog_item(m, call.message.chat.id, call.message.message_id))

def add_catalog_item(msg, chat_id, message_id):
    try:
        parts = msg.text.split('-')
        country = parts[0].strip()
        price = int(parts[1].strip())
        
        data['catalog'].append({"country": country, "price": price})
        save_data()
        
        bot.edit_message_text(
            f"✅ Добавлено: {country} - {price}₽",
            chat_id, message_id
        )
        admin_panel_after_delay(msg)
    except:
        bot.send_message(msg.chat.id, "❌ Ошибка. Используйте формат: Страна - Цена (например: Россия - 500)")

# ============================================================
# КНОПКА: УДАЛИТЬ НОМЕР
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_delete_number')
def delete_number(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(delete_number_after_delay, call)).start()

def delete_number_after_delay(call):
    if not data['catalog']:
        bot.send_message(call.message.chat.id, "❌ Нет номеров для удаления")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(
            f"❌ {item['country']} - {item['price']}₽",
            callback_data=f"delete_catalog_{idx}"
        ))
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_panel'))
    
    bot.edit_message_text("🗑 Выберите номер для удаления:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# КНОПКА: УДАЛИТЬ КОНКРЕТНЫЙ НОМЕР
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_catalog_'))
def delete_catalog_item(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    idx = int(call.data.split('_')[2])
    item = data['catalog'][idx]
    data['catalog'].pop(idx)
    save_data()
    
    bot.answer_callback_query(call.id, f"✅ Удалено: {item['country']} - {item['price']}₽")
    admin_panel_after_delay(call)

# ============================================================
# КНОПКА: РЕДАКТИРОВАТЬ КНОПКИ (СПИСОК)
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_edit_buttons_list')
def admin_edit_buttons_list(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(admin_edit_buttons_list_after_delay, call)).start()

def admin_edit_buttons_list_after_delay(call):
    markup = InlineKeyboardMarkup(row_width=1)
    for key, btn in data['settings']['buttons'].items():
        markup.add(InlineKeyboardButton(
            f"✏️ {btn['text']}", 
            callback_data=f"edit_button_{key}"
        ))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel'))
    
    bot.edit_message_text(
        "🛠 РЕДАКТИРОВАНИЕ КНОПОК\n\n"
        "Выберите кнопку для изменения:",
        call.message.chat.id, call.message.message_id, reply_markup=markup
    )

# ============================================================
# КНОПКА: ВЫБОР КНОПКИ ДЛЯ РЕДАКТИРОВАНИЯ (ТЕКСТ + ЦВЕТ)
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_button_'))
def edit_button_menu(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(edit_button_menu_after_delay, call)).start()

def edit_button_menu_after_delay(call):
    key = call.data.split('_')[2]
    btn = data['settings']['buttons'][key]
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📝 Изменить текст", callback_data=f"edit_button_text_{key}"),
        InlineKeyboardButton("🎨 Изменить цвет", callback_data=f"edit_button_color_{key}"),
        InlineKeyboardButton("🔙 Назад", callback_data='admin_edit_buttons_list')
    )
    
    bot.edit_message_text(
        f"🛠 НАСТРОЙКА КНОПКИ\n\n"
        f"📌 Текст: {btn['text']}\n"
        f"🎨 Цвет: {btn['color']}\n\n"
        f"💡 Доступные цвета:\n"
        f"• #ff0000 - красный\n"
        f"• #00ff00 - зелёный\n"
        f"• #0000ff - синий\n"
        f"• #ff8800 - оранжевый\n"
        f"• #ff00ff - розовый",
        call.message.chat.id, call.message.message_id, reply_markup=markup
    )

# ============================================================
# КНОПКА: ИЗМЕНИТЬ ТЕКСТ КНОПКИ (РАБОТАЕТ)
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_button_text_'))
def edit_button_text(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    
    key = call.data.split('_')[3]
    bot.answer_callback_query(call.id, "✏️ Введите новый текст")
    
    msg = bot.send_message(call.message.chat.id, 
        f"✏️ Введите НОВЫЙ ТЕКСТ для кнопки:\n\n"
        f"📌 Текущий: {data['settings']['buttons'][key]['text']}\n\n"
        f"💡 Можно использовать любые эмодзи: 📱 🔥 ⭐️ ✅ ❌ 🎯"
    )
    bot.register_next_step_handler(msg, lambda m: set_button_text(m, key, call.message.chat.id, call.message.message_id))

def set_button_text(msg, key, chat_id, message_id):
    new_text = msg.text
    old_text = data['settings']['buttons'][key]['text']
    data['settings']['buttons'][key]['text'] = new_text
    save_data()
    
    # Обновляем сообщение админа
    bot.edit_message_text(
        f"✅ Текст кнопки обновлён!\n\n"
        f"📌 Было: {old_text}\n"
        f"📌 Стало: {new_text}",
        chat_id, message_id
    )
    
    # Показываем обновлённый список кнопок
    admin_edit_buttons_list_after_delay(msg)

# ============================================================
# КНОПКА: ИЗМЕНИТЬ ЦВЕТ КНОПКИ (РАБОТАЕТ)
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_button_color_'))
def edit_button_color(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    
    key = call.data.split('_')[3]
    bot.answer_callback_query(call.id, "🎨 Введите цвет")
    
    msg = bot.send_message(call.message.chat.id, 
        f"🎨 Введите НОВЫЙ ЦВЕТ для кнопки:\n\n"
        f"📌 Текущий цвет: {data['settings']['buttons'][key]['color']}\n\n"
        f"📌 Форматы:\n"
        f"• HEX: #ff0000 (красный)\n"
        f"• HEX: #00ff00 (зелёный)\n"
        f"• HEX: #0000ff (синий)\n"
        f"• Название: красный, синий, зелёный, оранжевый\n\n"
        f"💡 Пример: #ff8800 или оранжевый"
    )
    bot.register_next_step_handler(msg, lambda m: set_button_color(m, key, call.message.chat.id, call.message.message_id))

def set_button_color(msg, key, chat_id, message_id):
    color_input = msg.text.strip()
    
    # Конвертация названий в HEX
    color_map = {
        "красный": "#ff0000",
        "зелёный": "#00ff00",
        "зеленый": "#00ff00",
        "синий": "#0000ff",
        "оранжевый": "#ff8800",
        "желтый": "#ffff00",
        "жёлтый": "#ffff00",
        "фиолетовый": "#8800ff",
        "розовый": "#ff00ff",
        "черный": "#000000",
        "чёрный": "#000000",
        "белый": "#ffffff",
        "серый": "#888888",
        "голубой": "#00ffff"
    }
    
    if color_input.lower() in color_map:
        color = color_map[color_input.lower()]
    elif color_input.startswith('#'):
        color = color_input
    else:
        color = '#' + color_input
    
    old_color = data['settings']['buttons'][key]['color']
    data['settings']['buttons'][key]['color'] = color
    save_data()
    
    # Обновляем сообщение админа
    bot.edit_message_text(
        f"✅ Цвет кнопки обновлён!\n\n"
        f"🎨 Было: {old_color}\n"
        f"🎨 Стало: {color}",
        chat_id, message_id
    )
    
    # Показываем обновлённый список кнопок
    admin_edit_buttons_list_after_delay(msg)

# ============================================================
# КНОПКА: ИЗМЕНИТЬ ТЕКСТ ПРИВЕТСТВИЯ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_edit_welcome')
def edit_welcome(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(edit_welcome_after_delay, call)).start()

def edit_welcome_after_delay(call):
    msg = bot.send_message(call.message.chat.id, 
        f"✏️ Введите НОВЫЙ ТЕКСТ ПРИВЕТСТВИЯ:\n\n"
        f"📌 Текущий:\n{data['settings']['welcome']}"
    )
    bot.register_next_step_handler(msg, lambda m: set_welcome(m, call.message.chat.id, call.message.message_id))

def set_welcome(msg, chat_id, message_id):
    data['settings']['welcome'] = msg.text
    save_data()
    
    bot.edit_message_text(
        f"✅ Текст приветствия обновлён!\n\n"
        f"📌 Новый текст:\n{msg.text}",
        chat_id, message_id
    )

# ============================================================
# КНОПКА: РАССЫЛКА
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_broadcast')
def broadcast(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(broadcast_after_delay, call)).start()

def broadcast_after_delay(call):
    msg = bot.send_message(call.message.chat.id, "✏️ Введите текст для рассылки:")
    bot.register_next_step_handler(msg, lambda m: send_broadcast(m, call.message.chat.id, call.message.message_id))

def send_broadcast(msg, chat_id, message_id):
    text = msg.text
    count = 0
    for user_id in data['stats']['users']:
        try:
            bot.send_message(user_id, f"📢 РАССЫЛКА:\n\n{text}")
            count += 1
        except:
            pass
    
    bot.edit_message_text(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено {count} пользователям",
        chat_id, message_id
    )

# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == '__main__':
    print("✅ SIALENS Физ бот запущен")
    print(f"👤 Админ ID: {ADMIN_ID}")
    print(f"📦 Каталог: {len(data['catalog'])} номеров")
    print(f"📋 Заказов: {len(data['orders'])}")
    
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"Ошибка: {e}")
        time.sleep(5)