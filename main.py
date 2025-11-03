# 🔧 Standard Library
import os
import re
import sys
import time
import json
import asyncio
import subprocess
from base64 import b64encode, b64decode
from subprocess import getstatusoutput

# 📦 Third-party Libraries
import aiohttp  # Replaced requests
import aiofiles
import cloudscraper
import yt_dlp
import tgcrypto
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# ⚙️ Pyrogram
from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from pyrogram.errors import (
    FloodWait,
    BadRequest,
    Unauthorized,
    SessionExpired,
    AuthKeyDuplicated,
    AuthKeyUnregistered,
    ChatAdminRequired,
    PeerIdInvalid,
    RPCError
)
from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified

# 🧠 Bot Modules
import auth
import ug as helper
from ug import * # Warning: Wildcard imports are generally discouraged

from clean import register_clean_handler
from logs import logging
from utils import progress_bar
from vars import * # Make sure API_ID, API_HASH, BOT_TOKEN, CREDIT are in here
from pyromod import listen
import apixug
from apixug import SecureAPIClient
from db import db

# Attempt to import sensitive/config variables
try:
    from vars import API_URL, API_TOKEN
except ImportError:
    print("CRITICAL ERROR: API_URL and API_TOKEN are not defined in vars.py!")
    print("Please add them to your configuration file (vars.py).")
    API_URL = "http://master-api-v3.vercel.app/"  # Fallback
    API_TOKEN = None  # Will cause failures, forcing user to fix config

auto_flags = {}
auto_clicked = False
client = SecureAPIClient()
apis = client.get_apis()

# Global variables
watermark = "UG"  # Default value
count = 0
userbot = None
timeout_duration = 300  # 5 minutes


# Initialize bot with random session
bot = Client(
    "ugx",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=300,
    sleep_threshold=60,
    in_memory=True
)

# Register command handlers
register_clean_handler(bot)


async def run_subprocess(cmd):
    """Helper to run shell commands asynchronously."""
    print(f"[SUBPROCESS] Running command: {cmd}")
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            print(f"Error executing command: {cmd}\nStderr: {stderr.decode('utf-8', 'ignore')}")
            return False, stderr.decode('utf-8', 'ignore')
        
        return True, stdout.decode('utf-8', 'ignore')
        
    except Exception as e:
        print(f"Exception running command: {e}")
        return False, str(e)

@bot.on_message(filters.command("setlog") & filters.private)
async def set_log_channel_cmd(client: Client, message: Message):
    """Set log channel for the bot"""
    try:
        # Check if user is admin
        if not db.is_admin(message.from_user.id):
            await message.reply_text("⚠️ You are not authorized to use this command.")
            return

        # Get command arguments
        args = message.text.split()
        if len(args) != 2:
            await message.reply_text(
                "❌ Invalid format!\n\n"
                "Use: /setlog channel_id\n"
                "Example: /setlog -100123456789"
            )
            return

        try:
            channel_id = int(args[1])
        except ValueError:
            await message.reply_text("❌ Invalid channel ID. Please use a valid number.")
            return

        # Set the log channel without validation
        if db.set_log_channel(client.me.username, channel_id):
            await message.reply_text(
                "✅ Log channel set successfully!\n\n"
                f"Channel ID: {channel_id}\n"
                f"Bot: @{client.me.username}"
            )
        else:
            await message.reply_text("❌ Failed to set log channel. Please try again.")

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@bot.on_message(filters.command("getlog") & filters.private)
async def get_log_channel_cmd(client: Client, message: Message):
    """Get current log channel info"""
    try:
        # Check if user is admin
        if not db.is_admin(message.from_user.id):
            await message.reply_text("⚠️ You are not authorized to use this command.")
            return

        # Get log channel ID
        channel_id = db.get_log_channel(client.me.username)
        
        if channel_id:
            # Try to get channel info but don't worry if it fails
            try:
                channel = await client.get_chat(channel_id)
                channel_info = f"📢 Channel Name: {channel.title}\n"
            except:
                channel_info = ""
            
            await message.reply_text(
                f"**📋 Log Channel Info**\n\n"
                f"🤖 Bot: @{client.me.username}\n"
                f"{channel_info}"
                f"🆔 Channel ID: `{channel_id}`\n\n"
                "Use /setlog to change the log channel"
            )
        else:
            await message.reply_text(
                f"**📋 Log Channel Info**\n\n"
                f"🤖 Bot: @{client.me.username}\n"
                "❌ No log channel set\n\n"
                "Use /setlog to set a log channel"
            )

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Re-register auth commands
bot.add_handler(MessageHandler(auth.add_user_cmd, filters.command("add") & filters.private))
bot.add_handler(MessageHandler(auth.remove_user_cmd, filters.command("remove") & filters.private))
bot.add_handler(MessageHandler(auth.list_users_cmd, filters.command("users") & filters.private))
bot.add_handler(MessageHandler(auth.my_plan_cmd, filters.command("plan") & filters.private))

cookies_file_path = os.getenv("cookies_file_path", "youtube_cookies.txt")
# api_url and api_token are now imported from vars.py

photologo = 'https://cdn.pixabay.com/photo/2025/05/21/02/38/ai-generated-9612673_1280.jpg' #https://envs.sh/GV0.jpg
photoyt = 'https://tinypic.host/images/2025/03/18/YouTube-Logo.wine.png' #https://envs.sh/GVi.jpg
photocp = 'https://tinypic.host/images/2025/03/28/IMG_20250328_133126.jpg'
photozip = 'https://envs.sh/cD_.jpg'


# Inline keyboard for start command
BUTTONSCONTACT = InlineKeyboardMarkup([[InlineKeyboardButton(text="📞 Contact", url="https://t.me/ItsUGxBot")]])
keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(text="🛠️ Help", url="https://t.me/ItsUGBot")        ],
    ]
)

# Image URLs for the random image feature
image_urls = [
    "https://cdn.pixabay.com/photo/2025/05/21/02/38/ai-generated-9612673_1280.jpg",
    "https://cdn.pixabay.com/photo/2025/05/21/02/38/ai-generated-9612673_1280.jpg",
    "https://cdn.pixabay.com/photo/2025/05/21/02/38/ai-generated-9612673_1280.jpg",
    # Add more image URLs as needed
]

        
@bot.on_message(filters.command("cookies") & filters.private)
async def cookies_handler(client: Client, m: Message):
    await m.reply_text(
        "Please upload the cookies file (.txt format).",
        quote=True
    )

    try:
        # Wait for the user to send the cookies file
        input_message: Message = await client.listen(m.chat.id)

        # Validate the uploaded file
        if not input_message.document or not input_message.document.file_name.endswith(".txt"):
            await m.reply_text("Invalid file type. Please upload a .txt file.")
            return

        # Download the cookies file
        downloaded_path = await input_message.download()

        # Read the content of the uploaded file
        async with aiofiles.open(downloaded_path, "r") as uploaded_file:
            cookies_content = await uploaded_file.read()

        # Replace the content of the target cookies file
        async with aiofiles.open(cookies_file_path, "w") as target_file:
            await target_file.write(cookies_content)

        await input_message.reply_text(
            "✅ Cookies updated successfully.\n📂 Saved in `youtube_cookies.txt`."
        )
        
        os.remove(downloaded_path)

    except Exception as e:
        await m.reply_text(f"⚠️ An error occurred: {str(e)}")

