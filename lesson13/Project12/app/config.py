from pathlib import Path
import os

# Путь к файлу с переменными окружения
_env_file = Path(__file__).parent.parent / "local.env"

# Читаем переменные из local.env файла
_env_vars = {}
if _env_file.exists():
    with open(_env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Пропускаем пустые строки и комментарии
            if not line or line.startswith('#'):
                continue
            # Парсим KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip("'\"")  # Убираем кавычки если есть
                _env_vars[key] = value

# Функция для получения переменной (сначала из файла, потом из системных переменных)
def _get_env(key: str, default: str = "") -> str:
    return _env_vars.get(key, os.getenv(key, default))

API_TOKEN = _get_env("API_TOKEN", "")
DATABASE_URL = _get_env("DATABASE_URL", "sqlite:///./db/quiz_bot.db")
LOG_LEVEL = _get_env("LOG_LEVEL", "INFO")