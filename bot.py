import telebot
from config import TOKEN, ADMIN_ID
import json
import os
import time
import threading
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

bot = telebot.TeleBot(TOKEN)
SUPPORT_LINK = "https://t.me/deverskyi"

def load_data():
    if not os.path.exists('data.json'):
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump({
                "catalog": [],
                "orders": [],
                "stats": {"users": [], "visits": 0, "user_details": {}, "accepted_users": []},
                "settings": {
                    "welcome": "Добро пожаловать в SIALENS Физ!",
                    "legal": {
                        "agreement_text": "📜 <b>Покупая номер в нашем боте, вы соглашаетесь с условиями:</b>\n\n• <a href='https://telegra.ph/Politika-konfidencialnosti-07-17-132'>Политика конфиденциальности</a>\n• <a href='https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17'>Публичная оферта</a>\n\nНажимая кнопку ниже, вы принимаете все условия.",
                        "privacy_link": "https://telegra.ph/Politika-konfidencialnosti-07-17-132",
                        "offer_link": "https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17",
                        "accept_button": "✅ Я принимаю условия",
                        "show_legal": True
                    },
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

def smooth_execute(func, *args, **kwargs):
    time.sleep(0.3)
    func(*args, **kwargs)

# ============================================================
# СТАРТ
# ============================================================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or "Нет юзернейма"
    first_name = message.from_user.first_name or "Без имени"
    
    if user_id not in data['stats']['users']:
        data['stats']['users'].append(user_id)
        data['stats']['user_details'][user_id] = {
            "username": username,
            "first_name": first_name,
            "first_visit": time.ctime(),
            "last_visit": time.ctime(),
            "accepted": False
        }
    else:
        data['stats']['user_details'][user_id]["last_visit"] = time.ctime()
    
    data['stats']['visits'] += 1
    save_data()
    
    if user_id not in data['stats']['accepted_users']:
        show_legal_agreement(message)
    else:
        show_main_menu(message)

# ============================================================
# ЮРИДИЧЕСКОЕ СОГЛАШЕНИЕ
# ============================================================

def show_legal_agreement(message):
    legal = data['settings']['legal']
    
    if not legal.get('show_legal', True):
        data['stats']['accepted_users'].append(str(message.from_user.id))
        save_data()
        show_main_menu(message)
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    
    if legal.get('privacy_link'):
        markup.add(InlineKeyboardButton("📋 Политика конфиденциальности", url=legal['privacy_link']))
    if legal.get('offer_link'):
        markup.add(InlineKeyboardButton("📄 Публичная оферта", url=legal['offer_link']))
    
    markup.add(InlineKeyboardButton(legal.get('accept_button', '✅ Я принимаю условия'), callback_data='accept_legal'))
    
    bot.send_message(
        message.chat.id,
        legal.get('agreement_text', '📜 Пожалуйста, ознакомьтесь с условиями и примите их.'),
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.callback_query_handler(func=lambda call: call.data == 'accept_legal')
def accept_legal(call):
    user_id = str(call.from_user.id)
    
    if user_id not in data['stats']['accepted_users']:
        data['stats']['accepted_users'].append(user_id)
        if user_id in data['stats']['user_details']:
            data['stats']['user_details'][user_id]['accepted'] = True
        save_data()
    
    bot.answer_callback_query(call.id, "✅ Условия приняты!")
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    show_main_menu(call.message)

# ============================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================

def show_main_menu(message):
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
    threading.Thread(target=smooth_execute, args=(buy_menu_after, call)).start()

def buy_menu_after(call):
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

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def select_country(call):
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(select_country_after, call)).start()

def select_country_after(call):
    idx = int(call.data.split('_')[1])
    item = data['catalog'][idx]
    msg = bot.send_message(call.message.chat.id, 
        f"💳 Оплатите {item['price']}₽ на номер:\n<b>+79103552521</b> (Сбербанк)\n\n📸 После оплаты пришлите СКРИНШОТ.",
        parse_mode='HTML')
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
        InlineKeyboardButton("✅ Принять", callback_data=f"accept_{order_idx}", style="success"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{order_idx}", style="danger"),
        InlineKeyboardButton("✏️ Написать", callback_data=f"reply_{order_idx}", style="primary")
    )
    bot.send_photo(ADMIN_ID, file_id, 
        f"🆕 НОВЫЙ ЗАКАЗ #{order['id']}\n👤 {msg.from_user.first_name} (@{msg.from_user.username})\n🌍 {data['catalog'][idx]['country']}\n💰 {data['catalog'][idx]['price']}₽",
        reply_markup=markup)

# ============================================================
# КНОПКА: НАЗАД
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_start')
def back_to_start(call):
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(show_main_menu, call.message)).start()

# ============================================================
# АДМИН ПАНЕЛЬ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_panel')
def admin_panel(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(admin_panel_after, call)).start()

def admin_panel_after(call):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Статистика", callback_data='admin_stats', style="primary"),
        InlineKeyboardButton("👥 Юзеры", callback_data='admin_users', style="primary"),
        InlineKeyboardButton("📋 Заказы", callback_data='admin_orders', style="primary"),
        InlineKeyboardButton("➕ Добавить номер", callback_data='admin_add', style="success"),
        InlineKeyboardButton("🗑 Удалить номер", callback_data='admin_delete', style="danger"),
        InlineKeyboardButton("✏️ Редакт. кнопки", callback_data='admin_edit_buttons', style="primary"),
        InlineKeyboardButton("📝 Приветствие", callback_data='admin_edit_welcome', style="primary"),
        InlineKeyboardButton("⚖️ Юридические", callback_data='admin_legal', style="primary"),
        InlineKeyboardButton("💬 Рассылка", callback_data='admin_broadcast', style="primary"),
        InlineKeyboardButton("🔙 Выход", callback_data='back_to_start', style="danger")
    )
    bot.edit_message_text("🛠 АДМИН ПАНЕЛЬ", call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# АДМИН: ЮРИДИЧЕСКИЕ ДОКУМЕНТЫ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_legal')
def admin_legal(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(admin_legal_after, call)).start()

def admin_legal_after(call):
    legal = data['settings']['legal']
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📝 Изменить текст согласия", callback_data='legal_text', style="primary"),
        InlineKeyboardButton("🔗 Изменить ссылку на политику", callback_data='legal_privacy', style="primary"),
        InlineKeyboardButton("🔗 Изменить ссылку на оферту", callback_data='legal_offer', style="primary"),
        InlineKeyboardButton("📌 Изменить текст кнопки", callback_data='legal_button', style="primary"),
        InlineKeyboardButton("🔄 Включить/отключить", callback_data='legal_toggle', style="danger"),
        InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary")
    )
    status = "ВКЛЮЧЕН" if legal.get('show_legal', True) else "ВЫКЛЮЧЕН"
    bot.edit_message_text(
        f"⚖️ ЮРИДИЧЕСКИЕ ДОКУМЕНТЫ\n\n"
        f"📌 Статус: {status}\n"
        f"📝 Текст согласия:\n{legal.get('agreement_text', 'Не задан')[:150]}...\n"
        f"🔗 Политика: {legal.get('privacy_link', 'Не задана')}\n"
        f"🔗 Оферта: {legal.get('offer_link', 'Не задана')}\n"
        f"📌 Кнопка: {legal.get('accept_button', 'Не задана')}",
        call.message.chat.id, call.message.message_id, reply_markup=markup
    )

# ============================================================
# ИЗМЕНЕНИЕ ЮРИДИЧЕСКИХ ТЕКСТОВ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'legal_text')
def legal_text(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id, "✏️ Введите текст")
    msg = bot.send_message(call.message.chat.id, 
        f"✏️ Введите НОВЫЙ ТЕКСТ СОГЛАСИЯ:\n\n"
        f"📌 Текущий:\n{data['settings']['legal']['agreement_text']}\n\n"
        f"💡 Можно использовать HTML: <b>жирный</b>, <a href='ссылка'>текст</a>"
    )
    bot.register_next_step_handler(msg, lambda m: set_legal_text(m, call.message.chat.id, call.message.message_id))

def set_legal_text(msg, chat_id, message_id):
    data['settings']['legal']['agreement_text'] = msg.text
    save_data()
    bot.edit_message_text("✅ Текст согласия обновлён!", chat_id, message_id)
    time.sleep(0.5)
    admin_legal_after(msg)

@bot.callback_query_handler(func=lambda call: call.data == 'legal_privacy')
def legal_privacy(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id, "🔗 Введите ссылку")
    msg = bot.send_message(call.message.chat.id, 
        f"🔗 Введите ССЫЛКУ НА ПОЛИТИКУ КОНФИДЕНЦИАЛЬНОСТИ:\n\n"
        f"📌 Текущая: {data['settings']['legal']['privacy_link']}\n\n"
        f"💡 Пример: https://telegra.ph/..."
    )
    bot.register_next_step_handler(msg, lambda m: set_legal_privacy(m, call.message.chat.id, call.message.message_id))

def set_legal_privacy(msg, chat_id, message_id):
    data['settings']['legal']['privacy_link'] = msg.text
    save_data()
    bot.edit_message_text(f"✅ Ссылка на политику обновлена: {msg.text}", chat_id, message_id)
    time.sleep(0.5)
    admin_legal_after(msg)

@bot.callback_query_handler(func=lambda call: call.data == 'legal_offer')
def legal_offer(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id, "🔗 Введите ссылку")
    msg = bot.send_message(call.message.chat.id, 
        f"🔗 Введите ССЫЛКУ НА ПУБЛИЧНУЮ ОФЕРТУ:\n\n"
        f"📌 Текущая: {data['settings']['legal']['offer_link']}\n\n"
        f"💡 Пример: https://telegra.ph/..."
    )
    bot.register_next_step_handler(msg, lambda m: set_legal_offer(m, call.message.chat.id, call.message.message_id))

def set_legal_offer(msg, chat_id, message_id):
    data['settings']['legal']['offer_link'] = msg.text
    save_data()
    bot.edit_message_text(f"✅ Ссылка на оферту обновлена: {msg.text}", chat_id, message_id)
    time.sleep(0.5)
    admin_legal_after(msg)

@bot.callback_query_handler(func=lambda call: call.data == 'legal_button')
def legal_button(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id, "📌 Введите текст")
    msg = bot.send_message(call.message.chat.id, 
        f"📌 Введите НОВЫЙ ТЕКСТ КНОПКИ СОГЛАСИЯ:\n\n"
        f"📌 Текущий: {data['settings']['legal']['accept_button']}\n\n"
        f"💡 Можно использовать эмодзи: ✅ ☑️ 📋"
    )
    bot.register_next_step_handler(msg, lambda m: set_legal_button(m, call.message.chat.id, call.message.message_id))

def set_legal_button(msg, chat_id, message_id):
    data['settings']['legal']['accept_button'] = msg.text
    save_data()
    bot.edit_message_text(f"✅ Текст кнопки обновлён: {msg.text}", chat_id, message_id)
    time.sleep(0.5)
    admin_legal_after(msg)

@bot.callback_query_handler(func=lambda call: call.data == 'legal_toggle')
def legal_toggle(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    current = data['settings']['legal'].get('show_legal', True)
    data['settings']['legal']['show_legal'] = not current
    save_data()
    status = "ВКЛЮЧЕН" if data['settings']['legal']['show_legal'] else "ВЫКЛЮЧЕН"
    bot.send_message(call.message.chat.id, f"🔄 Юридический блок {status}")
    time.sleep(0.5)
    admin_legal_after(call)

# ============================================================
# АДМИН: СТАТИСТИКА
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_stats')
def admin_stats(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(admin_stats_after, call)).start()

def admin_stats_after(call):
    total_users = len(data['stats']['users'])
    total_visits = data['stats']['visits']
    total_orders = len(data['orders'])
    accepted = len(data['stats']['accepted_users'])
    pending = len([o for o in data['orders'] if o['status'] == 'waiting_approval'])
    approved = len([o for o in data['orders'] if o['status'] == 'approved'])
    rejected = len([o for o in data['orders'] if o['status'] == 'rejected'])
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_panel', style="primary"))
    bot.edit_message_text(
        f"📊 СТАТИСТИКА\n\n"
        f"👤 Всего юзеров: {total_users}\n"
        f"✅ Приняли условия: {accepted}\n"
        f"👀 Визитов: {total_visits}\n"
        f"📦 Заказов: {total_orders}\n"
        f"⏳ Ожидают: {pending}\n"
        f"✅ Одобрено: {approved}\n"
        f"❌ Отклонено: {rejected}",
        call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# АДМИН: ЮЗЕРЫ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_users')
def admin_users(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(admin_users_after, call)).start()

def admin_users_after(call):
    users_text = "👥 СПИСОК ЮЗЕРОВ:\n\n"
    for uid, info in data['stats']['user_details'].items():
        users_text += f"🆔 {uid}\n"
        users_text += f"👤 {info['first_name']} (@{info['username']})\n"
        users_text += f"✅ Принял: {'Да' if info.get('accepted', False) else 'Нет'}\n"
        users_text += f"📅 Первый: {info['first_visit']}\n"
        users_text += f"📅 Последний: {info['last_visit']}\n\n"
    
    if len(users_text) > 4000:
        users_text = users_text[:3900] + "\n... и ещё"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_panel', style="primary"))
    bot.edit_message_text(users_text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# АДМИН: ЗАКАЗЫ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_orders')
def admin_orders(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(admin_orders_after, call)).start()

def admin_orders_after(call):
    if not data['orders']:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_panel', style="primary"))
        bot.edit_message_text("📭 Нет заказов", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for order in data['orders'][-10:]:
        status_emoji = "⏳" if order['status'] == 'waiting_approval' else "✅" if order['status'] == 'approved' else "❌"
        markup.add(InlineKeyboardButton(
            f"#{order['id']} {order['country']} - {order['price']}₽ {status_emoji}",
            callback_data=f"order_{data['orders'].index(order)}",
            style="primary"
        ))
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_panel', style="primary"))
    bot.edit_message_text("📋 ПОСЛЕДНИЕ ЗАКАЗЫ:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('order_'))
def order_detail(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(order_detail_after, call)).start()

def order_detail_after(call):
    idx = int(call.data.split('_')[1])
    order = data['orders'][idx]
    status_map = {"waiting_approval": "⏳ Ожидает", "approved": "✅ Одобрен", "rejected": "❌ Отклонён", "code_sent": "📨 Код отправлен"}
    markup = InlineKeyboardMarkup(row_width=2)
    if order['status'] == 'waiting_approval':
        markup.add(
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{idx}", style="success"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{idx}", style="danger")
        )
        markup.add(InlineKeyboardButton("✏️ Написать", callback_data=f"reply_{idx}", style="primary"))
    if order['status'] == 'approved' and not order['code_waiting']:
        markup.add(InlineKeyboardButton("📨 Отправить код", callback_data=f"send_code_{idx}", style="success"))
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_orders', style="primary"))
    bot.edit_message_text(
        f"📦 ЗАКАЗ #{order['id']}\n\n👤 {order['first_name']} (@{order['username']})\n🆔 {order['user_id']}\n🌍 {order['country']}\n💰 {order['price']}₽\n📅 {time.ctime(order['date'])}\n📊 {status_map.get(order['status'], order['status'])}\n📱 {order['phone'] or 'Не выдан'}\n🔄 Код: {'Ждёт' if order['code_waiting'] else 'Не ждёт'}",
        call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# ПРИНЯТЬ/ОТКЛОНИТЬ/НАПИСАТЬ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
def accept_order(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(accept_order_after, call)).start()

def accept_order_after(call):
    idx = int(call.data.split('_')[1])
    if data['orders'][idx]['status'] != 'waiting_approval':
        bot.send_message(call.message.chat.id, "❌ Уже обработан")
        return
    msg = bot.send_message(call.message.chat.id, "📱 Введите номер:")
    bot.register_next_step_handler(msg, lambda m: set_phone(m, idx, call.message.chat.id, call.message.message_id))

def set_phone(msg, idx, chat_id, message_id):
    phone = msg.text
    data['orders'][idx]['phone'] = phone
    data['orders'][idx]['status'] = 'approved'
    save_data()
    bot.edit_message_text(f"✅ Заказ #{data['orders'][idx]['id']} принят. Номер {phone} выдан.", chat_id, message_id)
    user_id = data['orders'][idx]['user_id']
    try:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(data['settings']['buttons']['wait_code']['text'], callback_data=f"wait_code_{idx}", style="primary"))
        bot.send_message(user_id, f"✅ Заказ одобрен!\n📱 Номер: {phone}\n\n🔐 ИНСТРУКЦИЯ:\n1. Введите номер в Telegram\n2. Нажмите «{data['settings']['buttons']['wait_code']['text']}»\n3. Получите код", reply_markup=markup)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_order(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(reject_order_after, call)).start()

def reject_order_after(call):
    idx = int(call.data.split('_')[1])
    if data['orders'][idx]['status'] != 'waiting_approval':
        bot.send_message(call.message.chat.id, "❌ Уже обработан")
        return
    msg = bot.send_message(call.message.chat.id, "✏️ Причина отказа:")
    bot.register_next_step_handler(msg, lambda m: set_reject(m, idx, call.message.chat.id, call.message.message_id))

def set_reject(msg, idx, chat_id, message_id):
    reason = msg.text
    data['orders'][idx]['status'] = 'rejected'
    save_data()
    bot.edit_message_text(f"❌ Заказ #{data['orders'][idx]['id']} отклонён.\nПричина: {reason}", chat_id, message_id)
    try:
        bot.send_message(data['orders'][idx]['user_id'], f"❌ Ваш заказ отклонён.\nПричина: {reason}")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def reply_to_user(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(reply_to_user_after, call)).start()

def reply_to_user_after(call):
    idx = int(call.data.split('_')[1])
    msg = bot.send_message(call.message.chat.id, "✏️ Сообщение:")
    bot.register_next_step_handler(msg, lambda m: send_reply(m, idx))

def send_reply(msg, idx):
    try:
        bot.send_message(data['orders'][idx]['user_id'], f"📩 {msg.text}")
        bot.send_message(msg.chat.id, "✅ Отправлено")
    except:
        bot.send_message(msg.chat.id, "❌ Ошибка")

# ============================================================
# ОТПРАВИТЬ КОД / ЖДУ КОД
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_code_'))
def send_code(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(send_code_after, call)).start()

def send_code_after(call):
    idx = int(call.data.split('_')[1])
    msg = bot.send_message(call.message.chat.id, "✏️ Введите код:")
    bot.register_next_step_handler(msg, lambda m: send_code_to_user(m, idx))

def send_code_to_user(msg, idx):
    code = msg.text
    data['orders'][idx]['code_waiting'] = False
    data['orders'][idx]['status'] = 'code_sent'
    save_data()
    try:
        bot.send_message(data['orders'][idx]['user_id'], f"📨 Код: {code}")
        bot.send_message(msg.chat.id, "✅ Отправлено")
    except:
        bot.send_message(msg.chat.id, "❌ Ошибка")

@bot.callback_query_handler(func=lambda call: call.data.startswith('wait_code_'))
def wait_code(call):
    bot.answer_callback_query(call.id, "🔄 Ожидайте")
    threading.Thread(target=smooth_execute, args=(wait_code_after, call)).start()

def wait_code_after(call):
    idx = int(call.data.split('_')[1])
    data['orders'][idx]['code_waiting'] = True
    save_data()
    bot.send_message(call.message.chat.id, "✅ Администратор получил уведомление")
    bot.send_message(ADMIN_ID, f"🔄 Пользователь ждёт код для заказа #{data['orders'][idx]['id']}")

# ============================================================
# ДОБАВИТЬ НОМЕР (ИСПРАВЛЕНО)
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_add')
def add_number(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(add_number_after, call)).start()

def add_number_after(call):
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
        save_data()
        bot.edit_message_text(f"✅ Добавлено: {country} - {price}₽", chat_id, message_id)
        time.sleep(0.5)
        
        # Показываем админ-панель заново
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📊 Статистика", callback_data='admin_stats', style="primary"),
            InlineKeyboardButton("👥 Юзеры", callback_data='admin_users', style="primary"),
            InlineKeyboardButton("📋 Заказы", callback_data='admin_orders', style="primary"),
            InlineKeyboardButton("➕ Добавить номер", callback_data='admin_add', style="success"),
            InlineKeyboardButton("🗑 Удалить номер", callback_data='admin_delete', style="danger"),
            InlineKeyboardButton("✏️ Редакт. кнопки", callback_data='admin_edit_buttons', style="primary"),
            InlineKeyboardButton("📝 Приветствие", callback_data='admin_edit_welcome', style="primary"),
            InlineKeyboardButton("⚖️ Юридические", callback_data='admin_legal', style="primary"),
            InlineKeyboardButton("💬 Рассылка", callback_data='admin_broadcast', style="primary"),
            InlineKeyboardButton("🔙 Выход", callback_data='back_to_start', style="danger")
        )
        bot.send_message(msg.chat.id, "🛠 АДМИН ПАНЕЛЬ", reply_markup=markup)
        
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка: {e}\nИспользуйте: Страна - Цена (например: Россия - 500)")

# ============================================================
# УДАЛИТЬ НОМЕР
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_delete')
def delete_number(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(delete_number_after, call)).start()

def delete_number_after(call):
    if not data['catalog']:
        bot.send_message(call.message.chat.id, "❌ Нет номеров")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(f"❌ {item['country']} - {item['price']}₽", callback_data=f"del_{idx}", style="danger"))
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back']['text'], callback_data='admin_panel', style="primary"))
    bot.edit_message_text("🗑 Выберите:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_catalog_item(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    idx = int(call.data.split('_')[1])
    item = data['catalog'].pop(idx)
    save_data()
    bot.answer_callback_query(call.id, f"✅ Удалено: {item['country']}")
    admin_panel_after(call)

# ============================================================
# РЕДАКТИРОВАТЬ КНОПКИ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_edit_buttons')
def admin_edit_buttons(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(admin_edit_buttons_after, call)).start()

def admin_edit_buttons_after(call):
    markup = InlineKeyboardMarkup(row_width=1)
    for key, btn in data['settings']['buttons'].items():
        markup.add(InlineKeyboardButton(f"✏️ {btn['text']}", callback_data=f"edit_{key}", style="primary"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary"))
    bot.edit_message_text("🛠 ВЫБЕРИТЕ КНОПКУ:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_button_menu(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(edit_button_menu_after, call)).start()

def edit_button_menu_after(call):
    key = call.data.split('_')[1]
    btn = data['settings']['buttons'][key]
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📝 Изменить текст", callback_data=f"edit_text_{key}", style="primary"),
        InlineKeyboardButton("🎨 Изменить цвет", callback_data=f"edit_color_{key}", style="primary"),
        InlineKeyboardButton("🔙 Назад", callback_data='admin_edit_buttons', style="primary")
    )
    bot.edit_message_text(
        f"🛠 НАСТРОЙКА\n\n📌 Текст: {btn['text']}\n🎨 Цвет: {btn['color']}\n\n💡 Цвета: #ff0000 (красный), #00ff00 (зелёный), #0000ff (синий), #ff8800 (оранжевый)",
        call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_text_'))
def edit_button_text(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    key = call.data.split('_')[2]
    bot.answer_callback_query(call.id, "✏️ Введите текст")
    msg = bot.send_message(call.message.chat.id, f"✏️ Новый текст для кнопки:\n\n📌 Текущий: {data['settings']['buttons'][key]['text']}")
    bot.register_next_step_handler(msg, lambda m: set_button_text(m, key, call.message.chat.id, call.message.message_id))

def set_button_text(msg, key, chat_id, message_id):
    data['settings']['buttons'][key]['text'] = msg.text
    save_data()
    bot.edit_message_text(f"✅ Текст обновлён: {msg.text}", chat_id, message_id)
    time.sleep(0.5)
    admin_edit_buttons_after(msg)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_color_'))
def edit_button_color(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return
    key = call.data.split('_')[2]
    bot.answer_callback_query(call.id, "🎨 Введите цвет")
    msg = bot.send_message(call.message.chat.id, 
        f"🎨 Введите цвет:\n\n📌 Текущий: {data['settings']['buttons'][key]['color']}\n\n"
        f"📌 Названия: красный, синий, зелёный, оранжевый, розовый\n"
        f"📌 HEX: #ff0000, #00ff00, #0000ff")
    bot.register_next_step_handler(msg, lambda m: set_button_color(m, key, call.message.chat.id, call.message.message_id))

def set_button_color(msg, key, chat_id, message_id):
    color_map = {
        "красный": "#ff0000", "зелёный": "#00ff00", "зеленый": "#00ff00",
        "синий": "#0000ff", "оранжевый": "#ff8800", "розовый": "#ff00ff",
        "желтый": "#ffff00", "жёлтый": "#ffff00", "фиолетовый": "#8800ff",
        "черный": "#000000", "чёрный": "#000000", "белый": "#ffffff",
        "серый": "#888888", "голубой": "#00ffff"
    }
    color = msg.text.strip()
    if color.lower() in color_map:
        color = color_map[color.lower()]
    elif not color.startswith('#'):
        color = '#' + color
    
    data['settings']['buttons'][key]['color'] = color
    save_data()
    bot.edit_message_text(f"✅ Цвет обновлён: {color}", chat_id, message_id)
    time.sleep(0.5)
    admin_edit_buttons_after(msg)

# ============================================================
# ИЗМЕНИТЬ ПРИВЕТСТВИЕ
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_edit_welcome')
def edit_welcome(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(edit_welcome_after, call)).start()

def edit_welcome_after(call):
    msg = bot.send_message(call.message.chat.id, f"✏️ Новое приветствие:\n\n📌 Текущее:\n{data['settings']['welcome']}")
    bot.register_next_step_handler(msg, lambda m: set_welcome(m, call.message.chat.id, call.message.message_id))

def set_welcome(msg, chat_id, message_id):
    data['settings']['welcome'] = msg.text
    save_data()
    bot.edit_message_text(f"✅ Приветствие обновлено!", chat_id, message_id)

# ============================================================
# РАССЫЛКА
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == 'admin_broadcast')
def broadcast(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    threading.Thread(target=smooth_execute, args=(broadcast_after, call)).start()

def broadcast_after(call):
    msg = bot.send_message(call.message.chat.id, "✏️ Текст рассылки:")
    bot.register_next_step_handler(msg, lambda m: send_broadcast(m, call.message.chat.id, call.message.message_id))

def send_broadcast(msg, chat_id, message_id):
    count = 0
    for user_id in data['stats']['users']:
        try:
            bot.send_message(user_id, f"📢 {msg.text}")
            count += 1
        except:
            pass
    bot.edit_message_text(f"✅ Отправлено {count} пользователям", chat_id, message_id)

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