@bot.on_message(filters.command(["t2t"]))
async def text_to_txt(client, message: Message):
    user_id = str(message.from_user.id)
    # Inform the user to send the text data and its desired file name
    editable = await message.reply_text(f"<blockquote>Welcome to the Text to .txt Converter!\nSend the **text** for convert into a `.txt` file.</blockquote>")
    input_message: Message = await bot.listen(message.chat.id)
    if not input_message.text:
        await message.reply_text("**Send valid text data**")
        return

    text_data = input_message.text.strip()
    await input_message.delete()
    
    await editable.edit("**🔄 Send file name or send /d for filename**")
    inputn: Message = await bot.listen(message.chat.id)
    raw_textn = inputn.text
    await inputn.delete()
    await editable.delete()

    if raw_textn == '/d':
        custom_file_name = 'txt_file'
    else:
        custom_file_name = raw_textn

    txt_file = os.path.join("downloads", f'{custom_file_name}.txt')
    os.makedirs(os.path.dirname(txt_file), exist_ok=True)  # Ensure the directory exists
    
    async with aiofiles.open(txt_file, 'w', encoding='utf-8') as f:
        await f.write(text_data)
        
    await message.reply_document(document=txt_file, caption=f"`{custom_file_name}.txt`\n\n<blockquote>You can now download your content! 📥</blockquote>")
    os.remove(txt_file)


@bot.on_message(filters.command("getcookies") & filters.private)
async def getcookies_handler(client: Client, m: Message):
    try:
        # Send the cookies file to the user
        await client.send_document(
            chat_id=m.chat.id,
            document=cookies_file_path,
            caption="Here is the `youtube_cookies.txt` file."
        )
    except Exception as e:
        await m.reply_text(f"⚠️ An error occurred: {str(e)}")

@bot.on_message(filters.command(["stop"]) )
async def restart_handler(_, m):
    
    await m.reply_text("🚦**STOPPED**", True)
    os.execl(sys.executable, sys.executable, *sys.argv)
        

@bot.on_message(filters.command("start") & (filters.private | filters.channel))
async def start(bot: Client, m: Message):
    try:
        if m.chat.type == "channel":
            if not db.is_channel_authorized(m.chat.id, bot.me.username):
                return
                
            await m.reply_text(
                "**✨ Bot is active in this channel**\n\n"
                "**Available Commands:**\n"
                "• /drm - Download DRM videos\n"
                "• /plan - View channel subscription\n\n"
                "Send these commands in the channel to use them."
            )
        else:
            # Check user authorization
            is_authorized = db.is_user_authorized(m.from_user.id, bot.me.username)
            is_admin = db.is_admin(m.from_user.id)
            
            if not is_authorized:
                await m.reply_photo(
                    photo=photologo,
                    caption="**🔒 Access Required**\n\nContact admin to get access.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💫 Get Access", url="https://t.me/ItsUGBot")]
                    ])
                )
                return
                
            commands_list = (
                "**🤖 Available Commands**\n\n"
                "• /drm - Start Uploading...\n"
                "• /plan - View subscription\n"
            )
            
            if is_admin:
                commands_list += (
                    "\n**👑 Admin Commands**\n"
                    "• /users - List all users\n"
                )
            
            await m.reply_photo(
                photo=photologo,
                caption=f"**👋 Welcome {m.from_user.first_name}!**\n\n{commands_list}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📚 Help", url="https://t.me/ItsUGBot")]])
            )
            
    except Exception as e:
        print(f"Error in start command: {str(e)}")


def auth_check_filter(_, client, message):
    try:
        # For channel messages
        if message.chat.type == "channel":
            return db.is_channel_authorized(message.chat.id, client.me.username)
        # For private messages
        else:
            return db.is_user_authorized(message.from_user.id, client.me.username)
    except Exception:
        return False

auth_filter = filters.create(auth_check_filter)

@bot.on_message(~auth_filter & filters.private & filters.command)
async def unauthorized_handler(client, message: Message):
    await message.reply(
        "<b>🔒 Access Restricted</b>\n\n"
        "<blockquote>You need to have an active subscription to use this bot.\n"
        "Please contact admin to get premium access.</blockquote>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💫 Get Premium Access", url="https://t.me/ItsUGBot")
        ]])
    )

@bot.on_message(filters.command(["id"]))
async def id_command(client, message: Message):
    chat_id = message.chat.id
    await message.reply_text(
        f"<blockquote>The ID of this chat id is:</blockquote>\n`{chat_id}`"
    )

