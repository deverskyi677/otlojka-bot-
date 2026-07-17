import telebot
import json
import os
import time
import re
import logging
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, ADMIN_ID

print(f"🔍 TOKEN: {TOKEN[:10] if TOKEN else 'НЕ ЗАГРУЖЕН'}...")
print(f"🔍 ADMIN_ID: {ADMIN_ID if ADMIN_ID else 'НЕ ЗАГРУЖЕН'}")

if not TOKEN:
    print("❌ ТОКЕН НЕ ЗАГРУЖЕН! Бот не запустится.")
    exit()

# ============================================================
# 1. НАСТРОЙКА
# ============================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = str(ADMIN_ID)

DATA_FILE = 'data.json'
BACKUP_FILE = 'data_backup.json'

# ============================================================
# 2. РАБОТА С ДАННЫМИ
# ============================================================
def load_data():
    if not os.path.exists(DATA_FILE):
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
                "welcome_text": "Добро пожаловать в SIALENS Физ!",
                "legal_text": "📜 <b>Покупая номер, вы соглашаетесь с условиями:</b>\n\n• <a href='https://telegra.ph/Politika-konfidencialnosti-07-17-132'>Политика конфиденциальности</a>\n• <a href='https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17'>Публичная оферта</a>",
                "accept_button_text": "✅ Я принимаю условия",
                "approve_text": "✅ ВАШ ПЛАТЕЖ ОДОБРЕН!\n\n📱 Ваш номер: {phone}\n\n🔐 ИНСТРУКЦИЯ:\n1️⃣ Введите номер в Telegram\n2️⃣ Вернитесь в чат с ботом\n3️⃣ Нажмите кнопку «Я вернулся, жду код»\n4️⃣ Я пришлю вам код подтверждения",
                "reject_text": "❌ Ваш платеж отклонён.\n\nПричина: {reason}"
            }
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, indent=2, ensure_ascii=False)
        logger.info("✅ Создан новый файл данных")
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                current = f.read()
            with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
                f.write(current)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("✅ Данные сохранены")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения: {e}")

data = load_data()

def is_admin(user_id):
    user_id = str(user_id)
    return user_id == ADMIN_ID or user_id in data.get('admins', [])

# ============================================================
# 3. /START
# ============================================================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or "нет_юзернейма"
    first_name = message.from_user.first_name or "Без_имени"

    if user_id not in data['users']:
        data['users'].append(user_id)
        data['stats']['visits'] = data['stats'].get('visits', 0) + 1
        save_data(data)
        logger.info(f"🆕 Новый пользователь: {user_id} - {first_name} (@{username})")

    if user_id not in data.get('accepted_users', []):
        show_legal_agreement(message)
        return

    show_main_menu(message)

