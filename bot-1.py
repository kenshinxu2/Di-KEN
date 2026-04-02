#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║   KENSHIN ANIME — THUMBNAIL GENERATOR BOT        ║
║   Admin-only | Railway deployment                ║
║   Commands: /start /help /setlogo /cancel        ║
╚══════════════════════════════════════════════════╝
"""

import os, io, logging, requests
from PIL import Image, ImageDraw, ImageFont

from telegram import Update, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters,
)

# ── Logging ─────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_IDS = set(
    int(x.strip()) for x in os.environ.get('ADMIN_IDS', '').split(',') if x.strip()
)
LOGO_PATH  = 'logo.png'
FONT_DIR   = '/fonts'

# ── Conversation states ───────────────────────────────
AWAIT_ANIME  = 1   # waiting for anime name (text)
AWAIT_POSTER = 2   # waiting for poster image
AWAIT_LOGO   = 3   # waiting for logo image (/setlogo flow)

# ── Genre → Accent color map ─────────────────────────
GENRE_COLORS = {
    'ACTION':       (190,  20,  20),
    'HORROR':       (110,   0,   0),
    'SUPERNATURAL': ( 90,   0, 160),
    'MYSTERY':      ( 20,  30, 130),
    'SCI-FI':       ( 10, 110, 210),
    'SCIENCE':      ( 10, 110, 210),
    'FANTASY':      (110,  30, 210),
    'ROMANCE':      (210,  30, 130),
    'COMEDY':       (200, 140,   0),
    'SPORTS':       ( 20, 155,  60),
    'ADVENTURE':    (210,  80,  10),
    'DRAMA':        ( 10, 130, 110),
}

def accent_color(genres: list[str]) -> tuple:
    for g in genres:
        gu = g.upper()
        for key, col in GENRE_COLORS.items():
            if key in gu:
                return col
    return (190, 20, 20)  # default red

# ── Font helper ───────────────────────────────────────
def get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            # fallback system fonts
            for fb in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                       '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf']:
                if os.path.exists(fb):
                    return ImageFont.truetype(fb, size)
        except Exception:
            pass
        return ImageFont.load_default()

# ── Jikan API ─────────────────────────────────────────
def fetch_jikan(name: str) -> dict | None:
    try:
        r = requests.get(
            'https://api.jikan.moe/v4/anime',
            params={'q': name, 'limit': 1},
            timeout=12,
            headers={'User-Agent': 'KenshinAnimeBot/1.0'}
        )
        data = r.json().get('data', [])
        if not data:
            return None
        a = data[0]
        genres = [g['name'].upper() for g in a.get('genres', [])]
        # Pad to exactly 3
        defaults = ['ANIME', 'DRAMA', 'ADVENTURE']
        while len(genres) < 3:
            genres.append(defaults[len(genres)])
        genres = genres[:3]
        return {
            'title':    (a.get('title_english') or a.get('title') or name).upper(),
            'genres':   genres,
            'synopsis': (a.get('synopsis') or '').replace('[Written by MAL Rewrite]', '').strip().upper(),
            'score':    str(a.get('score') or '?'),
        }
    except Exception as e:
        log.error(f'Jikan fetch error: {e}')
        return None

# ── Drawing helpers ────────────────────────────────────
def cover_fit(img: Image.Image, w: int, h: int) -> Image.Image:
    iw, ih = img.size
    scale  = max(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img    = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw - w) // 2, (nh - h) // 2, (nw - w) // 2 + w, (nh - h) // 2 + h))

def wrap_text(draw: ImageDraw.Draw, text: str, font, max_w: int) -> list[str]:
    words  = text.split()
    lines, cur = [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if draw.textlength(test, font=font) > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines

def rounded_rect(draw: ImageDraw.Draw, x, y, w, h, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=fill, outline=outline, width=width)

def make_fade_overlay(pw: int, h: int) -> Image.Image:
    """Black gradient overlay for right edge of poster."""
    fade = Image.new('RGBA', (110, h), (0, 0, 0, 0))
    fd   = ImageDraw.Draw(fade)
    for i in range(110):
        alpha = int((i / 110) ** 1.6 * 255)
        fd.rectangle([i, 0, i + 1, h], fill=(0, 0, 0, alpha))
    return fade

def draw_builtin_logo(canvas: Image.Image, x: int, y: int, size: int):
    """Fallback built-in Kenshin Anime style logo."""
    draw = ImageDraw.Draw(canvas)
    rounded_rect(draw, x, y, size, size, size // 7, fill=(6, 13, 32))
    rounded_rect(draw, x, y, size, size, size // 7, outline=(40, 100, 220), width=2)
    f_k = get_font('Oswald-Bold.ttf', size // 5)
    f_a = get_font('Oswald-Bold.ttf', size // 6)
    draw.text((x + size // 2, y + size * 72 // 100), 'KENSHIN', font=f_k, fill=(255, 255, 255), anchor='mm')
    draw.text((x + size // 2, y + size * 88 // 100), 'ANIME',   font=f_a, fill=(79,  159, 255), anchor='mm')

def draw_logo(canvas: Image.Image, x: int, y: int, size: int):
    """Draw the channel logo (real or built-in)."""
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert('RGBA').resize((size, size), Image.LANCZOS)
            mask = Image.new('L', (size, size), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius=size // 7, fill=255)
            logo.putalpha(mask)
            canvas.paste(logo, (x, y), logo)
            return
        except Exception:
            pass
    draw_builtin_logo(canvas, x, y, size)

# ════════════════════════════════════════════════════
#              MAIN THUMBNAIL GENERATOR
# ════════════════════════════════════════════════════
def generate_thumbnail(poster_bytes: bytes, anime: dict) -> bytes:
    W, H = 1280, 720
    canvas = Image.new('RGB', (W, H), (0, 0, 0))

    title    = anime['title']
    genres   = anime['genres']   # exactly 3
    synopsis = anime['synopsis']
    score    = anime['score']
    ac       = accent_color(genres)

    # ── Left poster (480px wide) ─────────────────
    PW = 480
    poster = Image.open(io.BytesIO(poster_bytes)).convert('RGB')
    poster = cover_fit(poster, PW, H)
    canvas.paste(poster, (0, 0))

    # Genre tint overlay on left
    tint = Image.new('RGBA', (PW, H), (*ac, 55))
    tmp  = canvas.convert('RGBA')
    tmp.paste(tint, (0, 0), tint)
    canvas = tmp.convert('RGB')

    # Right black fade
    fade = make_fade_overlay(PW, H)
    tmp  = canvas.convert('RGBA')
    tmp.paste(fade, (PW - 110, 0), fade)
    canvas = tmp.convert('RGB')

    draw = ImageDraw.Draw(canvas)

    # Fonts
    f_kenshin  = get_font('Oswald-Bold.ttf', 38)
    f_join     = get_font('Oswald-Bold.ttf', 17)
    f_synopsis = get_font('Oswald-Regular.ttf', 17)
    f_genre    = get_font('Oswald-Bold.ttf', 18)
    f_tagline  = get_font('Oswald-Regular.ttf', 14)

    # ── Header row ────────────────────────────────
    RX = 504       # right content start x
    RW = W - RX - 16   # ~760px
    LS = 88        # logo size
    LY = 16

    draw_logo(canvas, RX, LY, LS)
    draw = ImageDraw.Draw(canvas)   # re-create after paste

    NX = RX + LS + 14
    draw.text((NX, LY + 8),  'KENSHIN', font=f_kenshin, fill=(255, 255, 255))
    draw.text((NX, LY + 50), 'ANIME',   font=f_kenshin, fill=(255,  45, 154))

    # JOIN NOW pill
    jTxt = 'JOIN NOW'
    jW   = int(draw.textlength(jTxt, font=f_join)) + 38
    jH   = 42
    jX   = W - 18 - jW
    jY   = LY + LS // 2 - jH // 2
    rounded_rect(draw, jX, jY, jW, jH, jH // 2, outline=(255, 255, 255), width=2)
    draw.text((jX + jW // 2, jY + jH // 2), jTxt, font=f_join, fill=(255, 255, 255), anchor='mm')

    # ── Title ─────────────────────────────────────
    CY = LY + LS + 22
    fs = 64
    f_title = get_font('Oswald-Bold.ttf', fs)
    while draw.textlength(title, font=f_title) > RW and fs > 36:
        fs -= 3
        f_title = get_font('Oswald-Bold.ttf', fs)
    title_lines = wrap_text(draw, title, f_title, RW)
    for i, ln in enumerate(title_lines[:2]):
        draw.text((RX, CY), ln, font=f_title, fill=(255, 255, 255))
        CY += int(fs * 1.17)
    CY += 10

    # ── Separator line under title ─────────────────
    draw.line([(RX, CY), (W - 18, CY)], fill=(255, 255, 255), width=2)
    CY += 14

    # ── Synopsis box ──────────────────────────────
    if len(synopsis) > 490:
        synopsis = synopsis[:487] + '...'

    syn_lines = wrap_text(draw, synopsis, f_synopsis, RW - 44)
    lh = 24
    max_syn_l = 9
    vis_l = min(len(syn_lines), max_syn_l)
    box_h = vis_l * lh + 38
    box_w = RW

    rounded_rect(draw, RX, CY, box_w, box_h, 13, fill=(72, 72, 72, 140))

    sy = CY + 19
    cx_syn = RX + box_w // 2
    for i in range(vis_l):
        ln = syn_lines[i]
        if i == vis_l - 1 and len(syn_lines) > max_syn_l:
            # Trim and add ellipsis
            while draw.textlength(ln + '...', font=f_synopsis) > RW - 44 and ln:
                ln = ln.rsplit(' ', 1)[0]
            ln = ln + '...'
        draw.text((cx_syn, sy), ln, font=f_synopsis, fill=(255, 255, 255), anchor='mt')
        sy += lh
    CY += box_h + 20

    # ── Genre pill + Score pill ────────────────────
    g_txt = '  '.join(genres)
    gW    = int(draw.textlength(g_txt, font=f_genre)) + 44
    gH    = 46
    rounded_rect(draw, RX, CY, gW, gH, gH // 2, fill=(72, 72, 72))
    draw.text((RX + gW // 2, CY + gH // 2), g_txt, font=f_genre, fill=(255, 255, 255), anchor='mm')

    s_txt = f'\u2606\u2606\u2606\u2606\u2606 {score}/10'   # ☆☆☆☆☆
    sW    = int(draw.textlength(s_txt, font=f_genre)) + 44
    sX    = RX + gW + 16
    rounded_rect(draw, sX, CY, sW, gH, gH // 2, fill=(72, 72, 72))
    draw.text((sX + sW // 2, CY + gH // 2), s_txt, font=f_genre, fill=(255, 255, 255), anchor='mm')

    # ── Bottom separator + tagline ─────────────────
    draw.line([(RX, H - 50), (W - 18, H - 50)], fill=(200, 200, 200, 90), width=1)
    tagline = "KENSHIN ANIME'S THE PLACE FOR EVERY ANIME WATCHER"
    draw.text((RX, H - 36), tagline, font=f_tagline, fill=(255, 255, 255))

    # ── Export PNG ────────────────────────────────
    buf = io.BytesIO()
    canvas.save(buf, 'PNG', optimize=True)
    buf.seek(0)
    return buf.read()

# ════════════════════════════════════════════════════
#                  BOT HANDLERS
# ════════════════════════════════════════════════════
def is_admin(update: Update) -> bool:
    uid = update.effective_user.id
    if not ADMIN_IDS:
        return True  # No restriction if ADMIN_IDS not set
    return uid in ADMIN_IDS

def admin_only(func):
    """Decorator: block non-admins."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update):
            await update.message.reply_text('⛔ You are not authorized to use this bot.')
            return ConversationHandler.END
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper

