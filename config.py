import os

def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding='utf-8') as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and not os.environ.get(key):
                os.environ[key] = value

_load_env()

class Config:
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    CHANNEL_ID = os.environ.get('CHANNEL_ID', '@ant_capital')