def show_legal_agreement(message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📋 Политика конфиденциальности", url="https://telegra.ph/Politika-konfidencialnosti-07-17-132"),
        InlineKeyboardButton("📄 Публичная оферта", url="https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17")
    )
    markup.add(InlineKeyboardButton(data['settings'].get('accept_button_text', '✅ Я принимаю условия'), callback_data="accept_rules"))

    bot.send_message(
        message.chat.id,
        data['settings'].get('legal_text', '📜 Пожалуйста, ознакомьтесь с условиями и примите их.'),
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.callback_query_handler(func=lambda call: call.data == "accept_rules")
def accept_rules(call):
    user_id = str(call.from_user.id)
    if user_id not in data.get('accepted_users', []):
        data['accepted_users'].append(user_id)
        save_data(data)
    bot.answer_callback_query(call.id, "✅ Условия приняты!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    show_main_menu(call.message)

def show_main_menu(message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📱 Купить номер", callback_data="buy_menu"),
        InlineKeyboardButton("📞 Связь с поддержкой", url="https://t.me/deverskyi")
    )
    if is_admin(message.from_user.id):
        markup.add(InlineKeyboardButton("🛠 Админ панель", callback_data="admin_panel"))

    bot.send_message(
        message.chat.id,
        data['settings'].get('welcome_text', 'Добро пожаловать!'),
        reply_markup=markup
    )

# ============================================================
# 4. ПОКУПКА
# ============================================================
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
        "🌍 Выберите страну для покупки номера:",
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
        f"💳 Оплатите {item['price']}₽ на номер:\n<b>+79103552521</b>\n\n📸 После оплаты пришлите СКРИНШОТ.",
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

    bot.send_message(msg.chat.id, "✅ Скрин отправлен на проверку. Ожидайте.")

    order_idx = len(data['orders']) - 1
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Принять", callback_data=f"accept_{order_idx}", style="success"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{order_idx}", style="danger")
    )
    markup.add(InlineKeyboardButton("✏️ Написать", callback_data=f"reply_{order_idx}", style="primary"))

    admin_ids = [ADMIN_ID] + data.get('admins', [])
    for admin_id in admin_ids:
        try:
            bot.send_photo(
                admin_id,
                order['screenshot'],
                f"🆕 НОВЫЙ ЗАКАЗ #{order['id']}\n\n"
                f"👤 {order['first_name']} (@{order['username']})\n"
                f"🌍 {order['country']}\n"
                f"💰 {order['price']}₽",
                reply_markup=markup
            )
            logger.info(f"📨 Заказ #{order['id']} отправлен админу {admin_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    show_main_menu(call.message)

# ============================================================
# 5. АДМИН ПАНЕЛЬ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Доступ запрещён")
        return

    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats", style="primary"),
        InlineKeyboardButton("📋 Заказы", callback_data="admin_orders", style="primary"),
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_users", style="primary"),
        InlineKeyboardButton("➕ Добавить номер", callback_data="admin_add_number", style="success"),
        InlineKeyboardButton("🗑 Удалить номер", callback_data="admin_delete_number", style="danger"),
        InlineKeyboardButton("✏️ Текст приветствия", callback_data="admin_edit_welcome", style="primary"),
        InlineKeyboardButton("📝 Тексты бота", callback_data="admin_edit_texts", style="primary"),
        InlineKeyboardButton("💬 Рассылка", callback_data="admin_broadcast", style="primary")
    )

    if str(call.from_user.id) == ADMIN_ID:
        markup.add(
            InlineKeyboardButton("👑 Управление админами", callback_data="admin_manage_admins", style="danger"),
            InlineKeyboardButton("⚖️ Юридические документы", callback_data="admin_legal", style="primary")
        )

    markup.add(InlineKeyboardButton("🔙 Выход", callback_data="back_to_menu", style="danger"))

    bot.edit_message_text(
        "🛠 АДМИН ПАНЕЛЬ\n\nЗдесь вы можете управлять ботом: просматривать статистику, обрабатывать заказы, редактировать содержимое.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# ============================================================
# 6. СТАТИСТИКА
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def admin_stats(call):
    if not is_admin(call.from_user.id):
        return

    bot.answer_callback_query(call.id)
    text = f"📊 СТАТИСТИКА БОТА\n\n"
    text += f"👤 Пользователей: {len(data.get('users', []))}\n"
    text += f"✅ Приняли правила: {len(data.get('accepted_users', []))}\n"
    text += f"👀 Визитов: {data['stats'].get('visits', 0)}\n"
    text += f"📦 Заказов: {len(data.get('orders', []))}\n"
    text += f"⏳ Ожидают: {len([o for o in data.get('orders', []) if o['status'] == 'waiting_approval'])}\n"
    text += f"✅ Одобрено: {len([o for o in data.get('orders', []) if o['status'] == 'approved'])}\n"
    text += f"❌ Отклонено: {len([o for o in data.get('orders', []) if o['status'] == 'rejected'])}"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# 7. ЗАКАЗЫ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_orders")
def admin_orders(call):
    if not is_admin(call.from_user.id):
        return

    bot.answer_callback_query(call.id)
    if not data.get('orders'):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary"))
        bot.edit_message_text("📭 Нет заказов", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for order in data['orders'][-10:]:
        idx = data['orders'].index(order)
        status_emoji = "⏳" if order['status'] == 'waiting_approval' else "✅" if order['status'] == 'approved' else "❌"
        markup.add(InlineKeyboardButton(
            f"#{order['id']} | {order['country']} | {order['price']}₽ {status_emoji}",
            callback_data=f"order_detail_{idx}",
            style="primary"
        ))

    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary"))

    bot.edit_message_text(
        "📋 ПОСЛЕДНИЕ ЗАКАЗЫ (10):\n\n⏳ - ожидает | ✅ - одобрен | ❌ - отклонён",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

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

    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_orders", style="primary"))

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
# 8. ПРИНЯТЬ ЗАКАЗ
# ============================================================
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
    phone = msg.text.strip()
    if not phone:
        bot.send_message(msg.chat.id, "❌ Номер не может быть пустым")
        return

    order = data['orders'][idx]
    order['phone'] = phone
    order['status'] = 'approved'
    data['stats']['orders_approved'] = data['stats'].get('orders_approved', 0) + 1
    save_data(data)

    bot.edit_message_text(
        f"✅ Заказ #{order['id']} принят.\n📱 Номер {phone} выдан.",
        chat_id,
        message_id
    )

    user_id = order['user_id']
    try:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔄 Я вернулся, жду код", callback_data=f"wait_code_{idx}", style="primary"))

        approve_text = data['settings'].get('approve_text', '').format(phone=phone)

        bot.send_message(user_id, approve_text, reply_markup=markup)
        bot.send_message(msg.chat.id, f"✅ Пользователю отправлен номер: {phone}")
        logger.info(f"📨 Номер {phone} отправлен пользователю {user_id}")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка отправки пользователю: {e}")
        logger.error(f"❌ Ошибка отправки пользователю {user_id}: {e}")

# ============================================================
# 9. ОТКЛОНИТЬ ЗАКАЗ
# ============================================================
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
    reason = msg.text.strip()
    order = data['orders'][idx]
    order['status'] = 'rejected'
    data['stats']['orders_rejected'] = data['stats'].get('orders_rejected', 0) + 1
    save_data(data)

    bot.edit_message_text(
        f"❌ Заказ #{order['id']} отклонён.\nПричина: {reason}",
        chat_id,
        message_id
    )

    try:
        reject_text = data['settings'].get('reject_text', '').format(reason=reason)
        bot.send_message(order['user_id'], reject_text)
        logger.info(f"📨 Отказ отправлен пользователю {order['user_id']}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки отказа: {e}")

# ============================================================
# 10. НАПИСАТЬ
# ============================================================
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
        logger.info(f"📨 Сообщение отправлено пользователю {user_id}")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка: {e}")
        logger.error(f"❌ Ошибка отправки сообщения: {e}")

# ============================================================
# 11. ОТПРАВИТЬ КОД
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('send_code_'))
def send_code(call):
    if not is_admin(call.from_user.id):
        return

    bot.answer_callback_query(call.id)
    idx = int(call.data.split('_')[2])
    msg = bot.send_message(call.message.chat.id, "✏️ Введите код подтверждения:")
    bot.register_next_step_handler(msg, lambda m: send_code_to_user(m, idx))

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
# 12. ЖДУ КОД
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('wait_code_'))
def wait_code(call):
    bot.answer_callback_query(call.id, "🔄 Ожидайте код от администратора")
    idx = int(call.data.split('_')[2])

    order = data['orders'][idx]
    order['code_waiting'] = True
    save_data(data)

    bot.send_message(call.message.chat.id, "✅ Вы уведомлены. Администратор отправит код в этот чат.")

    admin_ids = [ADMIN_ID] + data.get('admins', [])
    for admin_id in admin_ids:
        try:
            bot.send_message(admin_id, f"🔄 Пользователь @{order['username']} ждёт код для заказа #{order['id']}")
        except:
            pass

# ============================================================
# 13. ДОБАВИТЬ НОМЕР
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_number")
def add_number(call):
    if not is_admin(call.from_user.id):
        return

    bot.answer_callback_query(call.id)
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
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats", style="primary"),
        InlineKeyboardButton("📋 Заказы", callback_data="admin_orders", style="primary"),
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_users", style="primary"),
        InlineKeyboardButton("➕ Добавить номер", callback_data="admin_add_number", style="success"),
        InlineKeyboardButton("🗑 Удалить номер", callback_data="admin_delete_number", style="danger"),
        InlineKeyboardButton("✏️ Текст приветствия", callback_data="admin_edit_welcome", style="primary"),
        InlineKeyboardButton("📝 Тексты бота", callback_data="admin_edit_texts", style="primary"),
        InlineKeyboardButton("💬 Рассылка", callback_data="admin_broadcast", style="primary")
    )
    if str(msg.from_user.id) == ADMIN_ID:
        markup.add(
            InlineKeyboardButton("👑 Управление админами", callback_data="admin_manage_admins", style="danger"),
            InlineKeyboardButton("⚖️ Юридические документы", callback_data="admin_legal", style="primary")
        )
    markup.add(InlineKeyboardButton("🔙 Выход", callback_data="back_to_menu", style="danger"))

    bot.send_message(msg.chat.id, "🛠 АДМИН ПАНЕЛЬ", reply_markup=markup)

