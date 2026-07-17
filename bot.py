import telebot
import json
import os
import time
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, ADMIN_ID

# ========== 1. НАСТРОЙКИ ==========
bot = telebot.TeleBot(TOKEN)

# ========== 2. РАБОТА С ДАННЫМИ ==========
def load_data():
    if not os.path.exists('data.json'):
        default_data = {
            "catalog": [
                {"country": "Россия", "price": 500}
            ],
            "orders": [],
            "users": [],
            "accepted_users": [],
            "stats": {"visits": 0},
            "admins": [],
            "settings": {
                "welcome_text": "Добро пожаловать в SIALENS Физ!\n📱 Покупайте виртуальные номера легко и быстро.",
                "legal_text": "📜 <b>Покупая номер, вы соглашаетесь с условиями:</b>\n\n• <a href='https://telegra.ph/Politika-konfidencialnosti-07-17-132'>Политика конфиденциальности</a>\n• <a href='https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17'>Публичная оферта</a>\n\nНажимая кнопку ниже, вы принимаете все условия.",
                "accept_button_text": "✅ Я принимаю условия"
            }
        }
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(default_data, f, indent=2, ensure_ascii=False)
    with open('data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

data = load_data()

def is_admin(user_id):
    return str(user_id) == str(ADMIN_ID) or str(user_id) in data.get('admins', [])

# ========== 3. ГЛАВНОЕ МЕНЮ ==========
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = str(message.from_user.id)
    
    if user_id not in data['users']:
        data['users'].append(user_id)
    
    data['stats']['visits'] = data['stats'].get('visits', 0) + 1
    save_data(data)

    # Показываем юридический блок, если юзер ещё не принял условия
    if user_id not in data['accepted_users']:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📋 Политика", url="https://telegra.ph/Politika-konfidencialnosti-07-17-132"),
            InlineKeyboardButton("📄 Оферта", url="https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17"),
            InlineKeyboardButton(data['settings'].get('accept_button_text', '✅ Принять'), callback_data="accept_rules")
        )
        bot.send_message(
            message.chat.id,
            data['settings'].get('legal_text', 'Примите условия'),
            reply_markup=markup,
            parse_mode='HTML'
        )
        return

    # Показываем главное меню
    show_main_menu(message.chat.id)

def show_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📱 Купить номер", callback_data="buy_menu"),
        InlineKeyboardButton("📞 Связь с поддержкой", url="https://t.me/deverskyi")
    )
    if is_admin(chat_id):
        markup.add(InlineKeyboardButton("🛠 Админ панель", callback_data="admin_panel"))
    
    bot.send_message(
        chat_id,
        data['settings'].get('welcome_text', 'Добро пожаловать!'),
        reply_markup=markup
    )

# ========== 4. ПРИНЯТИЕ ПРАВИЛ ==========
@bot.callback_query_handler(func=lambda call: call.data == "accept_rules")
def accept_rules(call):
    user_id = str(call.from_user.id)
    if user_id not in data['accepted_users']:
        data['accepted_users'].append(user_id)
        save_data(data)
    
    bot.answer_callback_query(call.id, "✅ Условия приняты!")
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    show_main_menu(call.message.chat.id)

