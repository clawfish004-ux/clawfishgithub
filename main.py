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
    Write a VERY LONG 3-minute news script (at least 700 words) about 3 major Korean celebrity stories.
    Intro: 'Welcome to K-News Today, your daily source for the latest in Korean entertainment.'
    Provide 15 diverse keywords (e.g. 'seoul street', 'kpop idols', 'korean lifestyle').
    Format:
    STORY: [The 700-word script]
    TAGS: [kw1, kw2, ..., kw15]
    """
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

async def make_v9_4_video():
    target_duration = 180 
    story_text, keywords = get_pro_script()
    
    await edge_tts.Communicate(story_text, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    actual_duration = min(audio.duration, target_duration)
    final_audio = audio.subclip(0, actual_duration)

    local_imgs = []
    
    # 1. Unsplash Try (Engine A)
    print(f"📸 Attempting Unsplash HD...")
    headers = {"Authorization": f"Client-ID {UNSPLASH_KEY}"}
    for kw in keywords:
        if len(local_imgs) >= 30: break
        url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(kw)}&per_page=5"
        try:
            res = requests.get(url, headers=headers, timeout=10).json()
            for p in res.get('results', []):
                if len(local_imgs) >= 30: break
                r = requests.get(p['urls']['regular'], timeout=15)
                if r.status_code == 200:
                    fname = f"img_{len(local_imgs)}.jpg"
                    with open(fname, "wb") as f: f.write(r.content)
                    local_imgs.append(fname)
        except: continue

    # 2. Pexels Backup (Engine B) - တကယ်လို့ Unsplash မှာ ပုံမရရင်
    if len(local_imgs) < 10:
        print(f"⚠️ Unsplash failed or few images. Switching to Pexels Backup...")
        p_headers = {"Authorization": PEXELS_KEY}
        for kw in keywords:
            if len(local_imgs) >= 30: break
            url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(kw)}&per_page=5"
            try:
                res = requests.get(url, headers=p_headers, timeout=10).json()
                for p in res.get('photos', []):
                    if len(local_imgs) >= 30: break
                    r = requests.get(p['src']['large'], timeout=15)
                    if r.status_code == 200:
                        fname = f"img_{len(local_imgs)}.jpg"
                        with open(fname, "wb") as f: f.write(r.content)
                        local_imgs.append(fname)
            except: continue

    if not local_imgs: return None, []

    # Video Render
    img_dur = actual_duration / len(local_imgs)
    clips = []
    for i, p in enumerate(local_imgs):
        clip = ImageClip(p).set_duration(img_dur + 0.6).set_fps(10).resize(width=1920)
        clip = clip.fx(resize, lambda t: 1 + 0.03 * t)
        if i > 0: clip = clip.crossfadein(0.6)
        clips.append(clip)
    
    final_video = concatenate_videoclips(clips, method="compose", padding=-0.6)
    final_video = final_video.set_audio(final_audio).set_duration(actual_duration)
    
    output = "knews_dual_engine.mp4"
    final_video.write_videofile(output, fps=10, codec="libx264", bitrate="3000k", logger=None)
    
    audio.close()
    return output, local_imgs

async def main():
    print("🔥 Launching V9.4 (Dual-Engine: Unsplash + Pexels)...")
    try:
        path, imgs = await make_v9_4_video()
        if not path:
            print("❌ Failure: Could not get images from any source.")
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(path, "rb") as v:
            requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "📺 K-News Today: Dual-Engine Stability V9.4"})
        
        os.remove(path); os.remove("voice.mp3")
        for img in imgs: os.remove(img)
        print("✅ Success! Video sent to Telegram.")
    except Exception as e:
        print(f"❌ V9.4 Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

