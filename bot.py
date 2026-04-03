#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║ KENSHIN ANIME BOT — by @kenshin_anime                ║
║ Framework : Pyrofork (Pyrogram fork)                 ║
║ Features  : Fast API Fetch + Original Poster Caption ║
╚══════════════════════════════════════════════════════╝
"""
import os, io, asyncio, logging
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode, ChatAction

# ── Logging ────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("KenshinBot")

# ── Config ─────────────────────────────────────────────
API_ID    = int(os.environ.get("API_ID", "0"))
API_HASH  = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = set(
    int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()
)

# ── Pyrogram client ────────────────────────────────────
app = Client(
    "kenshin_anime_bot",
    api_id   = API_ID,
    api_hash = API_HASH,
    bot_token= BOT_TOKEN,
)

# ── Unicode math bold digit converter ──────────────────
_BOLD_DIGITS = "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"
def bold_num(s: str) -> str:
    return "".join(_BOLD_DIGITS[int(c)] if c.isdigit() else c for c in str(s))

def is_admin(uid: int) -> bool:
    return not ADMIN_IDS or uid in ADMIN_IDS

# ════════════════════════════════════════════════════════
# JIKAN API FETCHING
# ════════════════════════════════════════════════════════
JIKAN = "https://api.jikan.moe/v4"

async def jikan_search(name: str) -> dict | None:
    headers = {"User-Agent": "KenshinAnimeBot/2.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            # Search Anime
            async with session.get(f"{JIKAN}/anime", params={"q": name, "limit": 1}, timeout=10) as r:
                if r.status == 200:
                    d = await r.json()
                    if d.get("data"):
                        return _parse_anime(d["data"][0], kind="Anime")
        except Exception as e:
            log.error(f"Jikan Anime API error: {e}")

        await asyncio.sleep(0.5)

        try:
            # Search Manga if Anime not found
            async with session.get(f"{JIKAN}/manga", params={"q": name, "limit": 1}, timeout=10) as r:
                if r.status == 200:
                    d = await r.json()
                    if d.get("data"):
                        return _parse_manga(d["data"][0])
        except Exception as e:
            log.error(f"Jikan Manga API error: {e}")
            
    return None

def _parse_anime(a: dict, kind: str = "Anime") -> dict:
    genres = [g["name"] for g in a.get("genres", [])]
    studios= [s["name"] for s in a.get("studios", [])]
    title  = a.get("title_english") or a.get("title") or "Unknown"
    
    # Ye image URL wo original poster fetch karega jo aapko chahiye
    thumb_url = a.get("images", {}).get("jpg", {}).get("large_image_url") or ""

    return {
        "kind":      kind,
        "title":     title,
        "genres":    genres,
        "score":     str(a.get("score") or "?"),
        "episodes":  str(a.get("episodes") or "?"),
        "season":    str(a.get("season") or "1").title(),
        "runtime":   str(a.get("duration", "Unknown")),
        "status":    str(a.get("status", "Unknown")),
        "studios":   studios,
        "thumb_url": thumb_url
    }

def _parse_manga(m: dict) -> dict:
    genres = [g["name"] for g in m.get("genres", [])]
    mtype  = (m.get("type") or "Manga").title()
    title  = m.get("title_english") or m.get("title") or "Unknown"
    thumb_url = m.get("images", {}).get("jpg", {}).get("large_image_url") or ""

    return {
        "kind":      mtype,
        "title":     title,
        "genres":    genres,
        "score":     str(m.get("score") or "?"),
        "episodes":  str(m.get("chapters") or "?"),
        "season":    str(m.get("volumes") or "1"),
        "runtime":   "N/A",
        "status":    str(m.get("status", "Unknown")),
        "studios":   [m.get("authors", [{}])[0].get("name", "Unknown")] if m.get("authors") else [],
        "thumb_url": thumb_url
    }

def season_str(anime: dict) -> str:
    raw = anime.get("season", "1")
    try:
        return f"{int(raw):02d}"
    except Exception:
        return "01"

# ════════════════════════════════════════════════════════
# CUSTOM CAPTION FORMAT
# ════════════════════════════════════════════════════════
def build_info_caption(anime: dict) -> str:
    title    = anime.get("title", "Unknown").upper()
    category = anime.get("kind", "Anime")
    season   = season_str(anime)
    episodes = anime.get("episodes", "?")
    runtime  = anime.get("runtime", "Unknown").lower()
    rating   = bold_num(anime.get("score", "?"))
    status   = anime.get("status", "Unknown").lower()
    studio   = ", ".join(anime.get("studios", [])).lower() or "unknown"
    genres   = ", ".join(anime.get("genres", [])) or "unknown"
    
    caption = (
        f"<b><blockquote>「 {title} 」</blockquote></b>\n"
        f"<b>═══════════════════</b>\n"
        f"🌸 <b>Category:</b> {category}\n"
        f"🍥 <b>Season:</b> {season}\n"
        f"🧊 <b>Episodes:</b> {episodes}\n"
        f"🍣 <b>Runtime:</b> {runtime}\n"
        f"🍡 <b>Rating:</b> {rating}/𝟷𝟶\n"
        f"🍙 <b>Status:</b> {status}\n"
        f"🍵 <b>Studio:</b> {studio}\n"
        f"🎐 <b>Genres:</b> {genres}\n"
        f"<b>═══════════════════</b>\n"
        f"<b>POWERED BY: [@KENSHIN_ANIME]</b>"
    )
    return caption

# ════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ════════════════════════════════════════════════════════
@app.on_message(filters.command("start") & filters.private)
async def cmd_start(_, msg: Message):
    if not is_admin(msg.from_user.id): return
    await msg.reply_text(
        "🎌 <b>KENSHIN ANIME BOT</b>\n\n"
        "Ready to fetch Anime/Manga!\n"
        "👉 Use: <code>/info anime name</code>",
        parse_mode=ParseMode.HTML,
    )

@app.on_message(filters.command("info") & filters.private)
async def cmd_info(_, msg: Message):
    if not is_admin(msg.from_user.id): return
    
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply_text("⚠️ Usage: <code>/info Anime Name Here</code>", parse_mode=ParseMode.HTML)
        
    name = parts[1].strip()
    wait_msg = await msg.reply_text(f"🔍 Fetching info for <b>{name}</b>...", parse_mode=ParseMode.HTML)
    await app.send_chat_action(msg.chat.id, ChatAction.UPLOAD_PHOTO)
    
    try:
        anime = await jikan_search(name)
        if not anime:
            return await wait_msg.edit_text(f"❌ <b>{name}</b> not found on MyAnimeList.", parse_mode=ParseMode.HTML)
            
        caption = build_info_caption(anime)
        thumb_url = anime.get("thumb_url", "")
        
        # Agar image url milti hai toh image ke saath caption bhejo
        if thumb_url:
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(thumb_url, timeout=15) as r:
                        img_bytes = await r.read()
                        
                await msg.reply_photo(
                    photo=io.BytesIO(img_bytes), 
                    caption=caption, 
                    parse_mode=ParseMode.HTML
                )
                await wait_msg.delete()
                return
            except Exception as e:
                log.warning(f"Image download failed: {e}")
                
        # Agar image fail ho jaye, toh sirf text bhej do
        await wait_msg.edit_text(caption, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        await wait_msg.edit_text(f"❌ Error: {e}")

if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing!")
    if not API_ID or not API_HASH:
        raise ValueError("API_ID and API_HASH are missing!")
        
    log.info("🎌 Fast API Fetcher Bot Started!")
    app.run()