# ── /start ──────────────────────────────────────────
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎌 *KENSHIN ANIME — Thumbnail Generator Bot*\n\n"
        "📋 *Commands:*\n"
        "• `/help` — Show all commands\n"
        "• `/thumb` — Start generating a thumbnail\n"
        "• `/setlogo` — Upload your channel logo\n"
        "• `/cancel` — Cancel current operation\n\n"
        "👉 Send `/thumb` to start!",
        parse_mode='Markdown'
    )

# ── /help ────────────────────────────────────────────
@admin_only
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Kenshin Anime Bot — Help*\n\n"
        "*Thumbnail Generation:*\n"
        "1️⃣ Send `/thumb`\n"
        "2️⃣ Bot asks → Enter anime name\n"
        "3️⃣ Bot fetches info from Jikan API\n"
        "4️⃣ Bot asks → Send poster image\n"
        "5️⃣ Bot generates & sends 1280×720 PNG\n\n"
        "*Logo Management:*\n"
        "• `/setlogo` → Send your Kenshin Anime logo image\n"
        "• Logo saved & used in all future thumbnails\n"
        "• If no logo set, built-in fallback is used\n\n"
        "*Other:*\n"
        "• `/cancel` → Cancel any ongoing operation\n"
        "• `/start` → Welcome message",
        parse_mode='Markdown'
    )

