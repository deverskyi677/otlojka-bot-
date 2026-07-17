import telebot
from config import TOKEN, ADMIN_ID
import json
import os
import time
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

bot = telebot.TeleBot(TOKEN)
SUPPORT_LINK = "https://t.me/deverskyi"

# ========== ДАННЫЕ ==========
def load_data():
    if not os.path.exists('data.json'):
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump({
                "catalog": [],
                "orders": [],
                "stats": {"users": [], "visits": 0, "user_details": {}, "accepted_users": []},
                "admins": [],
                "settings": {
                    "welcome": "Добро пожаловать в SIALENS Физ!",
                    "texts": {
                        "approve": "✅ ВАШ ПЛАТЕЖ ОДОБРЕН!",
                        "reject": "❌ Ваш платеж отклонён.",
                        "after_approve": "✅ ВАШ ПЛАТЕЖ ОДОБРЕН!\n\n📱 Ваш номер: {phone}\n\n🔐 ИНСТРУКЦИЯ:\n1️⃣ Введите номер в Telegram\n2️⃣ Вернитесь в чат с ботом\n3️⃣ Нажмите кнопку «Жду код»\n4️⃣ Получите код"
                    },
                    "legal": {
                        "agreement_text": "📜 <b>Покупая номер, вы соглашаетесь с условиями:</b>\n\n• <a href='https://telegra.ph/Politika-konfidencialnosti-07-17-132'>Политика конфиденциальности</a>\n• <a href='https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17'>Публичная оферта</a>",
                        "privacy_link": "https://telegra.ph/Politika-konfidencialnosti-07-17-132",
                        "offer_link": "https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17",
                        "accept_button": "✅ Я принимаю условия",
                        "show_legal": True
                    },
                    "buttons": {
                        "buy": "📱 Купить номер",
                        "support": "📞 Связь с поддержкой",
                        "admin": "🛠 Админ панель",
                        "back": "🔙 Назад",
                        "wait_code": "🔄 Я вернулся, жду код"
                    }
                }
            }, f, ensure_ascii=False, indent=2)
    with open('data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

data = load_data()
def save_data():
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user_id):
    return str(user_id) == str(ADMIN_ID) or str(user_id) in data.get('admins', [])

# ========== СТАРТ ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id not in data['stats']['users']:
        data['stats']['users'].append(user_id)
        data['stats']['user_details'][user_id] = {
            "first_name": message.from_user.first_name,
            "username": message.from_user.username,
            "first_visit": time.ctime(),
            "last_visit": time.ctime(),
            "accepted": False
        }
    else:
        data['stats']['user_details'][user_id]["last_visit"] = time.ctime()
    data['stats']['visits'] += 1
    save_data()

    if user_id not in data['stats']['accepted_users'] and data['settings']['legal'].get('show_legal', True):
        show_legal(message)
    else:
        show_main_menu(message)

def show_legal(message):
    legal = data['settings']['legal']
    markup = InlineKeyboardMarkup(row_width=1)
    if legal.get('privacy_link'):
        markup.add(InlineKeyboardButton("📋 Политика", url=legal['privacy_link']))
    if legal.get('offer_link'):
        markup.add(InlineKeyboardButton("📄 Оферта", url=legal['offer_link']))
    markup.add(InlineKeyboardButton(legal.get('accept_button', '✅ Принять'), callback_data='accept_legal'))
    bot.send_message(message.chat.id, legal.get('agreement_text', 'Примите условия'), reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'accept_legal')
