

from os import environ

API_ID = int(environ.get("20937420", "write yours"))
API_HASH = environ.get("09d7f6744feb17759304df65666961da", "write yours")
BOT_TOKEN = environ.get("BOT_TOKEN", "write yours")

# Force Subscribe Configuration
FORCE_SUB_CHANNEL = environ.get("FORCE_SUB_CHANNEL", "abbhffi8uy")  # Channel username without @, 
FORCE_SUB_CHANNEL_LINK = environ.get("FORCE_SUB_CHANNEL_LINK", "https://t.me/abbhffi8uy")  # Channel link

# Admin Configuration
ADMINS = list(map(int, environ.get("ADMINS", "7881009185").split()))

# Optional: Bot Owner ID
OWNER_ID = int(environ.get("OWNER_ID", "7881009185"))

# Database URL (if you want to add database support later)
DATABASE_URL = environ.get("mongodb+srv://abhi736902:Abhishek2007@cluster0.3lujetq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", "")


