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
UNSPLASH_KEY = os.getenv("UNSPLASH_API_KEY") 
PEXELS_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY") 
VOICE = "en-US-AvaNeural"

def get_k_entertainment_script():
    prompt = """
    Act as a professional K-News anchor for 'K-News Today'.
    Write a 3-minute script (700 words) about:
    1. K-Drama/TV Series news (2026 trending shows).
    2. K-Pop Idol updates (NewJeans, IVE, or BTS).
    3. Korean Actor/Actress personal news.
    STRICT IMAGE RULE: Provide 25 keywords focusing on PEOPLE/HUMANS:
    'Korean actor portrait', 'Kpop idol performance', 'Korean actress fashion', 'smiling Korean celebrity'.
    Format: STORY: [Text] TAGS: [Keywords]
    """
    print("🧠 Gemini 3 Flash Preview is crafting K-Content...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        response = model.generate_content(prompt)
        text = response.text
        story = text.split("STORY:")[1].split("TAGS:")[0].strip()
        tags = text.split("TAGS:")[1].strip().replace("[","").replace("]","").split(",")
        return story, [t.strip() for t in tags]
    except Exception as e:
        print(f"⚠️ AI Script Error: {e}")
        return "Welcome to K-News Today. Today's top celebrity stories...", ["korean actor", "kpop idol"]

async def make_v10_video():
    target_duration = 180 
    story_text, keywords = get_k_entertainment_script()
    
    # Audio
    await edge_tts.Communicate(story_text, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    actual_duration = min(audio.duration, target_duration)
    final_audio = audio.subclip(0, actual_duration)

    # Human-centric Image Fetching
    local_imgs = []
    print(f"📸 Fetching Celeb Photos...")
    for kw in keywords:
        if len(local_imgs) >= 40: break
        try:
            # Engine A: Unsplash
            u_headers = {"Authorization": f"Client-ID {UNSPLASH_KEY}"}
            res = requests.get(f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(kw)}&per_page=3", headers=u_headers, timeout=5).json()
            for p in res.get('results', []):
                r = requests.get(p['urls']['small'], timeout=10) # 'small' link is perfect for 360p
                if r.status_code == 200:
                    fname = f"img_{len(local_imgs)}.jpg"
                    with open(fname, "wb") as f: f.write(r.content)
                    local_imgs.append(fname)
            
            # Engine B: Pexels
            if len(local_imgs) < 30:
                p_headers = {"Authorization": PEXELS_KEY}
                pres = requests.get(f"https://api.pexels.com/v1/search?query={urllib.parse.quote(kw)}&per_page=3", headers=p_headers, timeout=5).json()
                for p in pres.get('photos', []):
                    r = requests.get(p['src']['medium'], timeout=10)
                    if r.status_code == 200:
                        fname = f"img_{len(local_imgs)}.jpg"
                        with open(fname, "wb") as f: f.write(r.content)
                        local_imgs.append(fname)
        except: continue

    if len(local_imgs) < 5: return None, []

    # Rendering (Optimized for 640x360)
    img_dur = actual_duration / len(local_imgs)
    clips = []
    for i, p in enumerate(local_imgs):
        # ကိုကိုပြောတဲ့အတိုင်း 640x360 ပြောင်းလိုက်ပါပြီ
        clip = ImageClip(p).set_duration(img_dur + 0.5).set_fps(10).resize(height=360) 
        clip = clip.set_position("center").fx(resize, lambda t: 1 + 0.02 * t)
        if i > 0: clip = clip.crossfadein(0.5)
        clips.append(clip)
    
    final_video = concatenate_videoclips(clips, method="compose", padding=-0.5)
    final_video = final_video.set_audio(final_audio).set_duration(actual_duration)
    
    output = "knews_360p.mp4"
    # Bitrate ကိုလည်း အလိုက်သင့်လျှော့ချထားပါတယ်
    final_video.write_videofile(output, fps=10, codec="libx264", bitrate="1200k", audio_codec="aac", logger=None)
    
    audio.close()
    return output, local_imgs

async def main():
    print("🚀 Launching V10 (Super Lite 360p)...")
    try:
        path, imgs = await make_v10_video()
        if not path:
            print("❌ Failure: No celebrity images found.")
            return

        # Upload with Debug Log
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(path, "rb") as v:
            res = requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "📺 K-News Today: 360p Celebrity Update"})
            print(f"📡 Telegram Response: {res.status_code}")

        # Cleanup
        os.remove(path); os.remove("voice.mp3")
        for img in imgs: os.remove(img)
        print("✅ Process Complete!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

