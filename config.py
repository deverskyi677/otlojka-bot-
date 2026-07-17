import os

# Пытаемся взять из окружения, если нет — используем запасные
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID', '')

# Если переменные не заданы — используем тестовые (ЗАМЕНИ НА СВОИ!)
if not TOKEN:
    TOKEN = "8647853429:AAEBBxBvvGA-CyTsnrIxuWbW-BNYAgNQ6RI"  # ВСТАВЬ СВОЙ ТОКЕН СЮДА
    print("⚠️ ВНИМАНИЕ: Используется токен из config.py (не из окружения)")

if not ADMIN_ID:
    ADMIN_ID = "8830973658"  # ВСТАВЬ СВОЙ ID СЮДА
    print("⚠️ ВНИМАНИЕ: Используется ADMIN_ID из config.py (не из окружения)")

print(f"✅ TOKEN загружен: {TOKEN[:10]}...")
print(f"✅ ADMIN_ID: {ADMIN_ID}")