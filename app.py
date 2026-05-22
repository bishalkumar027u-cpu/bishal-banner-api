import io
import os
import asyncio
import base64
import httpx
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ================= CONFIGURATION =================
# Banner Dimensions
BANNER_WIDTH = 1526
BANNER_HEIGHT = 704

# Colors
YELLOW_BORDER = "#F5B400"
BLACK_BG = "#111111"
WHITE_TEXT = "#FFFFFF"
BLUE_LOGO_BG = "#0B45D9"

# Position Coordinates (based on 1526x704)
LOGO_BOX = {"x": 140, "y": 95, "size": 250}
NAME_POS = {"x": 520, "y": 150}
LIKES_POS = {"x": 950, "y": 290}
LEVEL_POS = {"x": 70, "y": 634}  # bottom se 70px = 704-70
UID_POS = {"x": 1080, "y": 619}  # bottom se 85px = 704-85

# =================================================

INFO_API_URL = "https://infoapi.up.railway.app/player-info"
BASE64_URL = "aHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L2doL1NoYWhHQ3JlYXRvci9pY29uQG1haW4vUE5H"
info_URL = base64.b64decode(BASE64_URL).decode("utf-8")

BASE_DIR = os.path.dirname(__file__)
FONT_BOLD_PATH = os.path.join(BASE_DIR, "arial_unicode_bold.otf")
FONT_REGULAR_PATH = os.path.join(BASE_DIR, "NotoSansCherokee.ttf")

timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
client = httpx.AsyncClient(
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=timeout,
    follow_redirects=True,
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
)
process_pool = ThreadPoolExecutor(max_workers=4)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await client.aclose()
    process_pool.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_font(size: int, bold: bool = False, italic: bool = False):
    """Load font with style support"""
    try:
        if bold and italic:
            # Try bold italic if available
            path = os.path.join(BASE_DIR, "arial_bold_italic.ttf")
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        if bold:
            path = FONT_BOLD_PATH
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        path = FONT_REGULAR_PATH
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    return ImageFont.load_default()


async def fetch_info(uid: str):
    url = f"{INFO_API_URL}?uid={uid}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=502, detail="Info API Error")


async def fetch_image_bytes(item_id):
    if not item_id or str(item_id) == "0":
        return None
    url = f"{info_URL}/{item_id}.png"
    try:
        resp = await client.get(url)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception:
        pass
    return None


