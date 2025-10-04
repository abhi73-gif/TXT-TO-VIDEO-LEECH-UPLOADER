from os import environ

def safe_int(value, default):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

API_ID = safe_int(environ.get("API_ID"), 20937420)
API_HASH = environ.get("API_HASH", "09d7f6744feb17759304df65666961da")
BOT_TOKEN = environ.get("BOT_TOKEN", "")  # Isse Render ya .env file se zarur set karein

# Force subscribe config HATA DIYA

# Admin Configuration
admin_env = environ.get("ADMINS", "7881009185")
try:
    ADMINS = list(map(int, admin_env.split())) if admin_env else []
except ValueError:
    ADMINS = [7881009185]

OWNER_ID = safe_int(environ.get("OWNER_ID"), 7881009185)

DATABASE_URL = environ.get(
    "DATABASE_URL",
    "mongodb+srv://abhi736902:Abhishek2007@cluster0.3lujetq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)
