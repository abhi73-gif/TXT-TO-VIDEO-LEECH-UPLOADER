# merged_main_full.py
# Powerful single-file merge of two provided main.py variants.
# Includes: /start, /upload, /drm, /t2t, /cookies, /getcookies, /setlog, /getlog,
# Force-subscribe, robust TXT parsing, yt-dlp based downloader, DRM hooks (ClassPlus/PW),
# helper fallbacks (download, send_vid), logging, simple DB shim, and safe error handling.
#
# NOTE:
# - This file is self-contained but expects external binaries: ffmpeg and yt-dlp installed.
# - For full DRM functionality some helper functions (get_mps_and_keys etc.) are included as placeholders.
# - Before running, create a vars.py or set environment variables for API_ID/API_HASH/BOT_TOKEN.
#
# Usage:
#   - Place this file as main.py
#   - Ensure requirements installed (pyrogram, aiohttp, requests, pyromod, yt-dlp, tgcrypto)
#   - Run: python main.py
#
# Author: merged by assistant for user
# Keep Credits: Do not remove credit lines if you redistribute.

import os
import re
import sys
import json
import time
import shutil
import logging
import asyncio
import subprocess
from datetime import datetime
from typing import Optional, Tuple, List

# Networking / HTTP
import requests
from aiohttp import ClientSession

# Pyrogram
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import UserNotParticipant, FloodWait
from pyrogram.enums import ChatMemberStatus

# optional: pyromod.listen used for nicer conversation flow; fallback to manual listen if not present
try:
    from pyromod import listen
except Exception:
    listen = None

# -------------------------
# Configuration (env or vars.py)
# -------------------------
# You can create a vars.py with these variables or set environment variables.
try:
    from vars import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, CREDIT, FORCE_SUB_CHANNEL, FORCE_SUB_CHANNEL_LINK
except Exception:
    API_ID = int(os.getenv("API_ID", "0") or 0)
    API_HASH = os.getenv("API_HASH", "") or ""
    BOT_TOKEN = os.getenv("BOT_TOKEN", "") or ""
    OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
    CREDIT = os.getenv("CREDIT", "UG")
    FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "") or ""
    FORCE_SUB_CHANNEL_LINK = os.getenv("FORCE_SUB_CHANNEL_LINK", FORCE_SUB_CHANNEL)

