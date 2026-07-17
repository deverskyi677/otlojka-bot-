import os

TOKEN = os.environ.get('TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID', '')  # УБРАТЬ int() — это строка!