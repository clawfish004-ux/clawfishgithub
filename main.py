import os
import sys
import subprocess

# --- AUTO INSTALLER ---
def install_and_fix():
    libs = ["google-generativeai", "openai", "edge-tts", "moviepy", "requests", "nest_asyncio", "Pillow==9.5.0"]
    for lib in libs:
        pkg = lib.split("==")[0]
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

install_and_fix()

import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
import google.generativeai as genai
from openai import OpenAI
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.all import resize
from PIL import Image

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else 1

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# ကိုကို ထည့်လိုက်တဲ့ Secret နာမည်အတိုင်း ပြောင်းယူထားပါတယ်
UNSPLASH_KEY = os.getenv("UNSPLASH_API_KEY") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_O4_MINI", "")
VOICE = "en-US-AndrewNeural"

def get_pro_script():
    prompt = """
    Act as a professional news anchor for 'K-News Today'.
    Write a VERY LONG 3-minute news script (at least 650 words) about 3 major Korean celebrity stories.
    Intro: 'Welcome to K-News Today, your daily source for the latest in Korean entertainment.'
    Format:
    STORY: [The 650-word script]
    TAGS: [15 Unsplash search keywords like 'korean city', 'kpop concert', 'seoul fashion']
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash') 
        response = model.generate_content(prompt, generation_config={"temperature": 0.9})
        return parse_output(response.text)
    except:
        client = OpenAI()
        response = client.chat.completions.create(model="o1-mini", messages=[{"role": "user", "content": prompt}])
        return parse_output(response.choices[0].message.content)

def parse_output(text):
    story = text.split("STORY:")[1].split("TAGS:")[0].strip()
    tags = text.split("TAGS:")[1].strip().replace("[","").replace("]","").split(",")
    return story, [t.strip() for t in tags]

async def make_v9_video():
    target_duration = 180 
    print("🧠 K-News Today is preparing a 3-minute HD broadcast...")
    story_text, keywords = get_pro_script()
    
    # Audio
    await edge_tts.Communicate(story_text, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    actual_duration = min(audio.duration, target_duration)
    final_audio = audio.subclip(0, actual_duration)

    # Unsplash HD Downloader
    print(f"📸 Fetching 30 HD images from Unsplash...")
    local_imgs = []
    for kw in keywords:
        if len(local_imgs) >= 30: break
        url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(kw)}&per_page=5&orientation=landscape&client_id={UNSPLASH_KEY}"
        try:
            res = requests.get(url).json()
            for p in res.get('results', []):
                if len(local_imgs) >= 30: break
                img_url = p['urls']['regular']
                r = requests.get(img_url, timeout=20)
                if r.status_code == 200:
                    fname = f"img_{len(local_imgs)}.jpg"
                    with open(fname, "wb") as f: f.write(r.content)
                    local_imgs.append(fname)
        except: continue

    # Video Engine
    print(f"🎬 Rendering {len(local_imgs)} clips with Zoom & Fade...")
    img_dur = actual_duration / len(local_imgs)
    clips = []
    for i, p in enumerate(local_imgs):
        # 1080p Resolution
        clip = ImageClip(p).set_duration(img_dur + 0.6).set_fps(10).resize(width=1920)
        # Ken Burns Effect
        clip = clip.fx(resize, lambda t: 1 + 0.03 * t)
        if i > 0: clip = clip.crossfadein(0.6)
        clips.append(clip)
    
    final_video = concatenate_videoclips(clips, method="compose", padding=-0.6)
    final_video = final_video.set_audio(final_audio).set_duration(actual_duration)
    
    output = "knews_v9_hd.mp4"
    final_video.write_videofile(output, fps=10, codec="libx264", bitrate="3000k", logger=None)
    
    audio.close()
    return output, local_imgs

async def main():
    print("🚀 Launching Version 9 (Unsplash Engine)...")
    try:
        path, imgs = await make_v9_video()
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(path, "rb") as v:
            requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "📺 K-News Today: Professional HD Broadcast (V9)"})
        
        # Cleanup
        os.remove(path); os.remove("voice.mp3")
        for img in imgs: os.remove(img)
        print("✅ V9 Successful! Check Telegram.")
    except Exception as e:
        print(f"❌ V9 Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