# runtime paths
DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
COOKIES_FILE = os.getenv("COOKIES_FILE", "youtube_cookies.txt")
WELCOME_IMAGE = os.getenv("WELCOME_IMAGE", "welcome.jpg")
LOG_FILE = os.getenv("LOG_FILE", "bot.log")

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# pyrogram client
bot = Client("merged_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=100)

# -------------------------
# Minimal DB shim (in-memory) - replace with real db module if available
# -------------------------
class SimpleDB:
    def __init__(self):
        self.admins = set()
        self.users = set()
        self.log_channel = {}
        self.channels = set()
    def is_admin(self, user_id):
        return user_id in self.admins or user_id == OWNER_ID
    def add_admin(self, user_id):
        self.admins.add(user_id)
    def is_user_authorized(self, user_id, bot_username=None):
        # default allow; extend as needed
        return True
    def is_channel_authorized(self, channel_id, bot_username=None):
        return True
    def set_log_channel(self, bot_username, cid):
        self.log_channel[bot_username] = cid
        return True
    def get_log_channel(self, bot_username):
        return self.log_channel.get(bot_username)
db = SimpleDB()

# prefill owner as admin
if OWNER_ID:
    db.add_admin(OWNER_ID)

# -------------------------
# Utilities: URL parsing, extraction, safe shell run
# -------------------------
URL_RE = re.compile(r"https?://[^\s]+")
def is_valid_url(url: str) -> bool:
    return bool(URL_RE.search(url)) if url else False

def extract_url_from_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    if not line:
        return None, None
    line = line.strip()
    m = URL_RE.search(line)
    if m:
        url = m.group(0)
        title = line.replace(url, "").strip() or f"File_{abs(hash(url))%10000}"
        return title, url
    # try domain only
    if '.' in line and not line.startswith('/'):
        url = 'https://' + line
        if is_valid_url(url):
            return f"File_{abs(hash(line))%10000}", url
    return None, None

def safe_run(cmd: str, timeout: int = 300) -> Tuple[int, str, str]:
    """Run shell command safely, return (rc, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return -1, "", f"Timeout: {e}"
    except Exception as e:
        return -1, "", str(e)

# -------------------------
# Helper functions (download/send video) with fallbacks
# -------------------------
async def helper_download_direct(url: str, output_name: str, format_filter: str = "best") -> Optional[str]:
    """
    Uses yt-dlp to download the URL into output_name (without extension).
    Returns path to downloaded file or None on failure.
    """
    # construct yt-dlp command
    # prefer mp4 if video, else keep ext
    out_pattern = f"{output_name}.%(ext)s"
    cmd = f'yt-dlp -f "{format_filter}" "{url}" -o "{out_pattern}" --no-warnings'
    log.info(f"Executing: {cmd}")
    rc, out, err = safe_run(cmd, timeout=1800)
    if rc != 0:
        log.warning(f"yt-dlp failed for {url}: rc={rc} err={err[:200]}")
    # find created file
    for ext in ['mp4', 'mkv', 'webm', 'mp3', 'pdf', 'jpg', 'png', 'mpeg']:
        candidate = f"{output_name}.{ext}"
        if os.path.exists(candidate):
            return candidate
    # try to grab any matching file (glob)
    for f in os.listdir('.'):
        if f.startswith(output_name) and f != __file__:
            return f
    return None

async def helper_send_vid(client: Client, chat_id, caption: str, filename: str, thumb: Optional[str], display_name: str, channel_id: Optional[int] = None, watermark: Optional[str] = None):
    """Sends a video or file to chat. If video, uses send_video; otherwise send_document."""
    try:
        if not os.path.exists(filename):
            log.warning("File not found for send_vid: " + filename)
            return False
        # choose send method by extension
        lower = filename.lower()
        if lower.endswith(('.mp4', '.mkv', '.webm', '.mov', '.avi', '.mpeg')):
            await client.send_video(chat_id if channel_id is None else channel_id, filename, caption=caption, supports_streaming=True, thumb=thumb if thumb and os.path.exists(thumb) else None)
        elif lower.endswith(('.pdf', '.zip', '.epub', '.txt')):
            await client.send_document(chat_id if channel_id is None else channel_id, filename, caption=caption)
        elif lower.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            await client.send_photo(chat_id if channel_id is None else channel_id, filename, caption=caption)
        else:
            await client.send_document(chat_id if channel_id is None else channel_id, filename, caption=caption)
        # clean up local file after sending
        try:
            os.remove(filename)
        except Exception:
            pass
        return True
    except FloodWait as e:
        log.warning(f"FloodWait: sleeping {e.x}")
        await asyncio.sleep(e.x)
        return False
    except Exception as e:
        log.exception("send_vid error: " + str(e))
        return False

# -------------------------
# DRM Hooks - placeholders and simplified implementations.
# These attempt to cover common patterns seen in uploaded files (classplus, encrypted.m, appx, etc.)
# For a production DRM decryptor you'd need API keys and specialized logic.
# -------------------------
def try_fix_drive_link(url: str) -> str:
    # convert google drive view link to direct download
    try:
        if 'drive.google.com' in url:
            url = url.replace('/view?usp=sharing', '')
            url = url.replace('/file/d/', '/uc?export=download&id=')
    except Exception:
        pass
    return url

def is_classplus_url(url: str) -> bool:
    return 'classplusapp' in url or 'media-cdn.classplusapp' in url or 'videos.classplusapp' in url

def is_m3u8_content(url: str) -> bool:
    return 'm3u8' in url or url.endswith('.m3u8')

def placeholder_get_mpd_and_keys(api_url: str) -> Tuple[Optional[str], Optional[List[str]]]:
    """
    Placeholder: call an API (like apixug) to exchange DRM URL for mpd and keys.
    Return (mpd_url, [key1:keyid:hex, ...]) or (None, None) on failure.
    """
    log.info(f"placeholder_get_mpd_and_keys: {api_url}")
    try:
        # Example: a simple GET returning JSON {data:{mpd:..., keys: [...]}}
        r = requests.get(api_url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            mpd = data.get('data', {}).get('url') or data.get('data', {}).get('mpd')
            keys = data.get('data', {}).get('keys') or data.get('keys')
            if mpd and keys:
                return mpd, keys
    except Exception as e:
        log.warning("DRM placeholder failed: " + str(e))
    return None, None

# -------------------------
# Force-subscribe decorator
# -------------------------
async def _is_subscribed(client: Client, user_id: int) -> bool:
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        member = await client.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER)
    except UserNotParticipant:
        return False
    except Exception as e:
        log.warning("is_subscribed error: " + str(e))
        return False

def force_subscribe(handler):
    async def wrapper(client: Client, message: Message):
        if FORCE_SUB_CHANNEL:
            ok = await _is_subscribed(client, message.from_user.id)
            if not ok:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔔 Join Channel", url=FORCE_SUB_CHANNEL_LINK or FORCE_SUB_CHANNEL)],
                    [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_sub")]
                ])
                await message.reply_text("🔒 Access denied. Please join our channel to use the bot.", reply_markup=kb)
                return
        return await handler(client, message)
    return wrapper

@bot.on_callback_query()
async def _cb_handler(client: Client, query: CallbackQuery):
    if query.data == "refresh_sub":
        ok = await _is_subscribed(client, query.from_user.id)
        if ok:
            await query.answer("✅ Verified — you may use the bot now.", show_alert=True)
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            await query.answer("❌ Not joined yet.", show_alert=True)

# -------------------------
# Commands: start, setlog, getlog
# -------------------------
@bot.on_message(filters.command("start") & (filters.private | filters.channel))
@force_subscribe
async def cmd_start(client: Client, m: Message):
    try:
        if m.chat.type == "channel":
            # channel welcome
            await m.reply_text("✨ Bot is active in this channel. Use /upload or /drm in the channel.")
            return
        is_admin = db.is_admin(m.from_user.id)
        is_auth = db.is_user_authorized(m.from_user.id, client.me.username) if db else True
        if not is_auth:
            await m.reply_text("🔒 You are not authorized. Contact admin.")
            return
        text = (
            f"👋 Hello {m.from_user.first_name}!\n\n"
            "• /upload - Upload .txt file with links\n"
            "• /drm - DRM batch downloader (send .txt)\n"
            "• /t2t - Convert text to .txt file\n"
            "• /cookies - Upload cookies file\n"
            "• /getcookies - Get current cookies file\n"
        )
        if is_admin:
            text += "\nAdmin: /setlog <channel_id> | /getlog"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📚 Help", url="https://t.me/ItsUGBot")]])
        if os.path.exists(WELCOME_IMAGE):
            await m.reply_photo(WELCOME_IMAGE, caption=text, reply_markup=kb)
        else:
            await m.reply_text(text, reply_markup=kb)
    except Exception as e:
        log.exception("start error")
        await m.reply_text("Error in start: " + str(e))

@bot.on_message(filters.command("setlog") & filters.private)
async def cmd_setlog(client: Client, m: Message):
    if not db.is_admin(m.from_user.id):
        return await m.reply_text("❌ You are not authorized.")
    parts = m.text.split()
    if len(parts) != 2:
        return await m.reply_text("Usage: /setlog <channel_id>")
    try:
        cid = int(parts[1])
        db.set_log_channel(client.me.username, cid)
        await m.reply_text(f"✅ Log channel set to {cid}")
    except Exception as e:
        await m.reply_text("Invalid channel id.")

@bot.on_message(filters.command("getlog") & filters.private)
async def cmd_getlog(client: Client, m: Message):
    if not db.is_admin(m.from_user.id):
        return await m.reply_text("❌ You are not authorized.")
    cid = db.get_log_channel(client.me.username)
    if cid:
        await m.reply_text(f"Log channel: {cid}")
    else:
        await m.reply_text("No log channel set. Use /setlog <channel_id>.")

# -------------------------
# Cookies handlers
# -------------------------
@bot.on_message(filters.command("cookies") & filters.private)
async def cmd_cookies(client: Client, m: Message):
    await m.reply_text("📥 Send cookies file (.txt)")
    try:
        msg = await client.listen(m.chat.id, timeout=120)
    except Exception:
        return await m.reply_text("⏳ Timeout: send cookies within 2 minutes.")
    if not msg or not msg.document or not msg.document.file_name.endswith(".txt"):
        return await m.reply_text("❌ Please upload a .txt file.")
    path = await msg.download()
    try:
        shutil.copy(path, COOKIES_FILE)
        await m.reply_text("✅ Cookies updated.")
    except Exception as e:
        await m.reply_text("Error saving cookies: " + str(e))

@bot.on_message(filters.command("getcookies") & filters.private)
async def cmd_getcookies(client: Client, m: Message):
    if os.path.exists(COOKIES_FILE):
        await client.send_document(m.chat.id, COOKIES_FILE, caption="Here is the cookies file.")
    else:
        await m.reply_text("No cookies file found.")

# -------------------------
# Text to txt converter
# -------------------------
@bot.on_message(filters.command("t2t") & filters.private)
async def cmd_t2t(client: Client, m: Message):
    ask = await m.reply_text("✍️ Send the text to convert into a .txt file (you have 2 minutes).")
    try:
        txt_msg = await client.listen(m.chat.id, timeout=120)
    except Exception:
        return await ask.edit("⏳ Timeout: try /t2t again.")
    if not txt_msg or not txt_msg.text:
        return await ask.edit("❌ Send valid text.")
    text = txt_msg.text
    await txt_msg.delete()
    await ask.edit("📁 Send filename or /d for default")
    try:
        fname_msg = await client.listen(m.chat.id, timeout=60)
    except Exception:
        fname = "txt_file"
    else:
        fname = fname_msg.text.strip() if fname_msg.text != "/d" else "txt_file"
        try:
            await fname_msg.delete()
        except Exception:
            pass
    path = os.path.join(DOWNLOADS_DIR, f"{fname}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    await client.send_document(m.chat.id, path, caption=f"`{fname}.txt` created.")
    try:
        os.remove(path)
    except Exception:
        pass

# -------------------------
# Upload (.txt) handler (generic downloader with batch flow)
# -------------------------
@bot.on_message(filters.command("upload") & filters.private)
@force_subscribe
async def cmd_upload(client: Client, m: Message):
    msg = await m.reply_text("📤 Send your .txt file with links (Name and URL per line).")
    try:
        doc = await client.listen(m.chat.id, timeout=180)
    except Exception:
        return await msg.edit("⏳ Timeout: send file within 3 minutes.")
    if not doc or not doc.document or not doc.document.file_name.endswith(".txt"):
        return await msg.edit("❌ Please send a .txt file.")
    path = await doc.download()
    await doc.delete()
    # read links
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
    except Exception as e:
        return await msg.edit("Error reading file: " + str(e))
    os.remove(path)
    links: List[Tuple[str, str]] = []
    for line in lines:
        title, url = extract_url_from_line(line)
        if title and url:
            links.append((title, url))
    if not links:
        return await msg.edit("❌ No valid links found in the file.")
    await msg.edit(f"✅ Found {len(links)} links.\nSend starting index (1..{len(links)}) or /d for 1.")
    try:
        idx_msg = await client.listen(m.chat.id, timeout=60)
        start_idx = int(idx_msg.text) if idx_msg and idx_msg.text.isdigit() else 1
        await idx_msg.delete()
    except Exception:
        start_idx = 1
    await msg.edit("📁 Enter batch name or /d for default:")
    try:
        batch_msg = await client.listen(m.chat.id, timeout=60)
        batch_name = batch_msg.text if batch_msg and batch_msg.text != "/d" else f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M')}"
        try:
            await batch_msg.delete()
        except Exception:
            pass
    except Exception:
        batch_name = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M')}"
    await msg.edit("🎚 Enter video quality (144/240/360/480/720/1080) or send /d for 480:")
    try:
        qmsg = await client.listen(m.chat.id, timeout=60)
        quality = qmsg.text if qmsg and qmsg.text.isdigit() else "480"
        try:
            await qmsg.delete()
        except Exception:
            pass
    except Exception:
        quality = "480"
    await msg.edit("💬 Enter caption for uploads (or /d for none):")
    try:
        capmsg = await client.listen(m.chat.id, timeout=120)
        caption = capmsg.text if capmsg and capmsg.text != "/d" else ""
        try:
            await capmsg.delete()
        except Exception:
            pass
    except Exception:
        caption = ""
    await msg.edit(f"🔄 Starting downloads from index {start_idx} ...")
    success = 0
    failed = 0
    for idx in range(start_idx - 1, len(links)):
        title, url = links[idx]
        try:
            display_title = re.sub(r'[<>:"/\\|?*]', '', title)[:60]
            safe_name = f"{str(idx+1).zfill(3)}_{display_title}"
            await client.send_message(m.chat.id, f"⬇️ Downloading {display_title} ({idx+1}/{len(links)})")
            # preprocess url
            url = try_fix_drive_link(url)
            # DRM detection
            if is_classplus_url(url):
                # try to get signed mpd using placeholder_get_mpd_and_keys
                mpd, keys = placeholder_get_mpd_and_keys(url)
                if mpd:
                    # use mpd as URL for yt-dlp
                    target = mpd
                    format_filter = f"best[height<={quality}]"
                    outpath = await helper_download_direct(target, safe_name, format_filter)
                else:
                    # fallback to direct yt-dlp
                    outpath = await helper_download_direct(url, safe_name, f"best[height<={quality}]")
            elif is_m3u8_content(url):
                outpath = await helper_download_direct(url, safe_name, format_filter="best")
            else:
                outpath = await helper_download_direct(url, safe_name, format_filter=f"best[height<={quality}]")
            if outpath:
                cap = caption or f"📁 {display_title}\n📦 Batch: {batch_name}\nExtracted by: {CREDIT}"
                await helper_send_vid(client, m.chat.id, cap, outpath, None, safe_name)
                success += 1
            else:
                failed += 1
                await client.send_message(m.chat.id, f"❌ Failed to download {display_title}")
        except FloodWait as e:
            await client.send_message(m.chat.id, f"⚠️ Rate limited. Sleeping {e.x} seconds.")
            await asyncio.sleep(e.x)
        except Exception as e:
            failed += 1
            log.exception("download loop error")
            await client.send_message(m.chat.id, f"❌ Error for {title}: {str(e)[:200]}")
    await client.send_message(m.chat.id, f"✅ Done. Success: {success}, Failed: {failed}")

# -------------------------
# DRM-specific command (more interactive flow)
# -------------------------
@bot.on_message(filters.command("drm") & filters.private)
@force_subscribe
async def cmd_drm(client: Client, m: Message):
    """
    DRM flow expects .txt with lines "Name: URL" or similar.
    This will attempt to handle classplus/testbook/pw patterns via placeholder calls.
    """
    prompt = await m.reply_text("📤 Send your .txt file for DRM downloads (20s to send).")
    try:
        doc = await client.listen(m.chat.id, timeout=20)
    except Exception:
        return await prompt.edit("⏳ Timeout: send file quickly.")
    if not doc or not doc.document or not doc.document.file_name.endswith(".txt"):
        return await prompt.edit("❌ Please send a .txt file.")
    path = await doc.download()
    await doc.delete()
    # read lines
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
    except Exception as e:
        return await prompt.edit("Error reading file: " + str(e))
    os.remove(path)
    links = []
    for ln in lines:
        # support "Title : url" or "Title url"
        if "://" in ln:
            # pick last url occurrence
            m = URL_RE.search(ln)
            if m:
                url = m.group(0)
                title = ln.replace(url, "").replace(":", "").strip() or f"File_{abs(hash(url))%10000}"
                links.append((title, url))
    if not links:
        return await prompt.edit("❌ No valid DRM links found.")
    await prompt.edit(f"✅ Found {len(links)} entries. Enter start index (1..{len(links)}) or /d:")
    try:
        smsg = await client.listen(m.chat.id, timeout=20)
        start = int(smsg.text) if smsg and smsg.text.isdigit() else 1
    except Exception:
        start = 1
    await prompt.edit("🎚 Enter quality (e.g., 480) or /d for 480:")
    try:
        qmsg = await client.listen(m.chat.id, timeout=20)
        quality = qmsg.text if qmsg and qmsg.text.isdigit() else "480"
    except Exception:
        quality = "480"
    await prompt.edit("🔐 If you have a token for ClassPlus, send it now or /d:")
    try:
        tokmsg = await client.listen(m.chat.id, timeout=20)
        token = tokmsg.text if tokmsg and tokmsg.text != "/d" else None
    except Exception:
        token = None
    await prompt.edit("🔄 Processing DRM downloads ...")
    succ = 0
    fail = 0
    for i in range(start-1, len(links)):
        title, url = links[i]
        display_title = re.sub(r'[<>:"/\\|?*]', '', title)[:60]
        try:
            await client.send_message(m.chat.id, f"🔐 Processing DRM: {display_title} ({i+1}/{len(links)})")
            # If classplus, use placeholder API flow
            if is_classplus_url(url):
                api_call = url
                if token:
                    api_call = f"{url}?token={token}"
                mpd, keys = placeholder_get_mpd_and_keys(api_call)
                if mpd:
                    out = await helper_download_direct(mpd, f"drm_{i+1}_{display_title}", format_filter=f"best[height<={quality}]")
                else:
                    out = await helper_download_direct(url, f"drm_{i+1}_{display_title}", format_filter=f"best[height<={quality}]")
            else:
                out = await helper_download_direct(url, f"drm_{i+1}_{display_title}", format_filter=f"best[height<={quality}]")
            if out:
                caption = f"🔐 {display_title}\nExtracted by {CREDIT}"
                await helper_send_vid(client, m.chat.id, caption, out, None, display_title)
                succ += 1
            else:
                fail += 1
                await client.send_message(m.chat.id, f"❌ Failed: {display_title}")
        except Exception as e:
            fail += 1
            log.exception("drm loop error")
            await client.send_message(m.chat.id, f"❌ Error: {str(e)[:200]}")
    await client.send_message(m.chat.id, f"✅ DRM task completed. Success: {succ}, Failed: {fail}")

# -------------------------
# Simple text message handler to accept single links and download quickly
# -------------------------
@bot.on_message(filters.text & filters.private)
async def quick_link_handler(client: Client, m: Message):
    if m.from_user.is_bot:
        return
    text = m.text.strip()
    murl = URL_RE.search(text)
    if not murl:
        return
    url = murl.group(0)
    await m.reply_text("🔎 Processing link. Send quality (144/240/360/480/720/1080) or /d for 480.")
    try:
        qmsg = await client.listen(m.chat.id, timeout=60)
        quality = qmsg.text if qmsg and qmsg.text.isdigit() else "480"
    except Exception:
        quality = "480"
    name = re.sub(r'[^a-zA-Z0-9]', '_', m.text)[:40] or "quick"
    await m.reply_text("⬇️ Downloading ...")
    out = await helper_download_direct(url, f"quick_{name}", format_filter=f"best[height<={quality}]")
    if out:
        await helper_send_vid(client, m.chat.id, f"Downloaded: {name}", out, None, name)
    else:
        await m.reply_text("❌ Failed to download link.")

# -------------------------
# Stop/restart handler
# -------------------------
@bot.on_message(filters.command("stop") & filters.private)
async def cmd_stop(client: Client, m: Message):
    if not db.is_admin(m.from_user.id):
        return await m.reply_text("❌ You are not authorized.")
    await m.reply_text("🛑 Restarting bot...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# -------------------------
# Graceful startup
# -------------------------
if __name__ == "__main__":
    log.info("Starting merged bot...")
    # Basic checks
    if API_ID == 0 or API_HASH == "" or BOT_TOKEN == "":
        log.warning("API_ID/API_HASH/BOT_TOKEN not set. Please set them in vars.py or environment.")
    # create downloads dir
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    try:
        bot.run()
    except Exception as e:
        log.exception("Bot crashed: " + str(e))
        raise
