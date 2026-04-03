#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║ KENSHIN ANIME BOT — by @kenshin_anime                ║
║ Framework : Pyrofork (Pyrogram fork)                 ║
║ Features  : Full Thumbnail Gen + HD Caption + Fixes  ║
╚══════════════════════════════════════════════════════╝
"""
import os, io, asyncio, logging
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

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

LOGO_PATH = "logo.png"
FONT_DIR  = "/fonts"

# ── Pyrogram client ────────────────────────────────────
app = Client(
    "kenshin_anime_bot",
    api_id   = API_ID,
    api_hash = API_HASH,
    bot_token= BOT_TOKEN,
)

# ── Conversation state storage (in-memory) ─────────────
STATES: dict = {}
STATE_ANIME  = "await_anime"
STATE_POSTER = "await_poster"
STATE_LOGO   = "await_logo"

# ── Unicode math bold digit converter ──────────────────
_BOLD_DIGITS = "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"
def bold_num(s: str) -> str:
    return "".join(_BOLD_DIGITS[int(c)] if c.isdigit() else c for c in str(s))

# ── Admin check ────────────────────────────────────────
def is_admin(uid: int) -> bool:
    return not ADMIN_IDS or uid in ADMIN_IDS

# ── Genre → accent color ───────────────────────────────
GENRE_COLORS = {
    "ACTION":       (190,  20,  20),
    "HORROR":       (110,   0,   0),
    "SUPERNATURAL": ( 90,   0, 160),
    "MYSTERY":      ( 20,  30, 130),
    "SCI-FI":       ( 10, 110, 210),
    "SCIENCE":      ( 10, 110, 210),
    "FANTASY":      (110,  30, 210),
    "ROMANCE":      (210,  30, 130),
    "COMEDY":       (200, 140,   0),
    "SPORTS":       ( 20, 155,  60),
    "ADVENTURE":    (210,  80,  10),
    "DRAMA":        ( 10, 130, 110),
}

def accent_color(genres: list) -> tuple:
    for g in genres:
        for key, col in GENRE_COLORS.items():
            if key in g.upper():
                return col
    return (190, 20, 20)

# ════════════════════════════════════════════════════════
# JIKAN API WITH ANTI-BLOCK HEADERS
# ════════════════════════════════════════════════════════
JIKAN = "https://api.jikan.moe/v4"

async def jikan_search(name: str) -> dict | None:
    headers = {"User-Agent": "KenshinAnimeBot/1.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            # Try Anime First
            async with session.get(f"{JIKAN}/anime", params={"q": name, "limit": 1}, timeout=10) as r:
                if r.status == 200:
                    d = await r.json()
                    if d.get("data"):
                        return _parse_anime(d["data"][0], kind="Anime")
        except Exception as e:
            log.error(f"Jikan Anime API error: {e}")

        await asyncio.sleep(0.5)

        try:
            # Try Manga Next
            async with session.get(f"{JIKAN}/manga", params={"q": name, "limit": 1}, timeout=10) as r:
                if r.status == 200:
                    d = await r.json()
                    if d.get("data"):
                        return _parse_manga(d["data"][0])
        except Exception as e:
            log.error(f"Jikan Manga API error: {e}")
            
    return None

def _pad_genres(genres: list, n: int = 3) -> list:
    pads = ["ANIME", "DRAMA", "ADVENTURE", "ACTION", "MYSTERY"]
    while len(genres) < n:
        genres.append(pads[len(genres) % len(pads)])
    return genres[:n]

def _parse_anime(a: dict, kind: str = "Anime") -> dict:
    genres = [g["name"] for g in a.get("genres", [])]
    studios= [s["name"] for s in a.get("studios", [])]
    title  = a.get("title_english") or a.get("title") or "Unknown"
    return {
        "kind":      kind,
        "title":     title,
        "genres":    genres,
        "genres3":   _pad_genres(genres.copy()),
        "score":     str(a.get("score") or "?"),
        "synopsis":  (a.get("synopsis") or "").replace("[Written by MAL Rewrite]", "").strip(),
        "episodes":  str(a.get("episodes") or "?"),
        "season":    str(a.get("season") or "1").title(),
        "runtime":   str(a.get("duration", "Unknown")),
        "status":    str(a.get("status", "Unknown")),
        "studios":   studios,
        "thumb_url": a.get("images", {}).get("jpg", {}).get("large_image_url") or "",
    }

def _parse_manga(m: dict) -> dict:
    genres = [g["name"] for g in m.get("genres", [])]
    mtype  = (m.get("type") or "Manga").title()
    if "manhwa" in (m.get("demographics") or []) or m.get("status", "").lower().endswith("manhwa"):
        mtype = "Manhwa"
    title  = m.get("title_english") or m.get("title") or "Unknown"
    return {
        "kind":      mtype,
        "title":     title,
        "genres":    genres,
        "genres3":   _pad_genres(genres.copy()),
        "score":     str(m.get("score") or "?"),
        "synopsis":  (m.get("synopsis") or "").replace("[Written by MAL Rewrite]", "").strip(),
        "episodes":  str(m.get("chapters") or "?"),
        "season":    str(m.get("volumes") or "1"),
        "runtime":   "N/A",
        "status":    str(m.get("status", "Unknown")),
        "studios":   [m.get("authors", [{}])[0].get("name", "Unknown")] if m.get("authors") else [],
        "thumb_url": m.get("images", {}).get("jpg", {}).get("large_image_url") or "",
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
# THUMBNAIL GENERATOR (YOUR FULL ORIGINAL CODE)
# ════════════════════════════════════════════════════════
def get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, name)
    for p in [path, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def cover_fit(img: Image.Image, w: int, h: int) -> Image.Image:
    iw, ih = img.size
    sc = max(w / iw, h / ih)
    nw, nh = int(iw * sc), int(ih * sc)
    img = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw - w) // 2, (nh - h) // 2, (nw - w) // 2 + w, (nh - h) // 2 + h))

def wrap_text(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) > max_w and cur:
            lines.append(cur); cur = w
        else:
            cur = test
    if cur: lines.append(cur)
    return lines

def rr(draw, x, y, w, h, r, fill=None, outline=None, lw=1):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=fill, outline=outline, width=lw)

def draw_logo(canvas, x, y, s):
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA").resize((s, s), Image.LANCZOS)
            mask = Image.new("L", (s, s), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0,0,s,s], radius=s//7, fill=255)
            logo.putalpha(mask)
            canvas.paste(logo, (x, y), logo)
            return
        except Exception:
            pass
    # Built-in fallback
    d = ImageDraw.Draw(canvas)
    rr(d, x, y, s, s, s//7, fill=(6,13,32), outline=(40,100,220), lw=2)
    fk = get_font("Oswald-Bold.ttf", s//5)
    fa = get_font("Oswald-Bold.ttf", s//6)
    d.text((x+s//2, y+s*72//100), "KENSHIN", font=fk, fill=(255,255,255), anchor="mm")
    d.text((x+s//2, y+s*88//100), "ANIME", font=fa, fill=(79,159,255), anchor="mm")

def make_fade(pw, h):
    fade = Image.new("RGBA", (110, h), (0,0,0,0))
    fd = ImageDraw.Draw(fade)
    for i in range(110):
        a = int((i/110)**1.6 * 255)
        fd.rectangle([i,0,i+1,h], fill=(0,0,0,a))
    return fade

def generate_thumbnail(poster_bytes: bytes, anime: dict) -> bytes:
    W, H = 1280, 720
    canvas = Image.new("RGB", (W, H), (0,0,0))
    title = anime["title"].upper()
    genres3 = anime["genres3"]
    synopsis= anime["synopsis"].upper()
    score = anime["score"]
    ac = accent_color(genres3)

    # Left poster
    PW = 480
    poster = Image.open(io.BytesIO(poster_bytes)).convert("RGB")
    poster = cover_fit(poster, PW, H)
    canvas.paste(poster, (0,0))
    
    # Tint
    tint = Image.new("RGBA", (PW, H), (*ac, 55))
    tmp = canvas.convert("RGBA"); tmp.paste(tint,(0,0),tint); canvas=tmp.convert("RGB")
    
    # Fade
    fade = make_fade(PW, H)
    tmp = canvas.convert("RGBA"); tmp.paste(fade,(PW-110,0),fade); canvas=tmp.convert("RGB")
    
    draw = ImageDraw.Draw(canvas)
    RX = 504
    RW = W - RX - 16
    LS = 88
    LY = 16
    draw_logo(canvas, RX, LY, LS)
    
    draw = ImageDraw.Draw(canvas)
    f36 = get_font("Oswald-Bold.ttf", 36)
    f17 = get_font("Oswald-Regular.ttf", 17)
    f18 = get_font("Oswald-Bold.ttf", 18)
    f14 = get_font("Oswald-Regular.ttf", 14)
    f_join = get_font("Oswald-Bold.ttf", 17)
    
    NX = RX + LS + 14
    draw.text((NX, LY+8), "KENSHIN", font=f36, fill=(255,255,255))
    draw.text((NX, LY+50), "ANIME", font=f36, fill=(255,45,154))
    
    jW = int(draw.textlength("JOIN NOW", font=f_join)) + 38
    jH = 42; jX = W-18-jW; jY = LY+LS//2-jH//2
    rr(draw, jX, jY, jW, jH, jH//2, outline=(255,255,255), lw=2)
    draw.text((jX+jW//2, jY+jH//2), "JOIN NOW", font=f_join, fill=(255,255,255), anchor="mm")
    
    CY = LY + LS + 22
    fs = 64
    f_t= get_font("Oswald-Bold.ttf", fs)
    while draw.textlength(title, font=f_t) > RW and fs > 36:
        fs -= 3; f_t = get_font("Oswald-Bold.ttf", fs)
        
    for ln in wrap_text(draw, title, f_t, RW)[:2]:
        draw.text((RX, CY), ln, font=f_t, fill=(255,255,255))
        CY += int(fs * 1.17)
        
    CY += 10
    draw.line([(RX,CY),(W-18,CY)], fill=(255,255,255), width=2); CY+=14
    
    if len(synopsis)>490: synopsis=synopsis[:487]+"..."
    syn_lines = wrap_text(draw, synopsis, f17, RW-44)
    lh=24; max_sl=9; vis=min(len(syn_lines),max_sl)
    bh = vis*lh+38
    rr(draw, RX, CY, RW, bh, 13, fill=(72,72,72))
    
    sy=CY+19; cx=RX+RW//2
    for i in range(vis):
        ln=syn_lines[i]
        if i==vis-1 and len(syn_lines)>max_sl:
            while draw.textlength(ln+"...", font=f17)>RW-44 and ln:
                ln=ln.rsplit(" ",1)[0]
            ln+="..."
        draw.text((cx,sy), ln, font=f17, fill=(255,255,255), anchor="mt"); sy+=lh
        
    CY += bh+20
    g_txt = " ".join(genres3)
    gW = int(draw.textlength(g_txt, font=f18))+44; gH=46
    rr(draw, RX, CY, gW, gH, gH//2, fill=(72,72,72))
    draw.text((RX+gW//2, CY+gH//2), g_txt, font=f18, fill=(255,255,255), anchor="mm")
    
    s_txt = f"☆☆☆☆☆ {score}/10"
    sW = int(draw.textlength(s_txt, font=f18))+44; sX=RX+gW+16
    rr(draw, sX, CY, sW, gH, gH//2, fill=(72,72,72))
    draw.text((sX+sW//2, CY+gH//2), s_txt, font=f18, fill=(255,255,255), anchor="mm")
    
    draw.line([(RX,H-50),(W-18,H-50)], fill=(180,180,180,90), width=1)
    draw.text((RX,H-36), "KENSHIN ANIME'S THE PLACE FOR EVERY ANIME WATCHER", font=f14, fill=(255,255,255))
    
    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf.read()

# ════════════════════════════════════════════════════════
# BOT COMMAND HANDLERS
# ════════════════════════════════════════════════════════
@app.on_message(filters.command("start") & filters.private)
async def cmd_start(_, msg: Message):
    if not is_admin(msg.from_user.id): return
    await msg.reply_text(
        "🎌 <b>KENSHIN ANIME BOT</b>\n\n"
        "📋 <b>Commands:</b>\n"
        "• /help — Full command guide\n"
        "• /info anime name — Get anime/manga info\n"
        "• /thumb — Generate HD thumbnail & caption\n"
        "• /setlogo — Upload channel logo\n"
        "• /cancel — Cancel current operation",
        parse_mode=ParseMode.HTML,
    )

@app.on_message(filters.command("help") & filters.private)
async def cmd_help(_, msg: Message):
    if not is_admin(msg.from_user.id): return
    await msg.reply_text(
        "📖 <b>KENSHIN ANIME BOT — Help</b>\n\n"
        "ℹ️ <b>Info:</b> /info <name>\n"
        "🎨 <b>Thumbnail:</b> /thumb\n"
        "📺 <b>Logo:</b> /setlogo\n"
        "❌ <b>Cancel:</b> /cancel",
        parse_mode=ParseMode.HTML,
    )

@app.on_message(filters.command("info") & filters.private)
async def cmd_info(_, msg: Message):
    if not is_admin(msg.from_user.id): return
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply_text("⚠️ Usage: <code>/info Anime Name Here</code>", parse_mode=ParseMode.HTML)
        
    name = parts[1].strip()
    wait_msg = await msg.reply_text(f"🔍 Searching for <b>{name}</b>...", parse_mode=ParseMode.HTML)
    await app.send_chat_action(msg.chat.id, "upload_photo")
    
    try:
        anime = await jikan_search(name)
        if not anime:
            return await wait_msg.edit_text(f"❌ <b>{name}</b> not found.", parse_mode=ParseMode.HTML)
            
        caption = build_info_caption(anime)
        thumb_url = anime.get("thumb_url", "")
        
        if thumb_url:
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(thumb_url, timeout=15) as r:
                        img_bytes = await r.read()
                await msg.reply_photo(photo=io.BytesIO(img_bytes), caption=caption, parse_mode=ParseMode.HTML)
                return await wait_msg.delete()
            except Exception as e:
                log.warning(f"Poster download failed: {e}")
                
        await wait_msg.edit_text(caption, parse_mode=ParseMode.HTML)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Error: {e}")

@app.on_message(filters.command("thumb") & filters.private)
async def cmd_thumb(_, msg: Message):
    if not is_admin(msg.from_user.id): return
    STATES[msg.from_user.id] = {"state": STATE_ANIME, "data": {}}
    await msg.reply_text("🎌 <b>HD Thumbnail Generator</b>\n\n📝 Enter the anime name:", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("setlogo") & filters.private)
async def cmd_setlogo(_, msg: Message):
    if not is_admin(msg.from_user.id): return
    STATES[msg.from_user.id] = {"state": STATE_LOGO, "data": {}}
    await msg.reply_text("📺 <b>Set Channel Logo</b>\n\nSend your logo image now.", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("cancel") & filters.private)
async def cmd_cancel(_, msg: Message):
    if not is_admin(msg.from_user.id): return
    STATES.pop(msg.from_user.id, None)
    await msg.reply_text("❌ Operation cancelled.")

@app.on_message(filters.private & (filters.text | filters.photo | filters.document))
async def handle_message(_, msg: Message):
    uid = msg.from_user.id
    if not is_admin(uid): return
    if msg.text and msg.text.startswith("/"): return

    state_data = STATES.get(uid)
    if not state_data:
        return await msg.reply_text("👋 Send /thumb to generate a thumbnail or /info anime name.")

    state = state_data["state"]

    if state == STATE_ANIME:
        if not msg.text: return await msg.reply_text("⚠️ Please send the anime name as text.")
            
        name = msg.text.strip()
        wait_msg = await msg.reply_text(f"🔍 Fetching info for <b>{name}</b>...", parse_mode=ParseMode.HTML)
        anime = await jikan_search(name)
        
        if not anime:
            STATES.pop(uid, None)
            return await wait_msg.edit_text(f"❌ <b>{name}</b> not found.", parse_mode=ParseMode.HTML)
            
        STATES[uid] = {"state": STATE_POSTER, "data": {"anime": anime}}
        genres_str = " | ".join(anime["genres3"])
        await wait_msg.edit_text(
            f"✅ Found: <b>{anime['title']}</b>\n"
            f"🎭 Genres: {genres_str}\n"
            f"⭐ Score: {anime['score']}/10\n\n"
            f"📸 <b>Now send the anime poster image:</b>",
            parse_mode=ParseMode.HTML,
        )

    elif state == STATE_POSTER:
        if not msg.photo and not msg.document:
            return await msg.reply_text("⚠️ Please send an image (photo).")
            
        wait_msg = await msg.reply_text("⚙️ Generating HD thumbnail... Please wait!")
        await app.send_chat_action(msg.chat.id, "upload_photo")
        
        try:
            file = await (msg.photo[-1] if msg.photo else msg.document).get_file()
            poster_bytes = bytes(await file.download_as_bytearray())
            anime = STATES[uid]["data"]["anime"]
            
            # Use original advanced generator
            thumb_bytes = await asyncio.to_thread(generate_thumbnail, poster_bytes, anime)
            
            # Use new custom caption
            caption = build_info_caption(anime)
            
            await wait_msg.delete()
            await msg.reply_photo(
                photo=io.BytesIO(thumb_bytes),
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            log.error(f"Thumb generate error: {e}")
            await wait_msg.edit_text(f"❌ Error: {e}")
        finally:
            STATES.pop(uid, None)

    elif state == STATE_LOGO:
        if not msg.photo and not msg.document:
            return await msg.reply_text("⚠️ Please send an image.")
            
        try:
            file = await (msg.photo[-1] if msg.photo else msg.document).get_file()
            await file.download_to_drive(LOGO_PATH)
            await msg.reply_text("✅ Logo saved! Send /thumb to test it.")
        except Exception as e:
            await msg.reply_text(f"❌ Failed to save logo: {e}")
        finally:
            STATES.pop(uid, None)

if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set!")
    if not API_ID or not API_HASH:
        raise ValueError("API_ID and API_HASH environment variables must be set!")
        
    log.info("🎌 Kenshin Anime Bot starting with FULL features...")
    app.run()