# ============================================================
# 14. УДАЛИТЬ НОМЕР
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_number")
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
            f"❌ {item['country']} - {item['price']}₽",
            callback_data=f"delete_catalog_{idx}",
            style="danger"
        ))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary"))

    bot.edit_message_text(
        "🗑 ВЫБЕРИТЕ НОМЕР ДЛЯ УДАЛЕНИЯ:\n\n"
        f"📦 Всего номеров: {len(data['catalog'])}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_catalog_'))
def delete_catalog_item(call):
    if not is_admin(call.from_user.id):
        return

    idx = int(call.data.split('_')[2])
    item = data['catalog'].pop(idx)
    save_data(data)

    bot.answer_callback_query(call.id, f"✅ Удалено: {item['country']}")
    admin_panel_after(call)

# ============================================================
# 15. ТЕКСТ ПРИВЕТСТВИЯ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_welcome")
def edit_welcome(call):
    if not is_admin(call.from_user.id):
        return

    bot.answer_callback_query(call.id)
    current = data['settings'].get('welcome_text', '')
    msg = bot.send_message(
        call.message.chat.id,
        f"✏️ Введите НОВЫЙ ТЕКСТ ПРИВЕТСТВИЯ:\n\n"
        f"📌 Текущий текст:\n{current}\n\n"
        f"💡 Поддерживает HTML: <b>жирный</b>, <i>курсив</i>"
    )
    bot.register_next_step_handler(msg, lambda m: set_welcome(m, call.message.chat.id, call.message.message_id))

def set_welcome(msg, chat_id, message_id):
    data['settings']['welcome_text'] = msg.text
    save_data(data)

    bot.edit_message_text(
        f"✅ Текст приветствия обновлён!\n\n"
        f"📌 Новый текст:\n{msg.text[:200]}...",
        chat_id,
        message_id
    )

# ============================================================
# 16. ТЕКСТЫ БОТА
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_texts")
def admin_edit_texts(call):
    if not is_admin(call.from_user.id):
        return

    bot.answer_callback_query(call.id)

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📝 Текст одобрения", callback_data="edit_text_approve", style="primary"),
        InlineKeyboardButton("📝 Текст отказа", callback_data="edit_text_reject", style="primary"),
        InlineKeyboardButton("📝 Текст правил", callback_data="edit_text_legal", style="primary"),
        InlineKeyboardButton("📝 Текст кнопки правил", callback_data="edit_text_accept_btn", style="primary"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary")
    )

    bot.edit_message_text(
        "🛠 РЕДАКТИРОВАНИЕ ТЕКСТОВ БОТА\n\n"
        "Выберите, какой текст хотите изменить:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_text_'))
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
        f"💡 Используйте {{reason}} для подстановки причины (в тексте отказа)"
    )
    bot.register_next_step_handler(msg, lambda m: set_text_field(m, field, call.message.chat.id, call.message.message_id))

def set_text_field(msg, field, chat_id, message_id):
    data['settings'][field] = msg.text
    save_data(data)

    bot.edit_message_text(
        f"✅ Текст обновлён!\n\n"
        f"📌 Новый текст:\n{msg.text[:200]}...",
        chat_id,
        message_id
    )

# ============================================================
# 17. ПОЛЬЗОВАТЕЛИ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_users")
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
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ============================================================
# 18. РАССЫЛКА
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def broadcast(call):
    if not is_admin(call.from_user.id):
        return

    bot.answer_callback_query(call.id)

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

    bot.edit_message_text(
        f"✅ РАССЫЛКА ЗАВЕРШЕНА!\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}\n"
        f"👤 Всего: {total}",
        chat_id,
        message_id
    )

# ============================================================
# 19. УПРАВЛЕНИЕ АДМИНАМИ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_manage_admins")
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
        InlineKeyboardButton("➕ Добавить админа", callback_data="add_admin", style="success"),
        InlineKeyboardButton("🗑 Удалить админа", callback_data="remove_admin", style="danger"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary")
    )

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_admin")
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
            f"❌ {admin_id}",
            callback_data=f"remove_admin_{admin_id}",
            style="danger"
        ))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_manage_admins", style="primary"))

    bot.edit_message_text(
        "🗑 ВЫБЕРИТЕ АДМИНА ДЛЯ УДАЛЕНИЯ:\n\n"
        f"📋 Всего админов: {len(admins)}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_admin_'))
def remove_admin_id(call):
    if str(call.from_user.id) != ADMIN_ID:
        return

    admin_id = call.data.split('_')[2]

    if admin_id in data.get('admins', []):
        data['admins'].remove(admin_id)
        save_data(data)

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
        InlineKeyboardButton("➕ Добавить админа", callback_data="add_admin", style="success"),
        InlineKeyboardButton("🗑 Удалить админа", callback_data="remove_admin", style="danger"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary")
    )

    bot.send_message(msg.chat.id, text, reply_markup=markup)

# ============================================================
# 20. ЮРИДИЧЕСКИЕ ДОКУМЕНТЫ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_legal")
def admin_legal(call):
    if str(call.from_user.id) != ADMIN_ID:
        return

    bot.answer_callback_query(call.id)

    legal = data['settings']
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📝 Текст правил", callback_data="legal_edit_text", style="primary"),
        InlineKeyboardButton("📌 Текст кнопки", callback_data="legal_edit_btn", style="primary"),
        InlineKeyboardButton("🔗 Ссылка политики", callback_data="legal_edit_privacy", style="primary"),
        InlineKeyboardButton("🔗 Ссылка оферты", callback_data="legal_edit_offer", style="primary"),
        InlineKeyboardButton("🔄 Показать/Скрыть блок", callback_data="legal_toggle", style="danger"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary")
    )

    status = "🟢 Включен" if legal.get('show_legal', True) else "🔴 Выключен"

    bot.edit_message_text(
        f"⚖️ НАСТРОЙКА ЮРИДИЧЕСКОГО БЛОКА\n\n"
        f"📌 Статус: {status}\n"
        f"📝 Текст правил:\n{legal.get('legal_text', '')[:100]}...\n\n"
        f"📌 Кнопка: {legal.get('accept_button_text', '')}\n"
        f"🔗 Политика: {legal.get('privacy_url', 'https://telegra.ph/Politika-konfidencialnosti-07-17-132')}\n"
        f"🔗 Оферта: {legal.get('offer_url', 'https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17')}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('legal_edit_'))
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

    bot.edit_message_text(
        f"✅ Обновлено!\n\n"
        f"📌 Новое значение:\n{msg.text[:200]}...",
        chat_id,
        message_id
    )

@bot.callback_query_handler(func=lambda call: call.data == "legal_toggle")
def legal_toggle(call):
    if str(call.from_user.id) != ADMIN_ID:
        return

    bot.answer_callback_query(call.id)

    current = data['settings'].get('show_legal', True)
    data['settings']['show_legal'] = not current
    save_data(data)

    status = "🟢 ВКЛЮЧЕН" if data['settings']['show_legal'] else "🔴 ВЫКЛЮЧЕН"
    bot.send_message(call.message.chat.id, f"🔄 Юридический блок теперь {status}")

    time.sleep(0.5)
    admin_legal_after(call)

def admin_legal_after(call):
    legal = data['settings']
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📝 Текст правил", callback_data="legal_edit_text", style="primary"),
        InlineKeyboardButton("📌 Текст кнопки", callback_data="legal_edit_btn", style="primary"),
        InlineKeyboardButton("🔗 Ссылка политики", callback_data="legal_edit_privacy", style="primary"),
        InlineKeyboardButton("🔗 Ссылка оферты", callback_data="legal_edit_offer", style="primary"),
        InlineKeyboardButton("🔄 Показать/Скрыть блок", callback_data="legal_toggle", style="danger"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_panel", style="primary")
    )

    status = "🟢 Включен" if legal.get('show_legal', True) else "🔴 Выключен"

    bot.send_message(
        call.message.chat.id,
        f"⚖️ НАСТРОЙКА ЮРИДИЧЕСКОГО БЛОКА\n\n"
        f"📌 Статус: {status}\n"
        f"📝 Текст правил:\n{legal.get('legal_text', '')[:100]}...\n\n"
        f"📌 Кнопка: {legal.get('accept_button_text', '')}\n"
        f"🔗 Политика: {legal.get('privacy_url', 'https://telegra.ph/Politika-konfidencialnosti-07-17-132')}\n"
        f"🔗 Оферта: {legal.get('offer_url', 'https://telegra.ph/Publichnaya-oferta-na-priobreteniya-virtualnyh-nomerov-07-17')}",
        reply_markup=markup
    )

# ============================================================
# 21. ЗАПУСК
# ============================================================
if __name__ == '__main__':
    logger.info("="*50)
    logger.info("🚀 SIALENS Физ бот запускается...")
    logger.info(f"👤 Главный админ: {ADMIN_ID}")
    logger.info(f"👥 Доп. админы: {data.get('admins', [])}")
    logger.info(f"📦 В каталоге: {len(data.get('catalog', []))} номеров")
    logger.info(f"📋 Всего заказов: {len(data.get('orders', []))}")
    logger.info(f"👤 Всего пользователей: {len(data.get('users', []))}")
    logger.info("="*50)
    logger.info("✅ Бот готов к работе!")

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"❌ Ошибка в polling: {e}")
            time.sleep(10)
            logger.info("🔄 Перезапуск...")