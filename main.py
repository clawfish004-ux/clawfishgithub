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

# --- CONFIG (Mapped to GitHub Secrets Exactly) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
UNSPLASH_KEY = os.getenv("UNSPLASH_API_KEY") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY") # ပုံထဲကအတိုင်း ပြင်လိုက်ပါပြီ
VOICE = "en-US-AndrewNeural"

def get_pro_script():
    prompt = """
    Act as a professional news anchor for 'K-News Today'.
    Write a VERY LONG 3-minute news script (at least 700 words) about 3 major Korean celebrity stories for April 2026.
    Intro: 'Welcome to K-News Today, your daily source for the latest in Korean entertainment.'
    Format:
    STORY: [The 700-word script]
    TAGS: [15 Unsplash keywords like 'korean actor', 'kpop stage', 'seoul nightlife']
    """
    
    # 1. Gemini 3 Flash Preview (The Primary Model for 2026)
    print("🧠 Using Gemini 3 Flash Preview (2026 Optimized)...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Model နာမည်ကို ၂၀၂၆ standard အတိုင်း သုံးထားပါတယ်
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        response = model.generate_content(prompt)
        if "STORY:" in response.text:
            print("✅ Gemini 3 Success!")
            return parse_output(response.text)
    except Exception as e:
        print(f"⚠️ Gemini 3 failed: {e}")

    # 2. OpenAI Backup (Correct Key Mapping)
    print("🤖 Switching to OpenAI Backup...")
    try:
        client = OpenAI(api_key=OPENAI_KEY)
        response = client.chat.completions.create(
            model="o1-mini", 
            messages=[{"role": "user", "content": prompt}]
        )
        print("✅ OpenAI Success!")
        return parse_output(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ All AI Models failed: {e}")
        return "Welcome to K-News Today. " + ("K-pop News Update. " * 60), ["kpop", "seoul"]

def parse_output(text):
    story = text.split("STORY:")[1].split("TAGS:")[0].strip()
    tags = text.split("TAGS:")[1].strip().replace("[","").replace("]","").split(",")
    return story, [t.strip() for t in tags]

async def make_v9_video():
    target_duration = 180 
    story_text, keywords = get_pro_script()
    
    # Audio
    await edge_tts.Communicate(story_text, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    actual_duration = min(audio.duration, target_duration)
    final_audio = audio.subclip(0, actual_duration)

    # Unsplash HD
    local_imgs = []
    print(f"📸 Fetching HD images from Unsplash (using API_KEY)...")
    for kw in keywords:
        if len(local_imgs) >= 30: break
        url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(kw)}&per_page=5&orientation=landscape&client_id={UNSPLASH_KEY}"
        try:
            res = requests.get(url, timeout=15).json()
            for p in res.get('results', []):
                if len(local_imgs) >= 30: break
                r = requests.get(p['urls']['regular'], timeout=20)
                if r.status_code == 200:
                    fname = f"img_{len(local_imgs)}.jpg"
                    with open(fname, "wb") as f: f.write(r.content)
                    local_imgs.append(fname)
        except: continue

    # Video Processing
    img_dur = actual_duration / len(local_imgs)
    clips = []
    for i, p in enumerate(local_imgs):
        clip = ImageClip(p).set_duration(img_dur + 0.6).set_fps(10).resize(width=1920)
        clip = clip.fx(resize, lambda t: 1 + 0.03 * t) # Ken Burns Effect
        if i > 0: clip = clip.crossfadein(0.6)
        clips.append(clip)
    
    final_video = concatenate_videoclips(clips, method="compose", padding=-0.6)
    final_video = final_video.set_audio(final_audio).set_duration(actual_duration)
    
    output = "knews_2026_final.mp4"
    final_video.write_videofile(output, fps=10, codec="libx264", bitrate="3000k", logger=None)
    
    audio.close()
    return output, local_imgs

async def main():
    print("🚀 Launching K-News Today V9.2 (Stable 2026 Edition)...")
    try:
        path, imgs = await make_v9_video()
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(path, "rb") as v:
            requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "📺 K-News Today: Professional 2026 Edition"})
        
        # Cleanup
        os.remove(path); os.remove("voice.mp3")
        for img in imgs: os.remove(img)
        print("✅ Production Finished!")
    except Exception as e:
        print(f"❌ V9.2 Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

