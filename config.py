import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_RAW = os.getenv("OWNER_ID", "").strip()
REMANGA_COOKIES = os.getenv("REMANGA_COOKIES", "").strip()

if not BOT_TOKEN:
    raise ValueError("Не указан BOT_TOKEN в .env")

OWNER_ID = int(OWNER_ID_RAW) if OWNER_ID_RAW else None

if not REMANGA_COOKIES:
    raise ValueError("Не указан REMANGA_COOKIES в .env")
