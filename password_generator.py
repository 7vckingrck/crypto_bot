import os
import time
import logging
import string
import secrets
from typing import List

RATE_LIMIT_MAX = 15
RATE_LIMIT_WINDOW = 60
_user_requests = {}  # user_id -> timestamps

DEFAULTS = {
    "simple": {"default": 8, "min": 4, "max": 32},
    "medium": {"default": 12, "min": 6, "max": 64},
    "strong": {"default": 20, "min": 8, "max": 128},
}

def check_rate_limit(user_id: int) -> bool:
    """Простая защита от спама."""
    now = time.time()
    ts_list = _user_requests.get(user_id, [])
    ts_list = [t for t in ts_list if now - t < RATE_LIMIT_WINDOW]
    if len(ts_list) >= RATE_LIMIT_MAX:
        _user_requests[user_id] = ts_list
        return False
    ts_list.append(now)
    _user_requests[user_id] = ts_list
    return True


def make_charset(level: str, exclude_ambiguous: bool = True) -> str:
    """Возвращает набор символов для выбранного уровня сложности."""
    AMBIG = {'l', 'I', '1', 'O', '0'}
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    punct = ''.join(ch for ch in string.punctuation if ch not in {'"', "'", '\\\\', '`'})

    if exclude_ambiguous:
        lower = ''.join(c for c in lower if c not in AMBIG)
        upper = ''.join(c for c in upper if c not in AMBIG)
        digits = ''.join(c for c in digits if c not in AMBIG)

    if level == "simple":
        return lower + digits
    elif level == "medium":
        return lower + upper + digits
    elif level == "strong":
        return lower + upper + digits + punct
    else:
        raise ValueError("Неизвестный уровень сложности")


def generate_password(level: str, length: int) -> str:
    """Генерация безопасного пароля."""
    charset = make_charset(level)
    return ''.join(secrets.choice(charset) for _ in range(length))


def generate_multiple_passwords(level: str, length: int, count: int = 3) -> List[str]:
    """Генерация нескольких паролей."""
    return [generate_password(level, length) for _ in range(count)]