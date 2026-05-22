import io
import os
import asyncio
import httpx
from fastapi import FastAPI, Response, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Silent Info API
INFO_API_URL = "https://silent-info-api.vercel.app/player-info"

# Base directory
BASE_DIR = os.path.dirname(__file__)

# Font paths (same folder me rakhein)
FONT_BOLD_PATH = os.path.join(BASE_DIR, "arial_unicode_bold.otf")
FONT_REGULAR_PATH = os.path.join(BASE_DIR, "NotoSansCherokee.ttf")

def load_font(size: int, bold: bool = False):
    try:
        path = FONT_BOLD_PATH if bold else FONT_REGULAR_PATH
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    except:
        pass
    return ImageFont.load_default()

# ============= DEBUG ENDPOINT - Pehle ye test karein =============
@app.get("/debug")
async def debug_api(uid: str = Query("14169575811"), region: str = Query("IN")):
    """Check what data API is returning"""
    url = f"{INFO_API_URL}?region={region}&uid={uid}"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        
    return {
        "status_code": resp.status_code,
        "response": resp.json() if resp.status_code == 200 else None,
        "raw_text": resp.text[:500] if resp.text else None
    }

# ============= MAIN BANNER ENDPOINT =============
@app.get("/banner")
async def get_banner(uid: str = Query(...), region: str = Query("IN")):
    """Generate banner from API data"""
    
    # 1. Fetch data from info API
    url = f"{INFO_API_URL}?region={region}&uid={uid}"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"API Error: {resp.status_code}")
        
        data = resp.json()
    
    # 2. Extract data (adjust according to actual API response)
    # Pehle debug endpoint se dekho response kaisa aa raha hai
    if "data" in data:
        player = data["data"]
    else:
        player = data
    
    # Try different possible field names
    name = player.get("nickname") or player.get("name") or player.get("playerName") or "Unknown"
    level = player.get("level") or player.get("accountLevel") or player.get("lvl") or "0"
    likes = player.get("likes") or player.get("totalLikes") or player.get("like") or "0"
    avatar_url = player.get("avatar") or player.get("headPic") or player.get("avatarUrl")
    banner_url = player.get("banner") or player.get("bannerUrl")
    
    # 3. Create banner image
    # Banner size
    WIDTH = 1200
    HEIGHT = 600
    
    # Create canvas
    img = Image.new("RGB", (WIDTH, HEIGHT), "#1a1a2e")
    draw = ImageDraw.Draw(img)
    
    # Draw gradient-like header
    draw.rectangle([0, 0, WIDTH, 100], fill="#16213e")
    
    # Title
    font_title = load_font(36, bold=True)
    draw.text((50, 30), "FREE FIRE PROFILE", font=font_title, fill="#e94560")
    
    # Player Name (large)
    font_name = load_font(48, bold=True)
    
    # Add stroke to name
    for dx in [-2, -1, 0, 1, 2]:
        for dy in [-2, -1, 0, 1, 2]:
            draw.text((250 + dx, 150 + dy), name, font=font_name, fill="black")
    draw.text((250, 150), name, font=font_name, fill="#ffffff")
    
    # Level
    font_level = load_font(32, bold=True)
    level_text = f"Level: {level}"
    
    # Level background pill
    bbox = draw.textbbox((0, 0), level_text, font=font_level)
    level_w = bbox[2] - bbox[0]
    level_h = bbox[3] - bbox[1]
    
    draw.rectangle([250, 230, 250 + level_w + 30, 230 + level_h + 15], fill="#e94560", radius=20)
    draw.text((265, 235), level_text, font=font_level, fill="#ffffff")
    
    # Likes
    font_likes = load_font(28, bold=True)
    draw.text((250, 290), f"❤️ Likes: {likes}", font=font_likes, fill="#ff6b6b")
    
    # UID
    font_uid = load_font(24, bold=False)
    draw.text((250, 340), f"UID: {uid}", font=font_uid, fill="#aaaaaa")
    
    # Draw avatar placeholder (circle)
    avatar_size = 150
    avatar_x = 50
    avatar_y = 150
    
    # Outer circle
    draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], 
                  outline="#e94560", width=4)
    
    # Inner circle
    draw.ellipse([avatar_x + 5, avatar_y + 5, avatar_x + avatar_size - 5, avatar_y + avatar_size - 5],
                  fill="#0f3460")
    
    # "A" in avatar
    font_avatar = load_font(80, bold=True)
    draw.text((avatar_x + 45, avatar_y + 35), "A", font=font_avatar, fill="#e94560")
    
    # Try to load actual avatar if URL exists
    if avatar_url:
        try:
            async with httpx.AsyncClient() as client:
                avatar_resp = await client.get(avatar_url)
                if avatar_resp.status_code == 200:
                    avatar_img = Image.open(io.BytesIO(avatar_resp.content))
                    avatar_img = avatar_img.resize((avatar_size - 10, avatar_size - 10), Image.LANCZOS)
                    
                    # Create circular mask
                    mask = Image.new("L", (avatar_size - 10, avatar_size - 10), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse([0, 0, avatar_size - 10, avatar_size - 10], fill=255)
                    
                    img.paste(avatar_img, (avatar_x + 5, avatar_y + 5), mask)
        except:
            pass
    
    # Draw banner background if URL exists
    if banner_url:
        try:
            async with httpx.AsyncClient() as client:
                banner_resp = await client.get(banner_url)
                if banner_resp.status_code == 200:
                    banner_img = Image.open(io.BytesIO(banner_resp.content))
                    banner_img = banner_img.resize((WIDTH, 200), Image.LANCZOS)
                    img.paste(banner_img, (0, HEIGHT - 200))
                    
                    # Dark overlay for text readability
                    overlay = Image.new("RGBA", (WIDTH, 200), (0, 0, 0, 128))
                    img.paste(overlay, (0, HEIGHT - 200), overlay)
        except:
            pass
    
    # Bottom decorative line
    draw.rectangle([0, HEIGHT - 10, WIDTH, HEIGHT], fill="#e94560")
    
    # Convert to bytes
    img_io = io.BytesIO()
    img.save(img_io, "PNG")
    img_io.seek(0)
    
    return Response(content=img_io.getvalue(), media_type="image/png")


@app.get("/")
async def home():
    return {
        "message": "Free Fire Banner API",
        "endpoints": {
            "/banner?uid=YOUR_UID&region=IN": "Generate banner",
            "/debug?uid=YOUR_UID&region=IN": "Check API response"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)