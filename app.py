import io
import os
import asyncio
import httpx
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Response, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont

# ================= CONFIGURATION =================
# Banner Dimensions (based on 1526x704)
BANNER_WIDTH = 1526
BANNER_HEIGHT = 704

# Colors
YELLOW_BORDER = "#F5B400"
BLACK_BG = "#111111"
WHITE_TEXT = "#FFFFFF"
BLUE_LOGO_BG = "#0B45D9"
GRAY_TEXT = "#888888"

# Position Coordinates
LOGO_BOX = {"x": 140, "y": 95, "size": 250}
NAME_POS = {"x": 520, "y": 150}
LIKES_POS = {"x": 950, "y": 290}
LEVEL_POS = {"x": 70, "y": 634}  # bottom se 70px = 704-70
UID_POS = {"x": 1080, "y": 619}  # bottom se 85px = 704-85

# ================= API ENDPOINT =================
INFO_API_URL = "https://silent-info-api.vercel.app/player-info"

# ================= SETUP =================
BASE_DIR = os.path.dirname(__file__)
FONT_BOLD_PATH = os.path.join(BASE_DIR, "arial_unicode_bold.otf")
FONT_REGULAR_PATH = os.path.join(BASE_DIR, "NotoSansCherokee.ttf")

# Custom font paths (optional - for better styling)
FONT_BOLD_ITALIC_PATH = os.path.join(BASE_DIR, "arial_bold_italic.ttf")

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
    try:
        await client.aclose()
    except Exception:
        pass
    try:
        process_pool.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================= FONT LOADER =================
def load_font(size: int, bold: bool = False, italic: bool = False):
    """Load font with style support"""
    # Try bold italic first
    if bold and italic:
        try:
            if os.path.exists(FONT_BOLD_ITALIC_PATH):
                return ImageFont.truetype(FONT_BOLD_ITALIC_PATH, size)
        except Exception:
            pass
    
    # Try bold
    if bold:
        try:
            if os.path.exists(FONT_BOLD_PATH):
                return ImageFont.truetype(FONT_BOLD_PATH, size)
        except Exception:
            pass
    
    # Try regular
    try:
        if os.path.exists(FONT_REGULAR_PATH):
            return ImageFont.truetype(FONT_REGULAR_PATH, size)
    except Exception:
        pass
    
    # Default fallback
    return ImageFont.load_default()


# ================= API FUNCTIONS =================
async def fetch_player_info(uid: str, region: str = "IN"):
    """Fetch player info from silent-info-api"""
    url = f"{INFO_API_URL}?region={region}&uid={uid}"
    
    try:
        resp = await client.get(url)
        
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 400:
            raise HTTPException(status_code=400, detail="Invalid UID or Region. Please check parameters.")
        elif resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Player not found. UID may be incorrect.")
        else:
            raise HTTPException(status_code=502, detail=f"API Error: Status {resp.status_code}")
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="API request timeout. Please try again.")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"API request failed: {str(e)}")


async def fetch_avatar_image(avatar_url: str):
    """Fetch avatar image from URL"""
    if not avatar_url:
        return None
    
    try:
        resp = await client.get(avatar_url)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception:
        pass
    return None