def create_freefire_banner(data: dict, avatar_bytes, logo_bytes=None):
    """Create Free Fire MAX style banner"""
    
    # Create base banner
    banner = Image.new("RGB", (BANNER_WIDTH, BANNER_HEIGHT), BLACK_BG)
    draw = ImageDraw.Draw(banner)
    
    # Draw Yellow Border
    border_width = 4
    for i in range(border_width):
        draw.rectangle(
            [i, i, BANNER_WIDTH - 1 - i, BANNER_HEIGHT - 1 - i],
            outline=YELLOW_BORDER
        )
    
    # Draw Top Header Bar (Free Fire MAX style)
    header_height = 80
    draw.rectangle([0, 0, BANNER_WIDTH, header_height], fill=YELLOW_BORDER)
    draw.rectangle([10, 10, BANNER_WIDTH - 10, header_height - 10], fill=BLACK_BG)
    
    # "FREEFIRE MAX" text on header
    font_header = load_font(45, bold=True)
    draw.text((30, 22), "FREEFIRE", font=font_header, fill=YELLOW_BORDER)
    draw.text((30, 22), "FREEFIRE", font=font_header, fill=YELLOW_BORDER)
    font_max = load_font(35, bold=True)
    draw.text((260, 28), "MAX", font=font_max, fill=WHITE_TEXT)
    
    # Draw White Info Panel (Center)
    panel_margin = 20
    panel_x1 = panel_margin
    panel_y1 = header_height + panel_margin
    panel_x2 = BANNER_WIDTH - panel_margin
    panel_y2 = BANNER_HEIGHT - panel_margin
    draw.rectangle([panel_x1, panel_y1, panel_x2, panel_y2], fill="#1A1A1A", outline=YELLOW_BORDER, width=2)
    
    # Blue Logo Box (Avatar/Icon area)
    logo_size = LOGO_BOX["size"]
    logo_x = LOGO_BOX["x"]
    logo_y = LOGO_BOX["y"]
    draw.rectangle([logo_x, logo_y, logo_x + logo_size, logo_y + logo_size], fill=BLUE_LOGO_BG, outline=YELLOW_BORDER, width=3)
    
    # Load and paste avatar
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((logo_size - 20, logo_size - 20), Image.LANCZOS)
            # Create circular mask for avatar
            mask = Image.new("L", (logo_size - 20, logo_size - 20), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([(0, 0), (logo_size - 20, logo_size - 20)], fill=255)
            banner.paste(avatar, (logo_x + 10, logo_y + 10), mask)
        except Exception:
            pass
    
    # Draw "A" text if no avatar
    font_logo = load_font(120, bold=True)
    draw.text((logo_x + 85, logo_y + 60), "A", font=font_logo, fill=WHITE_TEXT)
    
    # Player Name
    name = data.get("AccountName", "Unknown")
    font_name = load_font(55, bold=True, italic=True)
    draw.text((NAME_POS["x"], NAME_POS["y"]), name, font=font_name, fill=WHITE_TEXT)
    
    # Likes
    likes = data.get("Likes", "0")
    font_likes = load_font(40, bold=True)
    
    # Draw like icon (star/heart shape - simplified as text)
    draw.text((LIKES_POS["x"], LIKES_POS["y"]), "★", font=font_likes, fill=YELLOW_BORDER)
    draw.text((LIKES_POS["x"] + 45, LIKES_POS["y"]), str(likes), font=font_likes, fill=WHITE_TEXT)
    
    # Level
    level = data.get("AccountLevel", "0")
    font_level = load_font(50, bold=True)
    level_text = f"Lv.{level}"
    
    # Level background pill
    level_bbox = draw.textbbox((0, 0), level_text, font=font_level)
    level_w = level_bbox[2] - level_bbox[0]
    level_h = level_bbox[3] - level_bbox[1]
    pill_padding = 15
    draw.rectangle(
        [LEVEL_POS["x"] - pill_padding, LEVEL_POS["y"] - pill_padding,
         LEVEL_POS["x"] + level_w + pill_padding, LEVEL_POS["y"] + level_h + pill_padding],
        fill=YELLOW_BORDER,
        radius=25
    )
    draw.text((LEVEL_POS["x"], LEVEL_POS["y"]), level_text, font=font_level, fill=BLACK_BG)
    
    # UID
    uid = data.get("UID", "")
    font_uid = load_font(35, bold=True)
    draw.text((UID_POS["x"], UID_POS["y"]), f"UID: {uid}", font=font_uid, fill="#888888")
    
    # Convert to bytes
    img_io = io.BytesIO()
    banner.save(img_io, "PNG")
    img_io.seek(0)
    return img_io


@app.get("/")
async def home():
    return {"status": "FreeFire MAX Banner API", "endpoint": "/banner?uid=UID"}


@app.get("/banner")
async def get_freefire_banner(uid: str):
    if not uid:
        raise HTTPException(status_code=400, detail="UID required")
    
    # Fetch player data
    data = await fetch_info(uid)
    
    # Parse data (adjust according to your API response)
    payload = data.get("data", data)
    basic = payload.get("basicInfo", {})
    
    player_data = {
        "AccountName": basic.get("nickname", "Unknown"),
        "AccountLevel": basic.get("level", "0"),
        "Likes": basic.get("likes", "8684"),
        "UID": uid,
    }
    
    # Fetch avatar
    avatar_id = basic.get("headPic", 0)
    avatar_bytes = await fetch_image_bytes(avatar_id)
    
    # Generate banner
    loop = asyncio.get_event_loop()
    img_io = await loop.run_in_executor(
        process_pool,
        create_freefire_banner,
        player_data,
        avatar_bytes,
        None
    )
    
    return Response(
        content=img_io.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)