# ========== 5. ПОКУПКА НОМЕРА ==========
@bot.callback_query_handler(func=lambda call: call.data == "buy_menu")
def buy_menu(call):
    bot.answer_callback_query(call.id)
    
    if not data.get('catalog'):
        bot.send_message(call.message.chat.id, "❌ Нет доступных номеров")
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(
            f"{item['country']} - {item['price']}₽",
            callback_data=f"buy_{idx}"
        ))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    
    bot.edit_message_text(
        "🌍 Выберите страну:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_selected(call):
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    item = data['catalog'][idx]
    
    msg = bot.send_message(
        call.message.chat.id,
        f"💳 Оплатите {item['price']}₽ на номер:\n<b>+79103552521</b>\n\nПосле оплаты пришлите СКРИНШОТ.",
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
        "first_name": msg.from_user.first_name,
        "username": msg.from_user.username,
        "country": data['catalog'][idx]['country'],
        "price": data['catalog'][idx]['price'],
        "screenshot": msg.photo[-1].file_id,
        "status": "waiting_approval",
        "phone": None,
        "code_waiting": False,
        "date": time.time()
    }
    data['orders'].append(order)
    save_data(data)
    
    bot.send_message(msg.chat.id, "✅ Скрин отправлен на проверку. Ожидайте.")

    # Отправляем заказ всем админам
    order_idx = len(data['orders']) - 1
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Принять", callback_data=f"accept_{order_idx}", style="success"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{order_idx}", style="danger")
    )
    markup.add(InlineKeyboardButton("✏️ Написать", callback_data=f"reply_{order_idx}", style="primary"))
    
    admin_ids = [str(ADMIN_ID)] + data.get('admins', [])
    for admin_id in admin_ids:
        try:
            bot.send_photo(
                admin_id,
                order['screenshot'],
                f"🆕 ЗАКАЗ #{order['id']}\n"
                f"👤 {order['first_name']} (@{order['username']})\n"
                f"🌍 {order['country']}\n"
                f"💰 {order['price']}₽",
                reply_markup=markup
            )
        except:
            pass

# ========== 6. АДМИН ПАНЕЛЬ ==========
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Статистика", callback_data="statistics", style="primary"),
        InlineKeyboardButton("📋 Заказы", callback_data="orders_list", style="primary"),
        InlineKeyboardButton("➕ Добавить номер", callback_data="add_number", style="success"),
        InlineKeyboardButton("🗑 Удалить номер", callback_data="delete_number", style="danger"),
        InlineKeyboardButton("✏️ Текст приветствия", callback_data="edit_welcome", style="primary"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu", style="danger")
    )
    bot.edit_message_text("🛠 АДМИН ПАНЕЛЬ", call.message.chat.id, call.message.message_id, reply_markup=markup)