# ================= BANNER GENERATION =================
def create_freefire_banner(player_data: dict, avatar_bytes=None):
    """Create Free Fire MAX style banner"""
    
    # Create base banner
    banner = Image.new("RGB", (BANNER_WIDTH, BANNER_HEIGHT), BLACK_BG)
    draw = ImageDraw.Draw(banner)
    
    # Draw Yellow Border (4px)
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
    font_max = load_font(35, bold=True)
    draw.text((260, 28), "MAX", font=font_max, fill=WHITE_TEXT)
    
    # Draw White Info Panel (Center)
    panel_margin = 20
    panel_x1 = panel_margin
    panel_y1 = header_height + panel_margin
    panel_x2 = BANNER_WIDTH - panel_margin
    panel_y2 = BANNER_HEIGHT - panel_margin
    draw.rectangle([panel_x1, panel_y1, panel_x2, panel_y2], fill="#1A1A1A", outline=YELLOW_BORDER, width=2)
    
    # Blue Logo Box (Avatar area)
    logo_size = LOGO_BOX["size"]
    logo_x = LOGO_BOX["x"]
    logo_y = LOGO_BOX["y"]
    draw.rectangle([logo_x, logo_y, logo_x + logo_size, logo_y + logo_size], fill=BLUE_LOGO_BG, outline=YELLOW_BORDER, width=3)
    
    # Load and paste avatar (if available)
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
            # Fallback to "A" text if avatar fails
            font_logo = load_font(120, bold=True)
            draw.text((logo_x + 85, logo_y + 60), "A", font=font_logo, fill=WHITE_TEXT)
    else:
        # Draw "A" text if no avatar
        font_logo = load_font(120, bold=True)
        draw.text((logo_x + 85, logo_y + 60), "A", font=font_logo, fill=WHITE_TEXT)
    
    # Player Name (with stroke effect)
    name = player_data.get("nickname", "Unknown")
    font_name = load_font(55, bold=True, italic=True)
    
    # Add black stroke to name
    stroke = 2
    for dx in range(-stroke, stroke + 1):
        for dy in range(-stroke, stroke + 1):
            draw.text((NAME_POS["x"] + dx, NAME_POS["y"] + dy), name, font=font_name, fill="black")
    draw.text((NAME_POS["x"], NAME_POS["y"]), name, font=font_name, fill=WHITE_TEXT)
    
    # Likes
    likes = player_data.get("likes", "0")
    font_likes = load_font(40, bold=True)
    
    # Draw star icon
    draw.text((LIKES_POS["x"], LIKES_POS["y"]), "★", font=font_likes, fill=YELLOW_BORDER)
    draw.text((LIKES_POS["x"] + 45, LIKES_POS["y"]), str(likes), font=font_likes, fill=WHITE_TEXT)
    
    # Level with pill background
    level = player_data.get("level", "0")
    font_level = load_font(50, bold=True)
    level_text = f"Lv.{level}"
    
    # Calculate text size for pill
    level_bbox = draw.textbbox((0, 0), level_text, font=font_level)
    level_w = level_bbox[2] - level_bbox[0]
    level_h = level_bbox[3] - level_bbox[1]
    pill_padding = 15
    pill_radius = 25
    
    # Draw pill background
    draw.rectangle(
        [LEVEL_POS["x"] - pill_padding, LEVEL_POS["y"] - pill_padding,
         LEVEL_POS["x"] + level_w + pill_padding, LEVEL_POS["y"] + level_h + pill_padding],
        fill=YELLOW_BORDER,
        outline=None
    )
    # Fix rounded corners (approximation)
    draw.ellipse([LEVEL_POS["x"] - pill_padding, LEVEL_POS["y"] - pill_padding, 
                  LEVEL_POS["x"] - pill_padding + pill_radius*2, LEVEL_POS["y"] - pill_padding + pill_radius*2], fill=YELLOW_BORDER)
    draw.ellipse([LEVEL_POS["x"] + level_w + pill_padding - pill_radius*2, LEVEL_POS["y"] - pill_padding,
                  LEVEL_POS["x"] + level_w + pill_padding, LEVEL_POS["y"] - pill_padding + pill_radius*2], fill=YELLOW_BORDER)
    draw.ellipse([LEVEL_POS["x"] - pill_padding, LEVEL_POS["y"] + level_h + pill_padding - pill_radius*2,
                  LEVEL_POS["x"] - pill_padding + pill_radius*2, LEVEL_POS["y"] + level_h + pill_padding], fill=YELLOW_BORDER)
    draw.ellipse([LEVEL_POS["x"] + level_w + pill_padding - pill_radius*2, LEVEL_POS["y"] + level_h + pill_padding - pill_radius*2,
                  LEVEL_POS["x"] + level_w + pill_padding, LEVEL_POS["y"] + level_h + pill_padding], fill=YELLOW_BORDER)
    
    # Draw level text
    draw.text((LEVEL_POS["x"], LEVEL_POS["y"]), level_text, font=font_level, fill=BLACK_BG)
    
    # UID (bottom right)
    uid = player_data.get("uid", "")
    font_uid = load_font(35, bold=True)
    draw.text((UID_POS["x"], UID_POS["y"]), f"UID: {uid}", font=font_uid, fill=GRAY_TEXT)
    
    # Convert to bytes
    img_io = io.BytesIO()
    banner.save(img_io, "PNG", optimize=True)
    img_io.seek(0)
    return img_io


# ================= FASTAPI ENDPOINTS =================
@app.get("/")
async def home():
    return {
        "status": "FreeFire MAX Banner API is running",
        "endpoint": "/banner?uid=14169575811&region=IN",
        "usage": "Add region parameter (IN, ID, BR, ME, EU)"
    }


@app.get("/banner")
async def get_freefire_banner(
    uid: str = Query(..., description="Free Fire UID"),
    region: str = Query("IN", description="Region code: IN, ID, BR, ME, EU")
):
    """
    Generate FreeFire MAX style banner for given UID and region
    """
    if not uid or not uid.isdigit():
        raise HTTPException(status_code=400, detail="Invalid UID. UID must contain only numbers.")
    
    # Fetch player info from API
    try:
        api_response = await fetch_player_info(uid, region)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    # Extract player data from API response
    # Adjust these keys based on actual API response structure
    if "data" in api_response:
        player_info = api_response["data"]
    else:
        player_info = api_response
    
    player_data = {
        "nickname": player_info.get("nickname") or player_info.get("name") or "Unknown",
        "level": player_info.get("level") or player_info.get("accountLevel") or "0",
        "likes": player_info.get("likes") or player_info.get("totalLikes") or "0",
        "uid": uid,
        "avatar_url": player_info.get("avatar") or player_info.get("headPic") or None,
    }
    
    # Fetch avatar image if URL exists
    avatar_bytes = None
    if player_data["avatar_url"]:
        avatar_bytes = await fetch_avatar_image(player_data["avatar_url"])
    
    # Generate banner in thread pool
    loop = asyncio.get_event_loop()
    img_io = await loop.run_in_executor(
        process_pool,
        create_freefire_banner,
        player_data,
        avatar_bytes
    )
    
    # Return image
    return Response(
        content=img_io.getvalue(),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=300",
            "Content-Disposition": f'inline; filename="ff_banner_{uid}.png"'
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)