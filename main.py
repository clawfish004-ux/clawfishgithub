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
VOICE = "en-US-AndrewNeural"

def get_pro_script():
    prompt = """
    Act as a professional news anchor for 'K-News Today'.
    Write a 3-minute news script about 3 Korean celebrity stories.
    Intro: 'Welcome to K-News Today, your daily source for the latest in Korean entertainment.'
    Provide 15 keywords. Format: STORY: [Content] TAGS: [Keywords]
    """
    print("🧠 Using Gemini 3 Flash Preview...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        response = model.generate_content(prompt)
        return parse_output(response.text)
    except:
        client = OpenAI(api_key=OPENAI_KEY)
        response = client.chat.completions.create(model="o1-mini", messages=[{"role": "user", "content": prompt}])
        return parse_output(response.choices[0].message.content)

def parse_output(text):
    story = text.split("STORY:")[1].split("TAGS:")[0].strip()
    tags = text.split("TAGS:")[1].strip().replace("[","").replace("]","").split(",")
    return story, [t.strip() for t in tags]

async def make_v9_5_video():
    target_duration = 180 
    story_text, keywords = get_pro_script()
    
    await edge_tts.Communicate(story_text, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    actual_duration = min(audio.duration, target_duration)
    final_audio = audio.subclip(0, actual_duration)

    local_imgs = []
    headers = {"Authorization": f"Client-ID {UNSPLASH_KEY}"}
    p_headers = {"Authorization": PEXELS_KEY}

    # Dual-Engine Image Fetching
    for kw in keywords:
        if len(local_imgs) >= 30: break
        try:
            # Try Unsplash first
            res = requests.get(f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(kw)}&per_page=3", headers=headers, timeout=5).json()
            for p in res.get('results', []):
                r = requests.get(p['urls']['regular'], timeout=10)
                if r.status_code == 200:
                    fname = f"img_{len(local_imgs)}.jpg"
                    with open(fname, "wb") as f: f.write(r.content)
                    local_imgs.append(fname)
            # If still low, try Pexels
            if len(local_imgs) < 30:
                pres = requests.get(f"https://api.pexels.com/v1/search?query={urllib.parse.quote(kw)}&per_page=3", headers=p_headers, timeout=5).json()
                for p in pres.get('photos', []):
                    r = requests.get(p['src']['large'], timeout=10)
                    if r.status_code == 200:
                        fname = f"img_{len(local_imgs)}.jpg"
                        with open(fname, "wb") as f: f.write(r.content)
                        local_imgs.append(fname)
        except: continue

    if not local_imgs: return None, []

    # Rendering with Safe Settings
    img_dur = actual_duration / len(local_imgs)
    clips = [ImageClip(p).set_duration(img_dur + 0.6).set_fps(10).resize(width=1280).fx(resize, lambda t: 1 + 0.03 * t).crossfadein(0.6) if i > 0 else ImageClip(p).set_duration(img_dur + 0.6).set_fps(10).resize(width=1280).fx(resize, lambda t: 1 + 0.03 * t) for i, p in enumerate(local_imgs)]
    
    final_video = concatenate_videoclips(clips, method="compose", padding=-0.6)
    final_video = final_video.set_audio(final_audio).set_duration(actual_duration)
    
    output = "knews_final.mp4"
    # Bitrate ကို 2000k လောက်ပဲထားမယ် File size မကြီးအောင်
    final_video.write_videofile(output, fps=10, codec="libx264", bitrate="2000k", audio_codec="aac", logger=None)
    
    audio.close()
    return output, local_imgs

async def main():
    print("🚀 Launching V9.5 (Debug Edition)...")
    try:
        path, imgs = await make_v9_5_video()
        if not path:
            print("❌ No images found.")
            return

        print(f"📤 Uploading to Telegram (Chat ID: {TELEGRAM_CHAT_ID})...")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(path, "rb") as v:
            response = requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 K-News Today V9.5"})
            
        # Debugging Response
        print(f"📡 Telegram Response: {response.status_code} - {response.text}")
        
        if response.status_code != 200:
            print("⚠️ Video failed, trying to send as Document...")
            doc_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
            with open(path, "rb") as v:
                requests.post(doc_url, files={"document": v}, data={"chat_id": TELEGRAM_CHAT_ID})

        os.remove(path); os.remove("voice.mp3")
        for img in imgs: os.remove(img)
        print("✅ Finished Process.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
    