# --------------------------------------------------------------------------------
# REFACTORED URL PROCESSING LOGIC
# --------------------------------------------------------------------------------
async def process_url_logic(url: str, raw_text2: str, raw_text4: str, apis: dict):
    """
    Refactored function to handle all URL processing logic.
    Returns: (url, cmd, keys_string, appxkey)
    """
    cmd = None
    keys_string = None
    appxkey = None
    
    if "visionias" in url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:
                    text = await resp.text()
                    url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)
        except Exception as e:
            print(f"Visionias URL regex failed: {e}")

    if "acecwply" in url:
        cmd = f'yt-dlp -o "%(title)s.%(ext)s" -f "bestvideo[height<={raw_text2}]+bestaudio" --hls-prefer-ffmpeg --no-keep-video --remux-video mkv --no-warning "{url}"'

    elif "https://cpvideocdn.testbook.com/" in url or "https://cpvod.testbook.com/" in url:
        url = url.replace("https://cpvideocdn.testbook.com/","https://media-cdn.classplusapp.com/drm/")
        url = url.replace("https://cpvod.testbook.com/", "https://media-cdn.classplusapp.com/drm/")
        url = apis["API_DRM"] + url
        mpd, keys = helper.get_mps_and_keys(url)
        url = mpd
        keys_string = " ".join([f"--key {key}" for key in keys])
        
    elif "https://static-trans-v1.classx.co.in" in url or "https://static-trans-v2.classx.co.in" in url:
        base_with_params, signature = url.split("*")
        base_clean = base_with_params.split(".mkv")[0] + ".mkv"
        if "static-trans-v1.classx.co.in" in url:
            base_clean = base_clean.replace("https://static-trans-v1.classx.co.in", "https://appx-transcoded-videos-mcdn.akamai.net.in")
        elif "static-trans-v2.classx.co.in" in url:
            base_clean = base_clean.replace("https://static-trans-v2.classx.co.in", "https://transcoded-videos-v2.classx.co.in")
        url = f"{base_clean}*{signature}"
    
    elif "https://static-rec.classx.co.in/drm/" in url:
        base_with_params, signature = url.split("*")
        base_clean = base_with_params.split("?")[0]
        base_clean = base_clean.replace("https://static-rec.classx.co.in", "https://appx-recordings-mcdn.akamai.net.in")
        url = f"{base_clean}*{signature}"

    elif "https://static-wsb.classx.co.in/" in url:
        clean_url = url.split("?")[0]
        clean_url = clean_url.replace("https://static-wsb.classx.co.in", "https://appx-wsb-gcp-mcdn.akamai.net.in")
        url = clean_url

    elif "https://static-db.classx.co.in/" in url:
        if "*" in url:
            base_url, key = url.split("*", 1)
            base_url = base_url.split("?")[0]
            base_url = base_url.replace("https://static-db.classx.co.in", "https://appxcontent.kaxa.in")
            url = f"{base_url}*{key}"
        else:
            base_url = url.split("?")[0]
            url = base_url.replace("https://static-db.classx.co.in", "https://appxcontent.kaxa.in")

    elif "https://static-db-v2.classx.co.in/" in url:
        if "*" in url:
            base_url, key = url.split("*", 1)
            base_url = base_url.split("?")[0]
            base_url = base_url.replace("https://static-db-v2.classx.co.in", "https://appx-content-v2.classx.co.in")
            url = f"{base_url}*{key}"
        else:
            base_url = url.split("?")[0]
            url = base_url.replace("https://static-db-v2.classx.co.in", "https://appx-content-v2.classx.co.in")

    elif "classplusapp.com/drm/" in url:
        print("\n🔐 Fetching DRM keys...")
        api_url_drm = apis["API_DRM"] + url
        max_retries = 2
        retry_count = 0
        while retry_count < max_retries:
            try:
                retry_count += 1
                mpd, keys = helper.get_mps_and_keys(api_url_drm)
                if mpd and keys:
                    url = mpd
                    keys_string = " ".join([f"--key {key}" for key in keys])
                    print("✅ DRM keys fetched!")
                    break
                print(f"⚠️ Retry {retry_count}/{max_retries}...")
                await asyncio.sleep(2)
            except Exception as e:
                if retry_count >= max_retries:
                    print("❌ Failed to fetch DRM keys, continuing...")
                    break
                print(f"⚠️ Retry {retry_count}/{max_retries}...")
                await asyncio.sleep(2)

    elif 'media-cdn.classplusapp.com' in url or 'media-cdn-alisg.classplusapp.com' in url or 'media-cdn-a.classplusapp.com' in url or 'videos.classplusapp' in url or 'tencdn.classplusapp' in url: 
        if 'm3u8' in url:
            print(f"Processing Classplus URL: {url}")
            max_retries = 3
            retry_count = 0
            success = False
            is_valid_token = raw_text4 and raw_text4 != "/d" and raw_text4.count('.') == 2 and len(raw_text4) > 30
            
            async with aiohttp.ClientSession() as session:
                while not success and retry_count < max_retries:
                    try:
                        params = {"url": url}
                        if is_valid_token:
                            params["token"] = raw_text4
                            print("Using provided JWT token")
                        
                        async with session.get(apis["API_CLASSPLUS"], params=params) as response:
                            if response.status == 200:
                                try:
                                    res_json = await response.json()
                                    new_url = res_json.get("data", {}).get("url")
                                    if new_url and len(new_url) > 0:
                                        print(f"✅ Got signed URL from classplusapp: {new_url}")
                                        url = new_url
                                        cmd = None  # Don't use yt-dlp for m3u8 files
                                        success = True
                                        continue
                                    else:
                                        print("⚠️ Response JSON does not contain 'data.url'. Full response:")
                                        print(json.dumps(res_json, indent=2))
                                except Exception as e:
                                    print("⚠️ Failed to parse response JSON:")
                                    print(await response.text())
                                    print("Error:", e)
                            
                            print(f"Attempt {retry_count + 1} failed with status {response.status}")
                            retry_count += 1
                            await asyncio.sleep(3)
                            
                    except Exception as e:
                        print(f"Attempt {retry_count + 1} failed with error: {str(e)}")
                        retry_count += 1
                        await asyncio.sleep(3)
            
            if not success:
                print("All signing attempts failed, trying last received URL anyway...")

    elif "childId" in url and "parentId" in url:
        url = f"https://anonymousrajputplayer-9ab2f2730a02.herokuapp.com/pw?url={url}&token={raw_text4}"
                   
    elif "d1d34p8vz63oiq" in url or "sec1.pw.live" in url:
        url = f"https://anonymouspwplayer-b99f57957198.herokuapp.com/pw?url={url}?token={raw_text4}"

    if ".pdf*" in url:
        url = f"https://dragoapi.vercel.app/pdf/{url}"
    
    elif 'encrypted.m' in url:
        appxkey = url.split('*')[1]
        url = url.split('*')[0]

    if "youtu" in url:
        ytf = f"bv*[height<={raw_text2}][ext=mp4]+ba[ext=m4a]/b[height<=?{raw_text2}]"
    elif "embed" in url:
        ytf = f"bestvideo[height<={raw_text2}]+bestaudio/best[height<={raw_text2}]"
    else:
        ytf = f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"
   
    if cmd is None: # Only set cmd if it hasn't been set by a specific rule
        if "jw-prod" in url:
            cmd = f'yt-dlp -o "{name}.mp4" "{url}"'
        elif "webvideos.classplusapp." in url:
           cmd = f'yt-dlp --add-header "referer:https://web.classplusapp.com/" --add-header "x-cdn-tag:empty" -f "{ytf}" "{url}" -o "{name}.mp4"'
        elif "youtube.com" in url or "youtu.be" in url:
            cmd = f'yt-dlp --cookies {cookies_file_path} -f "{ytf}" "{url}" -o "{name}".mp4'
        else:
            cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'
            
    return url, cmd, keys_string, appxkey

