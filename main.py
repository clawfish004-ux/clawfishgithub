import os
import sys
import subprocess

# --- AUTO INSTALLER ---
# GitHub စက်ထဲမှာ library မရှိရင် auto သွင်းပေးမယ့် logic
def install_package(package):
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        print(f"📦 Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# လိုအပ်တဲ့ libraries တွေကို စစ်မယ်
for lib in ["google-generativeai", "edge-tts", "moviepy", "requests", "nest-asyncio"]:
    install_package(lib)

import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
import google.generativeai as genai
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image

# PIL version fix
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else 1

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VOICE = "en-US-AndrewNeural"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_trending_knews():
    prompt = """
    Act as a professional K-Entertainment reporter. 
    1. Write 2 hottest trending stories about Korean celebrities for today in 2026.
    2. Provide 6 pexels keywords to find real people images (Avoid stars/sky).
    Format:
    STORY: [The content]
    TAGS: [kw1, kw2, kw3, kw4, kw5, kw6]
    """
    try:
        response = model.generate_content(prompt).text
        story = response.split("STORY:")[1].split("TAGS:")[0].strip()
        tags = response.split("TAGS:")[1].strip().replace("[","").replace("]","").split(",")
        return story, [t.strip() for t in tags]
    except:
        return "New K-pop global tour 2026 starts today.", ["kpop stage", "korean singer", "seoul fashion"]

def download_image(url, filename):
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if res.status_code == 200:
            with open(filename, "wb") as f: f.write(res.content)
            return True
    except: return False

async def make_2min_video():
    target_duration = 120
    print("🧠 Gemini is fetching today's hottest trends...")
    story_text, keywords = get_trending_knews()
    
    # Audio
    print("🎙️ Creating Audio...")
    await edge_tts.Communicate((story_text + " ") * 2, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3").subclip(0, target_duration)
    
    # Images
    print(f"🔎 Pexels Keywords: {keywords}")
    headers = {"Authorization": PEXELS_API_KEY}
    all_urls = []
    for kw in keywords:
        url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(kw)}&per_page=2&orientation=landscape"
        try:
            res = requests.get(url, headers=headers).json()
            all_urls.extend([p['src']['large'] for p in res.get('photos', [])])
        except: continue
    
    local_imgs = []
    for i, url in enumerate(all_urls[:12]):
        fname = f"img_{i}.jpg"
        if download_image(url, fname): local_imgs.append(fname)
            
    if not local_imgs: return None
        
    # Clips & Render
    print("🎬 Rendering Video (2 Minutes)...")
    sec_per_img = target_duration / len(local_imgs)
    clips = [ImageClip(p).set_duration(sec_per_img).resize(newsize=(640, 360)).set_fps(8) for p in local_imgs]
    
    video = concatenate_videoclips(clips, method="chain").set_audio(audio)
    video.write_videofile("trend.mp4", fps=8, codec="libx264", bitrate="500k", threads=2, logger=None)
    
    audio.close()
    return "trend.mp4", local_imgs, story_text

async def main():
    print("🚀 Starting Production...")
    try:
        result = await make_2min_video()
        if result:
            path, imgs, story = result
            print("📤 Sending to Telegram...")
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🇰🇷 Trending:\n{story[:150]}..."})
            
            # Cleanup
            os.remove(path)
            os.remove("voice.mp3")
            for img in imgs: os.remove(img)
            print("✅ Successfully Finished!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

