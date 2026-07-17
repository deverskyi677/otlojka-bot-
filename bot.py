import telebot
from config import TOKEN, ADMIN_ID
import json
import os
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

bot = telebot.TeleBot(TOKEN)
SUPPORT_LINK = "https://t.me/deverskyi"

# Загрузка данных
def load_data():
    if not os.path.exists('data.json'):
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump({
                "catalog": [],
                "orders": [],
                "stats": {"users": [], "visits": 0},
                "settings": {
                    "welcome": "Добро пожаловать в SIALENS Физ!",
                    "button_color": "#0088cc",
                    "button_name": "📱 Купить номер",
                    "support_text": "Связь с поддержкой"
                }
            }, f, ensure_ascii=False, indent=2)
    with open('data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

data = load_data()

def save_data():
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- ОСНОВНЫЕ ХЕНДЛЕРЫ ---

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id not in data['stats']['users']:
        data['stats']['users'].append(user_id)
    data['stats']['visits'] += 1
    save_data()
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(data['settings']['button_name'], callback_data='buy'),
        InlineKeyboardButton("📞 Связь с поддержкой", url=SUPPORT_LINK)
    )
    if str(message.from_user.id) == str(ADMIN_ID):
        markup.add(InlineKeyboardButton("🛠 Админ панель", callback_data='admin_panel'))
    
    bot.send_message(message.chat.id, data['settings']['welcome'], reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'buy')