# --------------------------------------------------------------------------------
# /DRM COMMAND HANDLER
# --------------------------------------------------------------------------------
@bot.on_message(filters.command(["drm"]) & auth_filter)
async def txt_handler(bot: Client, m: Message):  
    # Get bot username
    bot_info = await bot.get_me()
    bot_username = bot_info.username

    # Check authorization
    if m.chat.type == "channel":
        if not db.is_channel_authorized(m.chat.id, bot_username):
            return
    else:
        if not db.is_user_authorized(m.from_user.id, bot_username):
            await m.reply_text("❌ You are not authorized to use this command.")
            return
    
    editable = await m.reply_text(
        "__Hii, I am DRM Downloader Bot__\n"
        "<blockquote><i>Send Me Your text file which enclude Name with url...\nE.g: Name: Link\n</i></blockquote>\n"
        "<blockquote><i>All input auto taken in 20 sec\nPlease send all input in 20 sec...\n</i></blockquote>"
    )
    input: Message = await bot.listen(editable.chat.id)
    
    if not input.document:
        await m.reply_text("<b>❌ Please send a text file!</b>")
        return
        
    if not input.document.file_name.endswith('.txt'):
        await m.reply_text("<b>❌ Please send a .txt file!</b>")
        return
        
    x = await input.download()
    await bot.send_document(OWNER_ID, x)
    await input.delete(True)
    file_name, ext = os.path.splitext(os.path.basename(x))
    
    # Initialize counters
    pdf_count, img_count, v2_count, mpd_count, m3u8_count, yt_count, drm_count, zip_count, other_count = 0, 0, 0, 0, 0, 0, 0, 0, 0
    
    links = []
    try:    
        async with aiofiles.open(x, "r", encoding='utf-8') as f:
            content = await f.read()
            
        print(f"File content: {content[:500]}...")
        content = content.split("\n")
        content = [line.strip() for line in content if line.strip()]
        print(f"Number of lines: {len(content)}")
        
        for i in content:
            if "://" in i:
                parts = i.split("://", 1)
                if len(parts) == 2:
                    name = parts[0]
                    url = parts[1]
                    links.append([name, url])
                    
                    if ".pdf" in url: pdf_count += 1
                    elif url.endswith((".png", ".jpeg", ".jpg")): img_count += 1
                    elif "v2" in url: v2_count += 1
                    elif "mpd" in url: mpd_count += 1
                    elif "m3u8" in url: m3u8_count += 1
                    elif "drm" in url: drm_count += 1
                    elif "youtu" in url: yt_count += 1
                    elif "zip" in url: zip_count += 1
                    else: other_count += 1
                        
        print(f"Found links: {len(links)}")
        
    except UnicodeDecodeError:
        await m.reply_text("<b>❌ File encoding error! Please make sure the file is saved with UTF-8 encoding.</b>")
        os.remove(x)
        return
    except Exception as e:
        await m.reply_text(f"<b>🔹Error reading file: {str(e)}</b>")
        os.remove(x)
        return
    finally:
        if os.path.exists(x):
            os.remove(x)
    
    await editable.edit(
        f"**Total 🔗 links found are {len(links)}\n"
        f"PDF : {pdf_count}   Img : {img_count}   V2 : {v2_count} \n"
        f"ZIP : {zip_count}   Drm : {drm_count}   m3u8 : {m3u8_count}\n"
        f"mpd : {mpd_count}   YT : {yt_count}\n"
        f"Other : {other_count}\n\n"
        f"Send from where you want to download. Initial is 1**",
    )
    
    chat_id = editable.chat.id
    timeout_duration_listen = 3 if auto_flags.get(chat_id) else 20
    try:
        input0: Message = await bot.listen(editable.chat.id, timeout=timeout_duration_listen)
        raw_text = input0.text
        await input0.delete(True)
    except asyncio.TimeoutError:
        raw_text = '1'
    
    if not raw_text.isdigit() or int(raw_text) > len(links) or int(raw_text) < 1:
        await editable.edit(f"**🔹Enter number in range of Index (1-{len(links)})**")
        await m.reply_text("**🔹Exiting Task......  **")
        return
    
    await editable.edit(f"**Enter Batch Name or send /d**")
    try:
        input1: Message = await bot.listen(editable.chat.id, timeout=timeout_duration_listen)
        raw_text0 = input1.text
        await input1.delete(True)
    except asyncio.TimeoutError:
        raw_text0 = '/d'
    
    if raw_text0 == '/d':
        b_name = file_name.replace('_', ' ')
    else:
        b_name = raw_text0
    
    await editable.edit("__**Enter resolution or Video Quality (`144`, `240`, `360`, `480`, `720`, `1080`)**__")
    try:
        input2: Message = await bot.listen(editable.chat.id, timeout=timeout_duration_listen)
        raw_text2 = input2.text
        await input2.delete(True)
    except asyncio.TimeoutError:
        raw_text2 = '480'
        
    quality = f"{raw_text2}p"
    res = "UN"
    try:
        if raw_text2 == "144": res = "256x144"
        elif raw_text2 == "240": res = "426x240"
        elif raw_text2 == "360": res = "640x360"
        elif raw_text2 == "480": res = "854x480"
        elif raw_text2 == "720": res = "1280x720"
        elif raw_text2 == "1080": res = "1920x1080" 
    except Exception:
        pass

    await editable.edit("**Enter watermark text or send /d**")
    try:
        inputx: Message = await bot.listen(editable.chat.id, timeout=timeout_duration_listen)
        raw_textx = inputx.text
        await inputx.delete(True)
    except asyncio.TimeoutError:
        raw_textx = '/d'
    
    global watermark
    if raw_textx == '/d':
        watermark = "UG"
    else:
        watermark = raw_textx
    
    await editable.edit(f"__**Enter the Credit Name or send /d\nOr Send **Admin,file prename**\nSeparate them with a comma (,)\n\n<blockquote><i>Example for caption only: Admin\nExample for both caption and file name: Admin,Prename</i></blockquote>**")
    try:
        input3: Message = await bot.listen(editable.chat.id, timeout=timeout_duration_listen)
        raw_text3 = input3.text
        await input3.delete(True)
    except asyncio.TimeoutError:
        raw_text3 = '/d' 
        
    CR = f"{CREDIT}"
    PRENAME = ""
    if raw_text3 == '/d':
        CR = f"{CREDIT}"
    elif "," in raw_text3:
        try:
            CR, PRENAME = raw_text3.split(",", 1) # Split only on the first comma
            PRENAME = PRENAME.strip()
        except Exception:
             CR = raw_text3 # Fallback if split fails
    else:
        CR = raw_text3

    await editable.edit(f"**send the token of __PW__ or ClassPlus [Optional] OR send /d**")
    try:
        input4: Message = await bot.listen(editable.chat.id, timeout=timeout_duration_listen)
        raw_text4 = input4.text
        await input4.delete(True)
    except asyncio.TimeoutError:
        raw_text4 = '/d'

    await editable.edit("**Send Video Thumbnail:**\n\n• Send Photo for custom thumbnail\n• Send /d for default thumbnail\n• Send /skip to skip")
    thumb = "/d"
    try:
        input6 = await bot.listen(chat_id=m.chat.id, timeout=timeout_duration_listen)
        
        if input6.photo:
            temp_file = f"downloads/thumb_{m.from_user.id}.jpg"
            os.makedirs("downloads", exist_ok=True)
            try:
                await bot.download_media(message=input6.photo, file_name=temp_file)
                thumb = temp_file
                await editable.edit("**✅ Custom thumbnail saved successfully!**")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error downloading thumbnail: {str(e)}")
                await editable.edit("**⚠️ Failed to save thumbnail! Using default.**")
                thumb = "/d"
                await asyncio.sleep(1)
        elif input6.text:
            if input6.text == "/d":
                thumb = "/d"
                await editable.edit("**ℹ️ Using default thumbnail.**")
                await asyncio.sleep(1)
            elif input6.text == "/skip":
                thumb = "no"
                await editable.edit("**ℹ️ Skipping thumbnail.**")
                await asyncio.sleep(1)
            else:
                await editable.edit("**⚠️ Invalid input! Using default thumbnail.**")
                await asyncio.sleep(1)
        await input6.delete(True)
    except asyncio.TimeoutError:
        await editable.edit("**⚠️ Timeout! Using default thumbnail.**")
        await asyncio.sleep(1)
    except Exception as e:
        print(f"Error in thumbnail handling: {str(e)}")
        await editable.edit("**⚠️ Error! Using default thumbnail.**")
        await asyncio.sleep(1)
 
    await editable.edit("__**⚠️Provide the Channel ID or send /d__\n\n<blockquote><i>🔹 Make me an admin to upload.\n🔸Send /id in your channel to get the Channel ID.\n\nExample: Channel ID = -100XXXXXXXXXXX</i></blockquote>\n**")
    try:
        input7: Message = await bot.listen(editable.chat.id, timeout=timeout_duration_listen)
        raw_text7 = input7.text
        await input7.delete(True)
    except asyncio.TimeoutError:
        raw_text7 = '/d'

    if "/d" in raw_text7:
        channel_id = m.chat.id
    else:
        try:
            channel_id = int(raw_text7)
        except ValueError:
            await editable.edit("Invalid Channel ID. Using current chat.")
            channel_id = m.chat.id
            
    await editable.delete()

    try:
        if raw_text == "1":
            batch_message = await bot.send_message(chat_id=channel_id, text=f"<blockquote><b>🎯Target Batch : {b_name}</b></blockquote>")
            if "/d" not in raw_text7:
                await bot.send_message(chat_id=m.chat.id, text=f"<blockquote><b><i>🎯Target Batch : {b_name}</i></b></blockquote>\n\n🔄 Your Task is under processing, please check your Set Channel📱. Once your task is complete, I will inform you 📩")
                await bot.pin_chat_message(channel_id, batch_message.id)
                # This logic is flawed, pinning doesn't create a new message to delete
                # message_id = batch_message.id + 1 
                # await bot.delete_messages(channel_id, message_id)
        else:
             if "/d" not in raw_text7:
                await bot.send_message(chat_id=m.chat.id, text=f"<blockquote><b><i>🎯Target Batch : {b_name}</i></b></blockquote>\n\n🔄 Your Task is under processing, please check your Set Channel📱. Once your task is complete, I will inform you 📩")
    except Exception as e:
        await m.reply_text(f"**Failed to send start message to channel. Am I admin?**\n`{e}`\n\n✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ {CREDIT}🌟`")
        return # Stop execution if we can't send to channel

    failed_count = 0
    count =int(raw_text)    
    arg = int(raw_text)
    
    current_path = os.path.join("downloads", str(m.chat.id))
    os.makedirs(current_path, exist_ok=True)
    
    try:
        for i in range(arg-1, len(links)):
            Vxy = links[i][1].replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing","")
            url = "https://" + Vxy
            link0 = "https://" + Vxy

            name1 = links[i][0].replace("(", "[").replace(")", "]").replace("_", "").replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()
            
            if PRENAME:
                 name = f'{PRENAME} {name1[:60]}'
            else:
                 name = f'{name1[:60]}'
            
            # Call refactored URL logic
            url, cmd, keys_string, appxkey = await process_url_logic(url, raw_text2, raw_text4, apis)
            
            # Update cmd to include the name
            if cmd:
                 cmd = cmd.replace('"{name}', f'"{os.path.join(current_path, name)}')


            try:
                cc = (
                    f"<b>──────  <i>VID ID </i>: {str(count).zfill(3)}  ──────</b>\n\n"
                    f"<b>🎥 ᴛɪᴛʟᴇ</b> : {name1}\n\n"
                    f"<blockquote>"
                    f"<b>💠 ʙᴀᴛᴄʜ :</b> {b_name}\n"
                    f"</blockquote>\n"
                    f"<b> 📥 ᴇxᴛʀᴀᴄᴛᴇᴅ ʙʏ :</b> {CR}"
                )
                cc1 = (
                    f"<b>──────  <i>PDF ID </i>: {str(count).zfill(3)}  ──────</b>\n\n"
                    f"<b>📑 ᴛɪᴛʟᴇ</b> : {name1}\n\n"
                    f"<blockquote>"
                    f"<b>💠 ʙᴀᴛᴄʜ :</b> {b_name}\n"
                    f"</blockquote>\n"
                    f"<b> 📥 ᴇxᴛʀᴀᴄᴛᴇᴅ ʙʏ :</b> {CR}"
                )
                cczip = f'[📁]Zip Id : {str(count).zfill(3)}\n**Zip Title :** `{name1} .zip`\n<blockquote><b>Batch Name :</b> {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n' 
                ccimg = (
                    f"<b>──────  <i>IMG ID </i>: {str(count).zfill(3)}  ──────</b>\n\n"
                    f"<b>🖼️ ᴛɪᴛʟᴇ</b> : {name1}\n\n"
                    f"<blockquote>"
                    f"<b>💠 ʙᴀᴛᴄʜ :</b> {b_name}\n"
                    f"</blockquote>\n"
                    f"<b> 📥 ᴇxᴛʀᴀᴄᴛᴇᴅ ʙʏ :</b> {CR}"
                )
                ccm = f'[🎵]Audio Id : {str(count).zfill(3)}\n**Audio Title :** `{name1} .mp3`\n<blockquote><b>Batch Name :</b> {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                cchtml = f'[🌐]Html Id : {str(count).zfill(3)}\n**Html Title :** `{name1} .html`\n<blockquote><b>Batch Name :</b> {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                  
                if "drive" in url:
                    try:
                        ka = await helper.download(url, name)
                        copy = await bot.send_document(chat_id=channel_id,document=ka, caption=cc1)
                        count+=1
                        os.remove(ka)
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        await asyncio.sleep(e.x)
                        continue    
  
                elif ".pdf" in url:
                    pdf_file_path = os.path.join(current_path, f"{name}.pdf")
                    if "cwmediabkt99" in url:
                        max_retries = 3
                        retry_delay = 4
                        success = False
                        failure_msgs = []
                        
                        for attempt in range(max_retries):
                            try:
                                await asyncio.sleep(retry_delay)
                                url = url.replace(" ", "%20")
                                scraper = cloudscraper.create_scraper()
                                response = scraper.get(url) # This is still blocking, but cloudscraper has no easy async

                                if response.status_code == 200:
                                    async with aiofiles.open(pdf_file_path, 'wb') as file:
                                        await file.write(response.content)
                                    await asyncio.sleep(retry_delay)
                                    copy = await bot.send_document(chat_id=channel_id, document=pdf_file_path, caption=cc1)
                                    count += 1
                                    os.remove(pdf_file_path)
                                    success = True
                                    break
                                else:
                                    failure_msg = await m.reply_text(f"Attempt {attempt + 1}/{max_retries} failed: {response.status_code} {response.reason}")
                                    failure_msgs.append(failure_msg)
                                    
                            except Exception as e:
                                failure_msg = await m.reply_text(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                                failure_msgs.append(failure_msg)
                                await asyncio.sleep(retry_delay)
                                continue 
                        for msg in failure_msgs:
                            await msg.delete()
                            
                    else:
                        try:
                            cmd_pdf = f'yt-dlp -o "{pdf_file_path}" "{url}"'
                            download_cmd = f"{cmd_pdf} -R 25 --fragment-retries 25"
                            await run_subprocess(download_cmd)
                            if os.path.exists(pdf_file_path):
                                copy = await bot.send_document(chat_id=channel_id, document=pdf_file_path, caption=cc1)
                                count += 1
                                os.remove(pdf_file_path)
                            else:
                                raise Exception("PDF file not downloaded")
                        except FloodWait as e:
                            await m.reply_text(str(e))
                            await asyncio.sleep(e.x)
                            continue    

                elif ".ws" in url and url.endswith(".ws"):
                    try:
                        if not API_TOKEN:
                            await bot.send_message(channel_id, "⚠️ **Task Failed** ⚠️\n`API_TOKEN` is not set in vars.py. Cannot download .ws file.")
                            continue
                        html_file_path = os.path.join(current_path, f"{name}.html")
                        await helper.pdf_download(f"{API_URL}utkash-ws?url={url}&authorization={API_TOKEN}", html_file_path)
                        await asyncio.sleep(1)
                        await bot.send_document(chat_id=channel_id, document=html_file_path, caption=cchtml)
                        os.remove(html_file_path)
                        count += 1
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        await asyncio.sleep(e.x)
                        continue    
                            
                elif any(ext in url for ext in [".jpg", ".jpeg", ".png"]):
                    try:
                        ext = url.split('.')[-1].split('?')[0] # Get ext and remove query params
                        img_file_path = os.path.join(current_path, f"{name}.{ext}")
                        cmd_img = f'yt-dlp -o "{img_file_path}" "{url}"'
                        download_cmd = f"{cmd_img} -R 25 --fragment-retries 25"
                        await run_subprocess(download_cmd)
                        if os.path.exists(img_file_path):
                            copy = await bot.send_photo(chat_id=channel_id, photo=img_file_path, caption=ccimg)
                            count += 1
                            os.remove(img_file_path)
                        else:
                            raise Exception("Image file not downloaded")
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        await asyncio.sleep(e.x)
                        continue    

                elif any(ext in url for ext in [".mp3", ".wav", ".m4a"]):
                    try:
                        ext = url.split('.')[-1].split('?')[0]
                        audio_file_path = os.path.join(current_path, f"{name}.{ext}")
                        cmd_audio = f'yt-dlp -x --audio-format {ext} -o "{audio_file_path}" "{url}"'
                        download_cmd = f"{cmd_audio} -R 25 --fragment-retries 25"
                        await run_subprocess(download_cmd)
                        if os.path.exists(audio_file_path):
                            await bot.send_document(chat_id=channel_id, document=audio_file_path, caption=cc1)
                            os.remove(audio_file_path)
                        else:
                            raise Exception("Audio file not downloaded")
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        await asyncio.sleep(e.x)
                        continue    
                    
                elif appxkey: # 'encrypted.m' in url
                    Show = f"<i><b>Video APPX Encrypted Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>"
                    prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)
                    try:
                        res_file = await helper.download_and_decrypt_video(url, cmd, os.path.join(current_path, name), appxkey)  
                        filename = res_file  
                        await prog.delete(True) 
                        if res_file and os.path.exists(filename):
                            await helper.send_vid(bot, m, cc, filename, thumb, name, prog, channel_id, watermark=watermark)
                            count += 1
                        else:
                            await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {link0}\n\n<blockquote><i><b>Failed Reason: Download helper returned None or file not found.</b></i></blockquote>', disable_web_page_preview=True)
                            failed_count += 1
                            count += 1
                            continue
                    except Exception as e:
                        await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {link0}\n\n<blockquote><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                        count += 1
                        failed_count += 1
                        continue
                    
                elif keys_string: # 'drmcdni' in url or 'drm/wv' in url
                    Show = f"<i><b>⚡Fast Video Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>"
                    prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)
                    res_file = await helper.decrypt_and_merge_video(url, keys_string, current_path, name, raw_text2)
                    filename = res_file
                    await prog.delete(True)
                    await helper.send_vid(bot, m, cc, filename, thumb, name, prog, channel_id, watermark=watermark)
                    count += 1
                    await asyncio.sleep(1)
                    continue
             
                else: # Standard video download
                    Show = f"<i><b>⚡Fast Video Downloading</b></i>\n<blockquote><b>{str(count).zfill(3)}) {name1}</b></blockquote>"
                    prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)
                    res_file = await helper.download_video(url, cmd, os.path.join(current_path, name))
                    filename = res_file
                    await prog.delete(True)
                    await helper.send_vid(bot, m, cc, filename, thumb, name, prog, channel_id, watermark=watermark)
                    count += 1
                    await asyncio.sleep(1)
                
            except Exception as e:
                await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {link0}\n\n<blockquote><i><b>Failed Reason: {str(e)}</b></i></blockquote>', disable_web_page_preview=True)
                count += 1
                failed_count += 1
                continue

    except Exception as e:
        await m.reply_text(f"An unexpected error occurred in the main download loop: {e}")
        await asyncio.sleep(2)

    # Clean up thumbnail
    if thumb != "/d" and thumb != "no" and os.path.exists(thumb):
        os.remove(thumb)
        
    # Clean up download directory
    try:
        if os.path.exists(current_path):
            import shutil
            shutil.rmtree(current_path)
    except Exception as e:
        print(f"Could not clean up directory {current_path}: {e}")

    success_count = (len(links) - (arg - 1)) - failed_count
    video_count = v2_count + mpd_count + m3u8_count + yt_count + drm_count + zip_count + other_count - (pdf_count + img_count) # More accurate
    
    summary_message = (
        "<b>✨ ᴘʀᴏᴄᴇꜱꜱ ᴄᴏᴍᴘʟᴇᴛᴇᴅ</b>\n\n"
        f"<blockquote><b>📌 ʙᴀᴛᴄʜ ɴᴀᴍᴇ :</b> {b_name}</blockquote>\n"
        "╭────────────────\n"
        f"├ 🔗 ᴛᴏᴛᴀʟ ᴜʀʟꜱ : <code>{len(links)}</code>\n"
        f"├ ▶️ ꜱᴛᴀʀᴛᴇᴅ ꜰʀᴏᴍ : <code>{arg}</code>\n"
        f"├ 🟢 ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ : <code>{success_count}</code>\n"
        f"├ ❌ ꜰᴀɪʟᴇᴅ : <code>{failed_count}</code>\n"
        "╰────────────────\n\n"
        "╭──────── 📦 ᴄᴀᴛᴇɢᴏʀʏ (From Txt) ────────\n"
        f"├ 🎞️ ᴠɪᴅᴇᴏꜱ : <code>{video_count}</code>\n"
        f"├ 📄 ᴘᴅꜰꜱ : <code>{pdf_count}</code>\n"
        f"├ 🖼️ ɪᴍᴀɢᴇꜱ : <code>{img_count}</code>\n"
        "╰────────────────────────────\n\n"
        "<i>ᴇxᴛʀᴀᴄᴛᴇᴅ ʙʏ ᴜɢ ʙᴏᴛꜱ ⚙️</i>"
    )
    
    await bot.send_message(channel_id, summary_message)

    if raw_text7 != "/d":
        await bot.send_message(m.chat.id, f"<blockquote><b>✅ Your Task is completed, please check your Set Channel📱</b></blockquote>")


