

from os import environ

API_ID = int(environ.get("API_ID", "20937420"))
API_HASH = environ.get("API_HASH", "09d7f6744feb17759304df65666961da")
BOT_TOKEN = environ.get("BOT_TOKEN", "")

# Force Subscribe Configuration
FORCE_SUB_CHANNEL = environ.get("FORCE_SUB_CHANNEL", "updatechannal123")  # Channel username without @, 
FORCE_SUB_CHANNEL_LINK = environ.get("FORCE_SUB_CHANNEL_LINK", "https://t.me/updatechannal123")  # Channel link

# Admin Configuration
ADMINS = list(map(int, environ.get("ADMINS", "7881009185").split()))

# Optional: Bot Owner ID
OWNER_ID = int(environ.get("OWNER_ID", "7881009185"))

# Database URL (if you want to add database support later)
DATABASE_URL = environ.get("DATABASE_URL", "")