# ── /thumb flow ──────────────────────────────────────
@admin_only
async def thumb_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎌 *Thumbnail Generator*\n\n"
        "Enter the *anime name* to fetch info:",
        parse_mode='Markdown'
    )
    return AWAIT_ANIME

async def got_anime_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    name = update.message.text.strip()
    msg  = await update.message.reply_text(f'🔍 Fetching info for *{name}*...', parse_mode='Markdown')

    anime = fetch_jikan(name)
    if not anime:
        await msg.edit_text(
            f"❌ Anime *{name}* not found on Jikan API.\n"
            "Try a different spelling and send `/thumb` again.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    context.user_data['anime'] = anime
    await msg.edit_text(
        f"✅ *Found:* {anime['title']}\n"
        f"🎭 *Genres:* {' | '.join(anime['genres'])}\n"
        f"⭐ *Score:* {anime['score']}/10\n\n"
        f"📸 Now send the *anime poster image*:",
        parse_mode='Markdown'
    )
    return AWAIT_POSTER

async def got_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    if not update.message.photo and not update.message.document:
        await update.message.reply_text("⚠️ Please send an image (photo), not a file.")
        return AWAIT_POSTER

    msg = await update.message.reply_text('⚙️ Generating thumbnail... Please wait!')

    try:
        # Get image bytes
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
        else:
            file = await update.message.document.get_file()
        poster_bytes = bytes(await file.download_as_bytearray())

        anime = context.user_data.get('anime', {})
        thumb_bytes = generate_thumbnail(poster_bytes, anime)

        caption = (
            f"🎌 *{anime.get('title','Thumbnail')}*\n"
            f"🎭 {' | '.join(anime.get('genres',[]))}\n"
            f"⭐ Score: {anime.get('score','?')}/10\n\n"
            f"_Generated by Kenshin Anime Bot_"
        )
        await msg.delete()
        await update.message.reply_photo(
            photo=InputFile(io.BytesIO(thumb_bytes), filename='thumbnail.png'),
            caption=caption,
            parse_mode='Markdown'
        )
    except Exception as e:
        log.error(f'Generate error: {e}')
        await msg.edit_text(f'❌ Error generating thumbnail: {e}')

    context.user_data.clear()
    return ConversationHandler.END

# ── /setlogo flow ────────────────────────────────────
@admin_only
async def setlogo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📺 *Set Channel Logo*\n\n"
        "Send your *Kenshin Anime logo image* now.\n"
        "It will be used in all generated thumbnails.",
        parse_mode='Markdown'
    )
    return AWAIT_LOGO

