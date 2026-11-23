import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_store.db")

# Referral bonus in bonus balance (rubles, informational)
DEFAULT_REFERRAL_BONUS = int(os.getenv("DEFAULT_REFERRAL_BONUS", "100"))

# Enable/disable referral system
REFERRAL_ENABLED = os.getenv("REFERRAL_ENABLED", "true").lower() == "true"

# Currency for Stars
STARS_CURRENCY = "XTR"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "bot_store.log")

# Media paths
MEDIA_DIR = os.path.join(os.path.dirname(__file__), "media")
os.makedirs(MEDIA_DIR, exist_ok=True)
