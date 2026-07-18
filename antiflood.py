# ============================================================
# antiflood.py — защита от спама командами / DDoS-подобной нагрузки
# ============================================================
# Работает по скользящему окну: если пользователь совершает больше
# MAX_ACTIONS действий (сообщений или нажатий на кнопки) за WINDOW_SECONDS —
# он временно блокируется. При повторных нарушениях подряд время блокировки
# растёт (эскалация), чтобы не давать боту захлёбываться постоянными
# короткими сериями запросов.
#
# Это не защищает от объёмной сетевой DDoS-атаки на сервер (это уровень
# инфраструктуры/хостинга), но полностью защищает от спама командами и
# кнопками внутри Telegram — то есть от единственного реального вектора,
# который вообще доступен атакующему через сам бот.

import time
from collections import defaultdict, deque

WINDOW_SECONDS = 5          # окно наблюдения
MAX_ACTIONS = 8             # макс. действий за окно — дальше блок
BLOCK_SECONDS = 30          # первая блокировка
ESCALATION_WINDOW = 600     # 10 минут — за это время считаем повторные нарушения
ESCALATION_BLOCK = 600      # 10 минут — блок при 3+ нарушении подряд
ESCALATION_THRESHOLD = 3
WARN_COOLDOWN = 5           # не чаще одного предупреждения в N секунд на юзера

_action_log = defaultdict(deque)
_blocked_until = {}
_flood_count = defaultdict(int)
_flood_count_reset = {}
_last_warned = {}


def is_flooding(user_id):
    """True — если пользователь сейчас должен быть заблокирован (флудит)."""
    now = time.time()
    uid = str(user_id)

    if uid in _blocked_until:
        if now < _blocked_until[uid]:
            return True
        del _blocked_until[uid]

    dq = _action_log[uid]
    dq.append(now)
    while dq and now - dq[0] > WINDOW_SECONDS:
        dq.popleft()

    if len(dq) > MAX_ACTIONS:
        if uid in _flood_count_reset and now > _flood_count_reset[uid]:
            _flood_count[uid] = 0
        _flood_count[uid] += 1
        _flood_count_reset[uid] = now + ESCALATION_WINDOW

        block_duration = ESCALATION_BLOCK if _flood_count[uid] >= ESCALATION_THRESHOLD else BLOCK_SECONDS
        _blocked_until[uid] = now + block_duration
        dq.clear()
        return True

    return False


def should_warn(user_id):
    """Не даёт слать предупреждение о бане на каждое последующее сообщение флудера."""
    now = time.time()
    uid = str(user_id)
    if now - _last_warned.get(uid, 0) > WARN_COOLDOWN:
        _last_warned[uid] = now
        return True
    return False


def remaining_block_seconds(user_id):
    uid = str(user_id)
    return max(0, int(_blocked_until.get(uid, 0) - time.time()))