def buy_menu(call):
    if not data['catalog']:
        bot.answer_callback_query(call.id, "❌ Нет доступных номеров")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(
            f"{item['country']} - {item['price']}₽",
            callback_data=f"buy_{idx}"
        ))
    bot.edit_message_text("🌍 Выберите страну:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def select_country(call):
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
    
    # Уведомление админу
    markup = InlineKeyboardMarkup(row_width=2)
    order_idx = len(data['orders']) - 1
    markup.add(
        InlineKeyboardButton("✅ Принять", callback_data=f"accept_{order_idx}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{order_idx}")
    )
    markup.add(InlineKeyboardButton("✏️ Написать", callback_data=f"reply_{order_idx}"))
    
    bot.send_photo(ADMIN_ID, file_id, 
        f"🆕 НОВЫЙ ЗАКАЗ #{order['id']}\n"
        f"👤 {msg.from_user.first_name} (@{msg.from_user.username})\n"
        f"🌍 {data['catalog'][idx]['country']}\n"
        f"💰 {data['catalog'][idx]['price']}₽",
        reply_markup=markup
    )

# --- АДМИН ПАНЕЛЬ ---

@bot.callback_query_handler(func=lambda call: call.data == 'admin_panel')
def admin_panel(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Статистика", callback_data='admin_stats'),
        InlineKeyboardButton("📋 Заказы", callback_data='admin_orders'),
        InlineKeyboardButton("➕ Добавить номер", callback_data='admin_add'),
        InlineKeyboardButton("🗑 Удалить номер", callback_data='admin_delete'),
        InlineKeyboardButton("✏️ Редактировать текст", callback_data='admin_edit_text'),
        InlineKeyboardButton("🎨 Цвет кнопок", callback_data='admin_edit_color'),
        InlineKeyboardButton("📝 Название кнопки", callback_data='admin_edit_button'),
        InlineKeyboardButton("💬 Рассылка", callback_data='admin_broadcast')
    )
    bot.edit_message_text("🛠 АДМИН ПАНЕЛЬ", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'admin_stats')
def admin_stats(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    total_users = len(data['stats']['users'])
    total_visits = data['stats']['visits']
    total_orders = len(data['orders'])
    pending_orders = len([o for o in data['orders'] if o['status'] == 'waiting_approval'])
    
    bot.edit_message_text(
        f"📊 СТАТИСТИКА\n\n"
        f"👤 Всего юзеров: {total_users}\n"
        f"👀 Визитов: {total_visits}\n"
        f"📦 Всего заказов: {total_orders}\n"
        f"⏳ Ожидают: {pending_orders}",
        call.message.chat.id, call.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')
        )
    )

@bot.callback_query_handler(func=lambda call: call.data == 'admin_orders')
def admin_orders(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    if not data['orders']:
        bot.edit_message_text("📭 Нет заказов", call.message.chat.id, call.message.message_id,
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')))
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for order in data['orders'][-10:]:
        status_emoji = "⏳" if order['status'] == 'waiting_approval' else "✅" if order['status'] == 'approved' else "❌"
        markup.add(InlineKeyboardButton(
            f"#{order['id']} {order['country']} - {order['price']}₽ {status_emoji}",
            callback_data=f"order_{data['orders'].index(order)}"
        ))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel'))
    bot.edit_message_text("📋 ПОСЛЕДНИЕ ЗАКАЗЫ:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('order_'))
def order_detail(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    idx = int(call.data.split('_')[1])
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
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{idx}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{idx}")
        )
        markup.add(InlineKeyboardButton("✏️ Написать", callback_data=f"reply_{idx}"))
    
    if order['status'] == 'approved' and not order['code_waiting']:
        markup.add(InlineKeyboardButton("📨 Отправить код", callback_data=f"send_code_{idx}"))
    
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_orders'))
    
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

# --- ОБРАБОТКА ЗАКАЗОВ АДМИНОМ ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
def accept_order(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    idx = int(call.data.split('_')[1])
    order = data['orders'][idx]
    
    if order['status'] != 'waiting_approval':
        bot.answer_callback_query(call.id, "Этот заказ уже обработан")
        return
    
    msg = bot.send_message(call.message.chat.id, "📱 Введите номер телефона для выдачи:")
    bot.register_next_step_handler(msg, lambda m: set_phone(m, idx))

def set_phone(msg, idx):
    phone = msg.text
    data['orders'][idx]['phone'] = phone
    data['orders'][idx]['status'] = 'approved'
    save_data()
    
    bot.send_message(msg.chat.id, f"✅ Заказ #{data['orders'][idx]['id']} одобрен. Номер выдан.")
    
    user_id = data['orders'][idx]['user_id']
    try:
        bot.send_message(user_id, 
            f"✅ Ваш заказ одобрен!\n\n"
            f"📱 Номер: {phone}\n\n"
            f"🔐 ИНСТРУКЦИЯ:\n"
            f"1. Введите номер в Telegram\n"
            f"2. Вернитесь в чат с ботом\n"
            f"3. Нажмите «Я вернулся, жду код»\n"
            f"4. Я пришлю вам код подтверждения\n\n"
            f"📌 После получения кода:\n"
            f"• Установите двухфакторную аутентификацию\n"
            f"• Привяжите почту для восстановления\n"
            f"• Завершите все активные сессии\n"
            f"• Спокойно пользуйтесь номером",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔄 Я вернулся, жду код", callback_data=f"wait_code_{idx}")
            )
        )
    except:
        pass
    
    bot.edit_message_text(
        f"✅ Заказ #{data['orders'][idx]['id']} принят. Номер {phone} выдан.",
        msg.chat.id, msg.message_id
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_order(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    idx = int(call.data.split('_')[1])
    order = data['orders'][idx]
    
    if order['status'] != 'waiting_approval':
        bot.answer_callback_query(call.id, "Этот заказ уже обработан")
        return
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите причину отказа:")
    bot.register_next_step_handler(msg, lambda m: set_reject(m, idx))

def set_reject(msg, idx):
    reason = msg.text
    data['orders'][idx]['status'] = 'rejected'
    save_data()
    
    bot.send_message(msg.chat.id, f"❌ Заказ #{data['orders'][idx]['id']} отклонён.")
    
    user_id = data['orders'][idx]['user_id']
    try:
        bot.send_message(user_id, f"❌ Ваш заказ отклонён.\nПричина: {reason}")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def reply_to_user(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    idx = int(call.data.split('_')[1])
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

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_code_'))
def send_code(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    idx = int(call.data.split('_')[1])
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

@bot.callback_query_handler(func=lambda call: call.data.startswith('wait_code_'))
def wait_code(call):
    idx = int(call.data.split('_')[1])
    data['orders'][idx]['code_waiting'] = True
    save_data()
    
    bot.answer_callback_query(call.id, "🔄 Ожидайте код от администратора")
    bot.send_message(call.message.chat.id, "✅ Вы уведомлены. Администратор отправит код в этот чат.")
    
    bot.send_message(ADMIN_ID, f"🔄 Пользователь ждёт код для заказа #{data['orders'][idx]['id']}")

# --- УПРАВЛЕНИЕ КАТАЛОГОМ ---

@bot.callback_query_handler(func=lambda call: call.data == 'admin_add')
def add_number(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите страну и цену (например: Россия - 500):")
    bot.register_next_step_handler(msg, lambda m: add_catalog_item(m))

def add_catalog_item(msg):
    try:
        parts = msg.text.split('-')
        country = parts[0].strip()
        price = int(parts[1].strip())
        
        data['catalog'].append({"country": country, "price": price})
        save_data()
        
        bot.send_message(msg.chat.id, f"✅ Добавлено: {country} - {price}₽")
    except:
        bot.send_message(msg.chat.id, "❌ Ошибка. Используйте формат: Страна - Цена (например: Россия - 500)")

@bot.callback_query_handler(func=lambda call: call.data == 'admin_delete')
def delete_number(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    if not data['catalog']:
        bot.answer_callback_query(call.id, "❌ Нет номеров для удаления")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(
            f"❌ {item['country']} - {item['price']}₽",
            callback_data=f"del_{idx}"
        ))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel'))
    bot.edit_message_text("🗑 Выберите номер для удаления:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_catalog_item(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    idx = int(call.data.split('_')[1])
    item = data['catalog'][idx]
    data['catalog'].pop(idx)
    save_data()
    
    bot.answer_callback_query(call.id, f"✅ Удалено: {item['country']} - {item['price']}₽")
    admin_panel(call)

# --- РЕДАКТИРОВАНИЕ НАСТРОЕК ---

@bot.callback_query_handler(func=lambda call: call.data == 'admin_edit_text')
def edit_text(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите новый текст приветствия:")
    bot.register_next_step_handler(msg, lambda m: set_text(m))

def set_text(msg):
    data['settings']['welcome'] = msg.text
    save_data()
    bot.send_message(msg.chat.id, "✅ Текст обновлён")

@bot.callback_query_handler(func=lambda call: call.data == 'admin_edit_button')
def edit_button(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите новое название для кнопки «Купить номер»:")
    bot.register_next_step_handler(msg, lambda m: set_button(m))

def set_button(msg):
    data['settings']['button_name'] = msg.text
    save_data()
    bot.send_message(msg.chat.id, "✅ Название кнопки обновлено")

@bot.callback_query_handler(func=lambda call: call.data == 'admin_edit_color')
def edit_color(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите цвет кнопок (например: #0088cc):")
    bot.register_next_step_handler(msg, lambda m: set_color(m))

def set_color(msg):
    color = msg.text
    if not color.startswith('#'):
        color = '#' + color
    data['settings']['button_color'] = color
    save_data()
    bot.send_message(msg.chat.id, f"✅ Цвет обновлён: {color}")

# --- РАССЫЛКА ---

@bot.callback_query_handler(func=lambda call: call.data == 'admin_broadcast')
def broadcast(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите текст для рассылки:")
    bot.register_next_step_handler(msg, lambda m: send_broadcast(m))

def send_broadcast(msg):
    text = msg.text
    count = 0
    for user_id in data['stats']['users']:
        try:
            bot.send_message(user_id, f"📢 РАССЫЛКА:\n\n{text}")
            count += 1
        except:
            pass
    
    bot.send_message(msg.chat.id, f"✅ Отправлено {count} пользователям")

# --- ЗАПУСК ---

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