async def got_logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    if not update.message.photo and not update.message.document:
        await update.message.reply_text("⚠️ Please send an image.")
        return AWAIT_LOGO
    try:
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
        else:
            file = await update.message.document.get_file()
        await file.download_to_drive(LOGO_PATH)
        await update.message.reply_text(
            "✅ *Logo saved!* It will now appear in all thumbnails.\n"
            "Send `/thumb` to generate a thumbnail.",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f'❌ Failed to save logo: {e}')
    return ConversationHandler.END

# ── /cancel ──────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text('❌ Operation cancelled. Send `/thumb` to start again.', parse_mode='Markdown')
    return ConversationHandler.END

# ── Fallback for non-command messages ─────────────────
async def unknown_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "👋 Send `/thumb` to generate a thumbnail, or `/help` for commands.",
        parse_mode='Markdown'
    )

# ════════════════════════════════════════════════════
#                     MAIN
# ════════════════════════════════════════════════════
def main():
    if not BOT_TOKEN:
        raise ValueError('BOT_TOKEN environment variable not set!')

    app = Application.builder().token(BOT_TOKEN).build()

    # Thumbnail conversation
    thumb_conv = ConversationHandler(
        entry_points=[CommandHandler('thumb', thumb_start)],
        states={
            AWAIT_ANIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_anime_name)],
            AWAIT_POSTER: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, got_poster)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

    # Logo conversation
    logo_conv = ConversationHandler(
        entry_points=[CommandHandler('setlogo', setlogo_start)],
        states={
            AWAIT_LOGO: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, got_logo)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler('start',  start))
    app.add_handler(CommandHandler('help',   help_cmd))
    app.add_handler(CommandHandler('cancel', cancel))
    app.add_handler(thumb_conv)
    app.add_handler(logo_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_msg))

    log.info('🎌 Kenshin Anime Bot starting...')
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