# ========== 7. СТАТИСТИКА ==========
@bot.callback_query_handler(func=lambda call: call.data == "statistics")
def statistics(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    total_users = len(data['users'])
    accepted_users = len(data['accepted_users'])
    total_visits = data['stats'].get('visits', 0)
    total_orders = len(data['orders'])
    pending_orders = len([o for o in data['orders'] if o['status'] == 'waiting_approval'])
    
    text = f"📊 СТАТИСТИКА\n\n"
    text += f"👤 Всего юзеров: {total_users}\n"
    text += f"✅ Приняли правила: {accepted_users}\n"
    text += f"👀 Визитов: {total_visits}\n"
    text += f"📦 Заказов: {total_orders}\n"
    text += f"⏳ Ожидают проверки: {pending_orders}"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ========== 8. ЗАКАЗЫ ==========
@bot.callback_query_handler(func=lambda call: call.data == "orders_list")
def orders_list(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    
    if not data['orders']:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary"))
        bot.edit_message_text("📭 Нет заказов", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for order in data['orders'][-10:]:
        idx = data['orders'].index(order)
        status_emoji = "⏳" if order['status'] == 'waiting_approval' else "✅" if order['status'] == 'approved' else "❌"
        markup.add(InlineKeyboardButton(
            f"#{order['id']} {order['country']} - {order['price']}₽ {status_emoji}",
            callback_data=f"order_detail_{idx}",
            style="primary"
        ))
    
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary"))
    bot.edit_message_text("📋 ПОСЛЕДНИЕ ЗАКАЗЫ:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('order_detail_'))
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
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{idx}", style="success"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{idx}", style="danger")
        )
        markup.add(InlineKeyboardButton("✏️ Написать", callback_data=f"reply_{idx}", style="primary"))
    
    if order['status'] == 'approved' and not order['code_waiting']:
        markup.add(InlineKeyboardButton("📨 Отправить код", callback_data=f"send_code_{idx}", style="success"))
    
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="orders_list", style="primary"))
    
    text = f"📦 ЗАКАЗ #{order['id']}\n\n"
    text += f"👤 {order['first_name']} (@{order['username']})\n"
    text += f"🆔 {order['user_id']}\n"
    text += f"🌍 {order['country']}\n"
    text += f"💰 {order['price']}₽\n"
    text += f"📅 {time.ctime(order['date'])}\n"
    text += f"📊 {status_map.get(order['status'], order['status'])}\n"
    text += f"📱 Номер: {order['phone'] or 'Не выдан'}"
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ========== 9. ПРИНЯТЬ/ОТКЛОНИТЬ/НАПИСАТЬ ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
def accept_order(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    order = data['orders'][idx]
    
    if order['status'] != 'waiting_approval':
        bot.send_message(call.message.chat.id, "❌ Заказ уже обработан")
        return
    
    msg = bot.send_message(call.message.chat.id, "📱 Введите номер телефона для выдачи:")
    bot.register_next_step_handler(msg, lambda m: set_phone(m, idx, call.message.chat.id, call.message.message_id))

def set_phone(msg, idx, chat_id, message_id):
    phone = msg.text
    data['orders'][idx]['phone'] = phone
    data['orders'][idx]['status'] = 'approved'
    save_data(data)
    
    bot.edit_message_text(
        f"✅ Заказ #{data['orders'][idx]['id']} принят. Номер {phone} выдан.",
        chat_id,
        message_id
    )
    
    user_id = data['orders'][idx]['user_id']
    try:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔄 Я вернулся, жду код", callback_data=f"wait_code_{idx}", style="primary"))
        
        bot.send_message(
            user_id,
            f"✅ ВАШ ПЛАТЕЖ ОДОБРЕН!\n\n"
            f"📱 Ваш номер: {phone}\n\n"
            f"🔐 ИНСТРУКЦИЯ:\n"
            f"1️⃣ Введите номер {phone} в Telegram\n"
            f"2️⃣ Вернитесь в чат с ботом\n"
            f"3️⃣ Нажмите кнопку «Я вернулся, жду код»\n"
            f"4️⃣ Я пришлю вам код подтверждения\n\n"
            f"📌 ПОСЛЕ ПОЛУЧЕНИЯ КОДА:\n"
            f"• Установите двухфакторную аутентификацию\n"
            f"• Привяжите почту для восстановления\n"
            f"• Завершите все активные сессии",
            reply_markup=markup
        )
        bot.send_message(msg.chat.id, f"✅ Пользователю отправлен номер: {phone}")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка отправки: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_order(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    order = data['orders'][idx]
    
    if order['status'] != 'waiting_approval':
        bot.send_message(call.message.chat.id, "❌ Заказ уже обработан")
        return
    
    msg = bot.send_message(call.message.chat.id, "✏️ Введите причину отказа:")
    bot.register_next_step_handler(msg, lambda m: set_reject(m, idx, call.message.chat.id, call.message.message_id))

def set_reject(msg, idx, chat_id, message_id):
    reason = msg.text
    data['orders'][idx]['status'] = 'rejected'
    save_data(data)
    
    bot.edit_message_text(
        f"❌ Заказ #{data['orders'][idx]['id']} отклонён.\nПричина: {reason}",
        chat_id,
        message_id
    )
    
    try:
        bot.send_message(data['orders'][idx]['user_id'], f"❌ Ваш заказ отклонён.\nПричина: {reason}")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def reply_to_user(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    msg = bot.send_message(call.message.chat.id, "✏️ Введите сообщение для покупателя:")
    bot.register_next_step_handler(msg, lambda m: send_reply(m, idx))

def send_reply(msg, idx):
    user_id = data['orders'][idx]['user_id']
    try:
        bot.send_message(user_id, f"📩 Сообщение от администратора:\n\n{msg.text}")
        bot.send_message(msg.chat.id, "✅ Сообщение отправлено")
    except:
        bot.send_message(msg.chat.id, "❌ Не удалось отправить сообщение")

# ========== 10. ОТПРАВИТЬ КОД ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('send_code_'))
def send_code(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[2])
    msg = bot.send_message(call.message.chat.id, "✏️ Введите код подтверждения:")
    bot.register_next_step_handler(msg, lambda m: send_code_to_user(m, idx))

def send_code_to_user(msg, idx):
    code = msg.text
    data['orders'][idx]['code_waiting'] = False
    data['orders'][idx]['status'] = 'code_sent'
    save_data(data)
    
    try:
        bot.send_message(data['orders'][idx]['user_id'], f"📨 Ваш код подтверждения:\n\n<b>{code}</b>", parse_mode='HTML')
        bot.send_message(msg.chat.id, "✅ Код отправлен")
    except:
        bot.send_message(msg.chat.id, "❌ Не удалось отправить код")

@bot.callback_query_handler(func=lambda call: call.data.startswith('wait_code_'))
def wait_code(call):
    bot.answer_callback_query(call.id, "🔄 Ожидайте код")
    idx = int(call.data.split('_')[2])
    data['orders'][idx]['code_waiting'] = True
    save_data(data)
    
    bot.send_message(call.message.chat.id, "✅ Вы уведомлены. Администратор отправит код в этот чат.")
    
    admin_ids = [str(ADMIN_ID)] + data.get('admins', [])
    for admin_id in admin_ids:
        try:
            bot.send_message(admin_id, f"🔄 Пользователь ждёт код для заказа #{data['orders'][idx]['id']}")
        except:
            pass

# ========== 11. ДОБАВИТЬ НОМЕР ==========
@bot.callback_query_handler(func=lambda call: call.data == "add_number")
def add_number(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "✏️ Введите страну и цену (например: Россия - 500):")
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
        
        data['catalog'].append({"country": country, "price": price})
        save_data(data)
        bot.edit_message_text(f"✅ Добавлено: {country} - {price}₽", chat_id, message_id)
        time.sleep(0.5)
        admin_panel_after(msg)
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка: {e}\nИспользуйте: Страна - Цена (например: Россия - 500)")

def admin_panel_after(msg):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Статистика", callback_data="statistics", style="primary"),
        InlineKeyboardButton("📋 Заказы", callback_data="orders_list", style="primary"),
        InlineKeyboardButton("➕ Добавить номер", callback_data="add_number", style="success"),
        InlineKeyboardButton("🗑 Удалить номер", callback_data="delete_number", style="danger"),
        InlineKeyboardButton("✏️ Текст приветствия", callback_data="edit_welcome", style="primary"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu", style="danger")
    )
    bot.send_message(msg.chat.id, "🛠 АДМИН ПАНЕЛЬ", reply_markup=markup)

# ========== 12. УДАЛИТЬ НОМЕР ==========
@bot.callback_query_handler(func=lambda call: call.data == "delete_number")
def delete_number(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    if not data['catalog']:
        bot.send_message(call.message.chat.id, "❌ Нет номеров для удаления")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(f"❌ {item['country']} - {item['price']}₽", callback_data=f"del_{idx}", style="danger"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary"))
    
    bot.edit_message_text("🗑 Выберите номер для удаления:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_catalog_item(call):
    if not is_admin(call.from_user.id):
        return
    
    idx = int(call.data.split('_')[1])
    item = data['catalog'].pop(idx)
    save_data(data)
    
    bot.answer_callback_query(call.id, f"✅ Удалено: {item['country']} - {item['price']}₽")
    admin_panel_after(call)

# ========== 13. ИЗМЕНИТЬ ПРИВЕТСТВИЕ ==========
@bot.callback_query_handler(func=lambda call: call.data == "edit_welcome")
def edit_welcome(call):
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        f"✏️ Введите новое приветствие:\n\nТекущее:\n{data['settings'].get('welcome_text', '')}"
    )
    bot.register_next_step_handler(msg, lambda m: set_welcome(m, call.message.chat.id, call.message.message_id))

def set_welcome(msg, chat_id, message_id):
    data['settings']['welcome_text'] = msg.text
    save_data(data)
    bot.edit_message_text("✅ Приветствие обновлено!", chat_id, message_id)

# ========== 14. НАЗАД В МЕНЮ ==========
@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    show_main_menu(call.message.chat.id)

# ========== 15. ЗАПУСК ==========
if __name__ == '__main__':
    print("✅ SIALENS Физ бот запущен")
    print(f"👤 Главный админ: {ADMIN_ID}")
    print(f"👥 Доп. админы: {data.get('admins', [])}")
    
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)