def accept_legal(call):
    user_id = str(call.from_user.id)
    if user_id not in data['stats']['accepted_users']:
        data['stats']['accepted_users'].append(user_id)
        data['stats']['user_details'][user_id]['accepted'] = True
        save_data()
    bot.answer_callback_query(call.id, "✅ Принято!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    show_main_menu(call.message)

def show_main_menu(message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(data['settings']['buttons']['buy'], callback_data='buy'),
        InlineKeyboardButton(data['settings']['buttons']['support'], url=SUPPORT_LINK)
    )
    if is_admin(message.from_user.id):
        markup.add(InlineKeyboardButton(data['settings']['buttons']['admin'], callback_data='admin_panel'))
    bot.send_message(message.chat.id, data['settings']['welcome'], reply_markup=markup)

# ========== ПОКУПКА ==========
@bot.callback_query_handler(func=lambda call: call.data == 'buy')
def buy(call):
    bot.answer_callback_query(call.id)
    if not data['catalog']:
        bot.send_message(call.message.chat.id, "❌ Нет номеров")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(f"{item['country']} - {item['price']}₽", callback_data=f"buy_{idx}"))
    markup.add(InlineKeyboardButton(data['settings']['buttons']['back'], callback_data='back_to_start'))
    bot.edit_message_text("🌍 Выберите страну:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_select(call):
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    item = data['catalog'][idx]
    msg = bot.send_message(call.message.chat.id, f"💳 Оплатите {item['price']}₽ на номер +79103552521\n📸 Пришлите скриншот")
    bot.register_next_step_handler(msg, lambda m: handle_screenshot(m, idx))

def handle_screenshot(msg, idx):
    if not msg.photo:
        bot.send_message(msg.chat.id, "❌ Это не фото")
        bot.register_next_step_handler(msg, lambda m: handle_screenshot(m, idx))
        return
    order = {
        "id": len(data['orders']) + 1,
        "user_id": str(msg.from_user.id),
        "username": msg.from_user.username or "Нет",
        "first_name": msg.from_user.first_name,
        "country": data['catalog'][idx]['country'],
        "price": data['catalog'][idx]['price'],
        "screenshot": msg.photo[-1].file_id,
        "status": "waiting_approval",
        "phone": None,
        "code_waiting": False,
        "date": time.time()
    }
    data['orders'].append(order)
    save_data()
    bot.send_message(msg.chat.id, "✅ Скрин отправлен на проверку")

    # Отправляем всем админам
    admin_ids = [str(ADMIN_ID)] + data.get('admins', [])
    markup = InlineKeyboardMarkup(row_width=2)
    idx_order = len(data['orders']) - 1
    markup.add(
        InlineKeyboardButton("✅ Принять", callback_data=f"accept_{idx_order}", style="success"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{idx_order}", style="danger")
    )
    markup.add(InlineKeyboardButton("✏️ Написать", callback_data=f"reply_{idx_order}", style="primary"))
    for admin_id in admin_ids:
        try:
            bot.send_photo(admin_id, order['screenshot'],
                f"🆕 ЗАКАЗ #{order['id']}\n👤 {order['first_name']} (@{order['username']})\n🌍 {order['country']}\n💰 {order['price']}₽",
                reply_markup=markup)
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_start')
def back_to_start(call):
    bot.answer_callback_query(call.id)
    show_main_menu(call.message)

# ========== АДМИН ПАНЕЛЬ ==========
@bot.callback_query_handler(func=lambda call: call.data == 'admin_panel')
def admin_panel(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Нет доступа")
        return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Статистика", callback_data='stats', style="primary"),
        InlineKeyboardButton("👥 Юзеры", callback_data='users', style="primary"),
        InlineKeyboardButton("📋 Заказы", callback_data='orders', style="primary"),
        InlineKeyboardButton("➕ Добавить номер", callback_data='add_num', style="success"),
        InlineKeyboardButton("🗑 Удалить номер", callback_data='del_num', style="danger"),
        InlineKeyboardButton("✏️ Ред. кнопки", callback_data='edit_btns', style="primary"),
        InlineKeyboardButton("📝 Приветствие", callback_data='edit_welcome', style="primary"),
        InlineKeyboardButton("✏️ Тексты", callback_data='edit_texts', style="primary"),
        InlineKeyboardButton("💬 Рассылка", callback_data='broadcast', style="primary"),
        InlineKeyboardButton("🔙 Выход", callback_data='back_to_start', style="danger")
    )
    if str(call.from_user.id) == str(ADMIN_ID):
        markup.add(
            InlineKeyboardButton("⚖️ Юр. документы", callback_data='legal', style="primary"),
            InlineKeyboardButton("👑 Админы", callback_data='manage_admins', style="danger")
        )
    bot.edit_message_text("🛠 АДМИН ПАНЕЛЬ", call.message.chat.id, call.message.message_id, reply_markup=markup)

# ========== СТАТИСТИКА ==========
@bot.callback_query_handler(func=lambda call: call.data == 'stats')
def stats(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    text = f"📊 Статистика\n\n👤 Юзеров: {len(data['stats']['users'])}\n✅ Приняли: {len(data['stats']['accepted_users'])}\n👀 Визитов: {data['stats']['visits']}\n📦 Заказов: {len(data['orders'])}\n⏳ Ожидают: {len([o for o in data['orders'] if o['status']=='waiting_approval'])}\n✅ Одобрено: {len([o for o in data['orders'] if o['status']=='approved'])}\n❌ Отклонено: {len([o for o in data['orders'] if o['status']=='rejected'])}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ========== ЮЗЕРЫ ==========
@bot.callback_query_handler(func=lambda call: call.data == 'users')
def users(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    text = "👥 Юзеры:\n\n"
    for uid, info in list(data['stats']['user_details'].items())[:20]:
        text += f"🆔 {uid} – {info['first_name']} (@{info['username']})\n✅ {info.get('accepted', False)}\n"
    if len(data['stats']['user_details']) > 20:
        text += f"\n... и ещё {len(data['stats']['user_details'])-20}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ========== ЗАКАЗЫ ==========
@bot.callback_query_handler(func=lambda call: call.data == 'orders')
def orders(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    if not data['orders']:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary"))
        bot.edit_message_text("📭 Нет заказов", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, order in enumerate(data['orders'][-10:]):
        status = "⏳" if order['status']=='waiting_approval' else "✅" if order['status']=='approved' else "❌"
        markup.add(InlineKeyboardButton(f"#{order['id']} {order['country']} {order['price']}₽ {status}", callback_data=f"order_{idx}"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary"))
    bot.edit_message_text("📋 Заказы:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('order_'))
def order_detail(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    order = data['orders'][idx]
    status_map = {"waiting_approval":"⏳ Ожидает","approved":"✅ Одобрен","rejected":"❌ Отклонён","code_sent":"📨 Код отправлен"}
    markup = InlineKeyboardMarkup(row_width=2)
    if order['status'] == 'waiting_approval':
        markup.add(
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{idx}", style="success"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{idx}", style="danger")
        )
        markup.add(InlineKeyboardButton("✏️ Написать", callback_data=f"reply_{idx}", style="primary"))
    if order['status'] == 'approved' and not order['code_waiting']:
        markup.add(InlineKeyboardButton("📨 Отправить код", callback_data=f"send_code_{idx}", style="success"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='orders', style="primary"))
    text = f"📦 ЗАКАЗ #{order['id']}\n👤 {order['first_name']} (@{order['username']})\n🌍 {order['country']}\n💰 {order['price']}₽\n📊 {status_map.get(order['status'], order['status'])}\n📱 {order['phone'] or 'Не выдан'}"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ========== ПРИНЯТЬ ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
def accept_order(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
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
    bot.edit_message_text(f"✅ Заказ #{data['orders'][idx]['id']} принят, номер {phone} выдан.", chat_id, message_id)
    # Уведомление пользователю
    user_id = data['orders'][idx]['user_id']
    try:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(data['settings']['buttons']['wait_code'], callback_data=f"wait_code_{idx}", style="primary"))
        text = data['settings']['texts'].get('after_approve', "✅ Одобрено!\n📱 {phone}").format(phone=phone)
        bot.send_message(user_id, text, reply_markup=markup)
        bot.send_message(msg.chat.id, "✅ Пользователю отправлено")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка: {e}")

# ========== ОТКЛОНИТЬ ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_order(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
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
    bot.edit_message_text(f"❌ Заказ #{data['orders'][idx]['id']} отклонён, причина: {reason}", chat_id, message_id)
    try:
        bot.send_message(data['orders'][idx]['user_id'], f"❌ Отклонён: {reason}")
    except:
        pass

# ========== НАПИСАТЬ ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def reply_order(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[1])
    msg = bot.send_message(call.message.chat.id, "✏️ Сообщение:")
    bot.register_next_step_handler(msg, lambda m: send_reply(m, idx))

def send_reply(msg, idx):
    try:
        bot.send_message(data['orders'][idx]['user_id'], f"📩 {msg.text}")
        bot.send_message(msg.chat.id, "✅ Отправлено")
    except:
        bot.send_message(msg.chat.id, "❌ Ошибка")

# ========== ОТПРАВИТЬ КОД ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('send_code_'))
def send_code(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
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

# ========== ЖДУ КОД ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('wait_code_'))
def wait_code(call):
    bot.answer_callback_query(call.id, "🔄 Ожидайте")
    idx = int(call.data.split('_')[1])
    data['orders'][idx]['code_waiting'] = True
    save_data()
    bot.send_message(call.message.chat.id, "✅ Уведомление отправлено")
    admin_ids = [str(ADMIN_ID)] + data.get('admins', [])
    for admin_id in admin_ids:
        try:
            bot.send_message(admin_id, f"🔄 Пользователь ждёт код для заказа #{data['orders'][idx]['id']}")
        except:
            pass

# ========== ДОБАВИТЬ НОМЕР ==========
@bot.callback_query_handler(func=lambda call: call.data == 'add_num')
def add_num(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "✏️ Страна - Цена (Россия - 500):")
    bot.register_next_step_handler(msg, lambda m: add_catalog(m, call.message.chat.id, call.message.message_id))

def add_catalog(msg, chat_id, message_id):
    try:
        parts = re.split(r'[-–—]', msg.text)
        if len(parts) == 2:
            country = parts[0].strip()
            price = int(re.sub(r'\D', '', parts[1].strip()))
        else:
            words = msg.text.split()
            country = ' '.join(words[:-1])
            price = int(re.sub(r'\D', '', words[-1]))
        data['catalog'].append({"country": country, "price": price})
        save_data()
        bot.edit_message_text(f"✅ Добавлено: {country} - {price}₽", chat_id, message_id)
        time.sleep(0.5)
        admin_panel_after(msg)
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка: {e}")

# ========== УДАЛИТЬ НОМЕР ==========
@bot.callback_query_handler(func=lambda call: call.data == 'del_num')
def del_num(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    if not data['catalog']:
        bot.send_message(call.message.chat.id, "❌ Нет номеров")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(data['catalog']):
        markup.add(InlineKeyboardButton(f"❌ {item['country']} - {item['price']}₽", callback_data=f"del_cat_{idx}", style="danger"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary"))
    bot.edit_message_text("🗑 Выберите:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_cat_'))
def del_cat(call):
    if not is_admin(call.from_user.id):
        return
    idx = int(call.data.split('_')[2])
    item = data['catalog'].pop(idx)
    save_data()
    bot.answer_callback_query(call.id, f"✅ Удалено {item['country']}")
    admin_panel_after(call)

# ========== РЕДАКТИРОВАТЬ КНОПКИ ==========
@bot.callback_query_handler(func=lambda call: call.data == 'edit_btns')
def edit_btns(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=1)
    for key, text in data['settings']['buttons'].items():
        markup.add(InlineKeyboardButton(f"✏️ {text}", callback_data=f"edit_btn_{key}", style="primary"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary"))
    bot.edit_message_text("🛠 Выберите кнопку для редактирования:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_btn_'))
def edit_btn(call):
    if not is_admin(call.from_user.id):
        return
    key = call.data.split('_')[2]
    bot.answer_callback_query(call.id, "✏️ Введите новый текст")
    msg = bot.send_message(call.message.chat.id, f"Текущий текст: {data['settings']['buttons'][key]}\nВведите новый:")
    bot.register_next_step_handler(msg, lambda m: set_btn_text(m, key, call.message.chat.id, call.message.message_id))

def set_btn_text(msg, key, chat_id, message_id):
    data['settings']['buttons'][key] = msg.text
    save_data()
    bot.edit_message_text(f"✅ Обновлено: {msg.text}", chat_id, message_id)
    time.sleep(0.5)
    edit_btns_after(msg)

def edit_btns_after(msg):
    # Показываем меню редактирования кнопок заново
    markup = InlineKeyboardMarkup(row_width=1)
    for key, text in data['settings']['buttons'].items():
        markup.add(InlineKeyboardButton(f"✏️ {text}", callback_data=f"edit_btn_{key}", style="primary"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary"))
    bot.send_message(msg.chat.id, "🛠 Выберите кнопку для редактирования:", reply_markup=markup)

# ========== РЕДАКТИРОВАТЬ ПРИВЕТСТВИЕ ==========
@bot.callback_query_handler(func=lambda call: call.data == 'edit_welcome')
def edit_welcome(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"Текущее приветствие:\n{data['settings']['welcome']}\n\nВведите новое:")
    bot.register_next_step_handler(msg, lambda m: set_welcome(m, call.message.chat.id, call.message.message_id))

def set_welcome(msg, chat_id, message_id):
    data['settings']['welcome'] = msg.text
    save_data()
    bot.edit_message_text("✅ Приветствие обновлено!", chat_id, message_id)

# ========== РЕДАКТИРОВАТЬ ТЕКСТЫ ==========
@bot.callback_query_handler(func=lambda call: call.data == 'edit_texts')
def edit_texts(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=1)
    for key in data['settings']['texts']:
        markup.add(InlineKeyboardButton(f"📝 {key}", callback_data=f"edit_text_{key}", style="primary"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary"))
    bot.edit_message_text("🛠 Выберите текст для редактирования:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_text_'))
def edit_text(call):
    if not is_admin(call.from_user.id):
        return
    key = call.data.split('_')[2]
    bot.answer_callback_query(call.id, "✏️ Введите новый текст")
    msg = bot.send_message(call.message.chat.id, f"Текущий текст:\n{data['settings']['texts'][key]}\n\nВведите новый:")
    bot.register_next_step_handler(msg, lambda m: set_text(m, key, call.message.chat.id, call.message.message_id))

def set_text(msg, key, chat_id, message_id):
    data['settings']['texts'][key] = msg.text
    save_data()
    bot.edit_message_text("✅ Текст обновлён!", chat_id, message_id)
    time.sleep(0.5)
    edit_texts_after(msg)

def edit_texts_after(msg):
    markup = InlineKeyboardMarkup(row_width=1)
    for key in data['settings']['texts']:
        markup.add(InlineKeyboardButton(f"📝 {key}", callback_data=f"edit_text_{key}", style="primary"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary"))
    bot.send_message(msg.chat.id, "🛠 Выберите текст:", reply_markup=markup)

# ========== РАССЫЛКА ==========
@bot.callback_query_handler(func=lambda call: call.data == 'broadcast')
def broadcast(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
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

# ========== АДМИНЫ (ТОЛЬКО ГЛАВНЫЙ) ==========
@bot.callback_query_handler(func=lambda call: call.data == 'manage_admins')
def manage_admins(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    text = "👑 Управление админами\n\nГлавный: " + str(ADMIN_ID) + "\nДополнительные:\n"
    admins = data.get('admins', [])
    if admins:
        for a in admins:
            info = data['stats']['user_details'].get(a, {})
            text += f"🆔 {a} – {info.get('first_name', '?')}\n"
    else:
        text += "Нет"
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("➕ Добавить", callback_data='add_admin', style="success"),
        InlineKeyboardButton("🗑 Удалить", callback_data='remove_admin', style="danger"),
        InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'add_admin')
def add_admin(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id, "🆔 Введите ID")
    msg = bot.send_message(call.message.chat.id, "🆔 Введите ID нового админа:")
    bot.register_next_step_handler(msg, lambda m: add_admin_id(m, call.message.chat.id, call.message.message_id))

def add_admin_id(msg, chat_id, message_id):
    try:
        new_id = str(msg.text).strip()
        if new_id == str(ADMIN_ID):
            bot.send_message(msg.chat.id, "❌ Это главный админ")
            return
        if 'admins' not in data:
            data['admins'] = []
        if new_id not in data['admins']:
            data['admins'].append(new_id)
            save_data()
            bot.edit_message_text(f"✅ Админ {new_id} добавлен", chat_id, message_id)
        else:
            bot.send_message(msg.chat.id, "❌ Уже есть")
    except:
        bot.send_message(msg.chat.id, "❌ Ошибка")
    time.sleep(0.5)
    manage_admins_after(msg)

def manage_admins_after(msg):
    # Показываем меню управления админами заново
    text = "👑 Управление админами\n\nГлавный: " + str(ADMIN_ID) + "\nДополнительные:\n"
    admins = data.get('admins', [])
    if admins:
        for a in admins:
            info = data['stats']['user_details'].get(a, {})
            text += f"🆔 {a} – {info.get('first_name', '?')}\n"
    else:
        text += "Нет"
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("➕ Добавить", callback_data='add_admin', style="success"),
        InlineKeyboardButton("🗑 Удалить", callback_data='remove_admin', style="danger"),
        InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary")
    )
    bot.send_message(msg.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'remove_admin')
def remove_admin(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    admins = data.get('admins', [])
    if not admins:
        bot.send_message(call.message.chat.id, "❌ Нет дополнительных админов")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for a in admins:
        info = data['stats']['user_details'].get(a, {})
        markup.add(InlineKeyboardButton(f"❌ {a} – {info.get('first_name', '?')}", callback_data=f"rem_admin_{a}", style="danger"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data='manage_admins', style="primary"))
    bot.edit_message_text("🗑 Выберите админа для удаления:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('rem_admin_'))
def rem_admin(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    admin_id = call.data.split('_')[2]
    if admin_id in data.get('admins', []):
        data['admins'].remove(admin_id)
        save_data()
        bot.answer_callback_query(call.id, "✅ Удалён")
    manage_admins_after(call)

# ========== ЮРИДИЧЕСКИЕ (ТОЛЬКО ГЛАВНЫЙ) ==========
@bot.callback_query_handler(func=lambda call: call.data == 'legal')
def legal(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    legal = data['settings']['legal']
    text = f"⚖️ Юр. документы\n\nТекст согласия:\n{legal['agreement_text'][:100]}...\nПолитика: {legal['privacy_link']}\nОферта: {legal['offer_link']}\nКнопка: {legal['accept_button']}\nСтатус: {'ВКЛ' if legal['show_legal'] else 'ВЫКЛ'}"
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📝 Текст согласия", callback_data='legal_text', style="primary"),
        InlineKeyboardButton("🔗 Политика", callback_data='legal_privacy', style="primary"),
        InlineKeyboardButton("🔗 Оферта", callback_data='legal_offer', style="primary"),
        InlineKeyboardButton("📌 Кнопка", callback_data='legal_button', style="primary"),
        InlineKeyboardButton("🔄 Вкл/Выкл", callback_data='legal_toggle', style="danger"),
        InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'legal_text')
def legal_text(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id, "✏️ Введите текст")
    msg = bot.send_message(call.message.chat.id, f"Текущий текст:\n{data['settings']['legal']['agreement_text']}\n\nВведите новый (можно HTML):")
    bot.register_next_step_handler(msg, lambda m: set_legal_text(m, call.message.chat.id, call.message.message_id))

def set_legal_text(msg, chat_id, message_id):
    data['settings']['legal']['agreement_text'] = msg.text
    save_data()
    bot.edit_message_text("✅ Обновлено!", chat_id, message_id)
    legal_after(msg)

@bot.callback_query_handler(func=lambda call: call.data == 'legal_privacy')
def legal_privacy(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id, "🔗 Введите ссылку")
    msg = bot.send_message(call.message.chat.id, f"Текущая ссылка:\n{data['settings']['legal']['privacy_link']}\n\nВведите новую:")
    bot.register_next_step_handler(msg, lambda m: set_legal_privacy(m, call.message.chat.id, call.message.message_id))

def set_legal_privacy(msg, chat_id, message_id):
    data['settings']['legal']['privacy_link'] = msg.text
    save_data()
    bot.edit_message_text("✅ Обновлено!", chat_id, message_id)
    legal_after(msg)

@bot.callback_query_handler(func=lambda call: call.data == 'legal_offer')
def legal_offer(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id, "🔗 Введите ссылку")
    msg = bot.send_message(call.message.chat.id, f"Текущая ссылка:\n{data['settings']['legal']['offer_link']}\n\nВведите новую:")
    bot.register_next_step_handler(msg, lambda m: set_legal_offer(m, call.message.chat.id, call.message.message_id))

def set_legal_offer(msg, chat_id, message_id):
    data['settings']['legal']['offer_link'] = msg.text
    save_data()
    bot.edit_message_text("✅ Обновлено!", chat_id, message_id)
    legal_after(msg)

@bot.callback_query_handler(func=lambda call: call.data == 'legal_button')
def legal_button(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id, "📌 Введите текст")
    msg = bot.send_message(call.message.chat.id, f"Текущий текст кнопки:\n{data['settings']['legal']['accept_button']}\n\nВведите новый:")
    bot.register_next_step_handler(msg, lambda m: set_legal_button(m, call.message.chat.id, call.message.message_id))

def set_legal_button(msg, chat_id, message_id):
    data['settings']['legal']['accept_button'] = msg.text
    save_data()
    bot.edit_message_text("✅ Обновлено!", chat_id, message_id)
    legal_after(msg)

@bot.callback_query_handler(func=lambda call: call.data == 'legal_toggle')
def legal_toggle(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    bot.answer_callback_query(call.id)
    data['settings']['legal']['show_legal'] = not data['settings']['legal'].get('show_legal', True)
    save_data()
    legal_after(call)

def legal_after(msg):
    # Показываем меню юр. документов заново
    legal = data['settings']['legal']
    text = f"⚖️ Юр. документы\n\nТекст согласия:\n{legal['agreement_text'][:100]}...\nПолитика: {legal['privacy_link']}\nОферта: {legal['offer_link']}\nКнопка: {legal['accept_button']}\nСтатус: {'ВКЛ' if legal['show_legal'] else 'ВЫКЛ'}"
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📝 Текст согласия", callback_data='legal_text', style="primary"),
        InlineKeyboardButton("🔗 Политика", callback_data='legal_privacy', style="primary"),
        InlineKeyboardButton("🔗 Оферта", callback_data='legal_offer', style="primary"),
        InlineKeyboardButton("📌 Кнопка", callback_data='legal_button', style="primary"),
        InlineKeyboardButton("🔄 Вкл/Выкл", callback_data='legal_toggle', style="danger"),
        InlineKeyboardButton("🔙 Назад", callback_data='admin_panel', style="primary")
    )
    bot.send_message(msg.chat.id if hasattr(msg, 'chat') else msg.message.chat.id, text, reply_markup=markup)

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    print("✅ SIALENS Физ бот запущен")
    print(f"👤 Главный админ: {ADMIN_ID}")
    print(f"👥 Доп. админы: {data.get('admins', [])}")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"Ошибка: {e}")
        time.sleep(5)