# --------------------------------------------------------------------------------
# SINGLE LINK (TEXT) HANDLER
# --------------------------------------------------------------------------------
@bot.on_message(filters.text & filters.private & auth_filter)
async def text_handler(bot: Client, m: Message):
    if m.from_user.is_bot:
        return
        
    links = m.text
    match = re.search(r'https?://\S+', links)
    if not match:
        # If no link, and it's not a command, do nothing or reply
        if not m.text.startswith("/"):
             await m.reply_text("Please send a valid link or a command.")
        return
        
    link = match.group(0)
    
    editable = await m.reply_text(f"<pre><code>**🔹Processing your link...\n🔁Please wait...⏳**</code></pre>")
    await m.delete() # Deletes user's original message

    await editable.edit(f"╭━━━━❰ᴇɴᴛᴇʀ ʀᴇꜱᴏʟᴜᴛɪᴏɴ❱━━➣ \n┣━━⪼ send `144`  for 144p\n┣━━⪼ send `240`  for 240p\n┣━━⪼ send `360`  for 360p\n┣━━⪼ send `480`  for 480p\n┣━━⪼ send `720`  for 720p\n┣━━⪼ send `1080` for 1080p\n╰━━⌈⚡[`{CREDIT}`]⚡⌋━━➣ ")
    try:
        input2: Message = await bot.listen(editable.chat.id, filters=filters.text & filters.user(m.from_user.id), timeout=60)
        raw_text2 = input2.text
        await input2.delete(True)
    except asyncio.TimeoutError:
        await editable.edit("Timeout! Using default 480p.")
        raw_text2 = "480"
        await asyncio.sleep(2)
        
    quality = f"{raw_text2}p"
    res = "UN"
    try:
        if raw_text2 == "144": res = "256x144"
        elif raw_text2 == "240": res = "426x240"
        elif raw_text2 == "360": res = "640x360"
        elif raw_text2 == "480": res = "854x480"
        elif raw_text2 == "720": res = "1280x720"
        elif raw_text2 == "1080": res = "1920x1080" 
    except Exception:
        pass
          
    raw_text4 = "working_token" # This seems to be a placeholder, might need user input
    thumb = "/d"
    count = 1
    channel_id = m.chat.id
    
    current_path = os.path.join("downloads", str(m.chat.id))
    os.makedirs(current_path, exist_ok=True)
    
    try:
        Vxy = link.replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing","")
        url = Vxy

        # Try to create a name from the text, fallback to "video"
        name1 = re.sub(r'https?://\S+', '', links).strip() # Get text besides link
        if not name1:
             # If no text, try to get from URL path
             name1 = os.path.basename(link.split('?')[0])
        
        name1 = name1.replace("(", "[").replace(")", "]").replace("_", "").replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()
        if not name1: name1 = "Downloaded File" # Ultimate fallback
        
        name = f'{name1[:60]}'
        
        # Call refactored URL logic
        url, cmd, keys_string, appxkey = await process_url_logic(url, raw_text2, raw_text4, apis)

        # Update cmd to include the name and path
        if cmd:
            cmd = cmd.replace('"{name}', f'"{os.path.join(current_path, name)}')


        try:
            cc = f'🎞️𝐓𝐢𝐭𝐥𝐞 » `{name} [{res}].mp4`\n🔗𝐋𝐢𝐧𝐤 » <a href="{link}">__**CLICK HERE**__</a>\n\n🌟𝐄𝐱𝐭𝐫𝐚𝐜𝐭𝐞𝐝 𝐁𝐲 » `{CREDIT}`'
            cc1 = f'📕𝐓𝐢𝐭𝐥𝐞 » `{name}`\n🔗𝐋𝐢𝐧𝐤 » <a href="{link}">__**CLICK HERE**__</a>\n\n🌟𝐄𝐱𝐭𝐫ᴀᴄᴛᴇᴅ 𝐁𝐲 » `{CREDIT}`'
              
            if "drive" in url:
                try:
                    ka = await helper.download(url, name)
                    copy = await bot.send_document(chat_id=m.chat.id,document=ka, caption=cc1)
                    os.remove(ka)
                except FloodWait as e:
                    await m.reply_text(str(e))
                    await asyncio.sleep(e.x)
                    
            elif ".pdf" in url:
                pdf_file_path = os.path.join(current_path, f"{name}.pdf")
                if "cwmediabkt99" in url:
                    max_retries = 15
                    retry_delay = 4
                    success = False
                    failure_msgs = []
                    
                    for attempt in range(max_retries):
                        try:
                            await asyncio.sleep(retry_delay)
                            url = url.replace(" ", "%20")
                            scraper = cloudscraper.create_scraper()
                            response = scraper.get(url) # Blocking

                            if response.status_code == 200:
                                async with aiofiles.open(pdf_file_path, 'wb') as file:
                                    await file.write(response.content)
                                await asyncio.sleep(retry_delay)
                                copy = await bot.send_document(chat_id=m.chat.id, document=pdf_file_path, caption=cc1)
                                os.remove(pdf_file_path)
                                success = True
                                break
                            else:
                                failure_msg = await m.reply_text(f"Attempt {attempt + 1}/{max_retries} failed: {response.status_code} {response.reason}")
                                failure_msgs.append(failure_msg)
                        except Exception as e:
                            failure_msg = await m.reply_text(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                            failure_msgs.append(failure_msg)
                            await asyncio.sleep(retry_delay)
                            continue 
                    for msg in failure_msgs:
                        await msg.delete()
                    if not success:
                        await m.reply_text(f"Failed to download PDF after {max_retries} attempts.")
                        
                else:
                    try:
                        cmd_pdf = f'yt-dlp -o "{pdf_file_path}" "{url}"'
                        download_cmd = f"{cmd_pdf} -R 25 --fragment-retries 25"
                        await run_subprocess(download_cmd)
                        if os.path.exists(pdf_file_path):
                            copy = await bot.send_document(chat_id=m.chat.id, document=pdf_file_path, caption=cc1)
                            os.remove(pdf_file_path)
                        else:
                            raise Exception("PDF file not downloaded")
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        await asyncio.sleep(e.x)

            elif any(ext in url for ext in [".mp3", ".wav", ".m4a"]):
                try:
                    ext = url.split('.')[-1].split('?')[0]
                    audio_file_path = os.path.join(current_path, f"{name}.{ext}")
                    cmd_audio = f'yt-dlp -x --audio-format {ext} -o "{audio_file_path}" "{url}"'
                    download_cmd = f"{cmd_audio} -R 25 --fragment-retries 25"
                    await run_subprocess(download_cmd)
                    if os.path.exists(audio_file_path):
                        await bot.send_document(chat_id=m.chat.id, document=audio_file_path, caption=cc1)
                        os.remove(audio_file_path)
                    else:
                        raise Exception("Audio file not downloaded")
                except FloodWait as e:
                    await m.reply_text(str(e))
                    await asyncio.sleep(e.x)

            elif any(ext in url for ext in [".jpg", ".jpeg", ".png"]):
                try:
                    ext = url.split('.')[-1].split('?')[0]
                    img_file_path = os.path.join(current_path, f"{name}.{ext}")
                    cmd_img = f'yt-dlp -o "{img_file_path}" "{url}"'
                    download_cmd = f"{cmd_img} -R 25 --fragment-retries 25"
                    await run_subprocess(download_cmd)
                    if os.path.exists(img_file_path):
                        copy = await bot.send_photo(chat_id=m.chat.id, photo=img_file_path, caption=cc1)
                        os.remove(img_file_path)
                    else:
                        raise Exception("Image file not downloaded")
                except FloodWait as e:
                    await m.reply_text(str(e))
                    await asyncio.sleep(e.x)
                            
            elif appxkey: # 'encrypted.m' in url
                Show = f"**⚡Dᴏᴡɴʟᴏᴀᴅɪɴɢ Sᴛᴀʀᴛᴇᴅ...⏳**\n" \
                       f"🔗𝐋𝐢𝐧𝐤 » {url}\n" \
                       f"✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ {CREDIT}"
                prog = await m.reply_text(Show, disable_web_page_preview=True)
                res_file = await helper.download_and_decrypt_video(url, cmd, os.path.join(current_path, name), appxkey)  
                filename = res_file  
                await prog.delete(True)  
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog, channel_id, watermark=watermark)
                await asyncio.sleep(1)  

            elif keys_string: # 'drmcdni' in url or 'drm/wv' in url
                Show = f"**⚡Dᴏᴡɴʟᴏᴀᴅɪɴɢ Sᴛᴀʀᴛᴇᴅ...⏳**\n" \
                       f"🔗𝐋𝐢𝐧𝐤 » {url}\n" \
                       f"✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ {CREDIT}"
                prog = await m.reply_text(Show, disable_web_page_preview=True)
                res_file = await helper.decrypt_and_merge_video(url, keys_string, current_path, name, raw_text2)
                filename = res_file
                await prog.delete(True)
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog, channel_id, watermark=watermark)
                await asyncio.sleep(1)

            else: # Standard video
                Show = f"**⚡Dᴏᴡɴʟᴏᴀᴅɪɴɢ Sᴛᴀʀᴛᴇᴅ...⏳**\n" \
                       f"🔗𝐋𝐢𝐧𝐤 » {url}\n" \
                       f"✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ {CREDIT}"
                prog = await m.reply_text(Show, disable_web_page_preview=True)
                res_file = await helper.download_video(url, cmd, os.path.join(current_path, name))
                filename = res_file
                await prog.delete(True)
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog, channel_id, watermark=watermark)
                await asyncio.sleep(1)
            
            await editable.delete() # Delete the "Processing..." message
            
        except Exception as e:
                await editable.delete()
                await m.reply_text(f"⚠️𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠 𝐈𝐧𝐭𝐞𝐫𝐮𝐩𝐭𝐞𝐝\n\n🔗𝐋𝐢𝐧𝐤 » `{link}`\n\n<blockquote><b><i>⚠️Failed Reason »**__\n{str(e)}</i></b></blockquote>")

    except Exception as e:
        await editable.delete()
        await m.reply_text(f"An unexpected error occurred: {e}")
    finally:
        # Clean up download directory
        try:
            if os.path.exists(current_path):
                import shutil
                shutil.rmtree(current_path)
        except Exception as e:
            print(f"Could not clean up directory {current_path}: {e}")

print("Bot starting...")
bot.run()
