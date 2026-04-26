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
VOICE = "en-US-AvaNeural" # ပိုချိုသာတဲ့ မိန်းကလေးအသံ ပြောင်းထားပါတယ်

def get_k_celeb_script():
    prompt = """
    Act as a professional K-News anchor. Write a 3-minute news script about:
    1. A huge K-Drama/TV Series update in 2026.
    2. K-Pop group (BTS/Blackpink/NewJeans) latest news.
    3. A famous Korean actor/actress personal news.
    Provide 20 keywords like: 'handsome korean actor portrait', 'korean actress filming', 'kpop idols on stage high quality', 'korean movie scene'.
    Format: STORY: [Content] TAGS: [Keywords]
    """
    print("🧠 Gemini 3 Flash Preview is preparing 2026 K-News...")
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

async def make_v9_8_video():
    target_duration = 180 
    story_text, keywords = get_k_celeb_script()
    
    await edge_tts.Communicate(story_text, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    actual_duration = min(audio.duration, target_duration)
    final_audio = audio.subclip(0, actual_duration)

    local_imgs = []
    # Search logic for People/Celebs
    for kw in keywords:
        if len(local_imgs) >= 35: break
        try:
            u_headers = {"Authorization": f"Client-ID {UNSPLASH_KEY}"}
            res = requests.get(f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(kw)}&per_page=3&orientation=landscape", headers=u_headers, timeout=5).json()
            for p in res.get('results', []):
                r = requests.get(p['urls']['regular'], timeout=10)
                if r.status_code == 200:
                    fname = f"img_{len(local_imgs)}.jpg"
                    with open(fname, "wb") as f: f.write(r.content)
                    local_imgs.append(fname)
            
            if len(local_imgs) < 30:
                p_headers = {"Authorization": PEXELS_KEY}
                pres = requests.get(f"https://api.pexels.com/v1/search?query={urllib.parse.quote(kw)}&per_page=3", headers=p_headers, timeout=5).json()
                for p in pres.get('photos', []):
                    r = requests.get(p['src']['large2x'], timeout=10)
                    if r.status_code == 200:
                        fname = f"img_{len(local_imgs)}.jpg"
                        with open(fname, "wb") as f: f.write(r.content)
                        local_imgs.append(fname)
        except: continue

    if len(local_imgs) < 5: return None, []

    # Optimized Rendering for Telegram (720p HD)
    img_dur = actual_duration / len(local_imgs)
    clips = [ImageClip(p).set_duration(img_dur + 0.6).set_fps(10).resize(width=1280).fx(resize, lambda t: 1 + 0.02 * t).crossfadein(0.6) if i > 0 else ImageClip(p).set_duration(img_dur + 0.6).set_fps(10).resize(width=1280).fx(resize, lambda t: 1 + 0.02 * t) for i, p in enumerate(local_imgs)]
    
    final_video = concatenate_videoclips(clips, method="compose", padding=-0.6)
    final_video = final_video.set_audio(final_audio).set_duration(actual_duration)
    
    output = "knews_2026_delivery_fix.mp4"
    # Bitrate ကို လျှော့ပြီး Telegram အတွက် optimize လုပ်ပါတယ်
    final_video.write_videofile(output, fps=10, codec="libx264", bitrate="2500k", audio_codec="aac", logger=None)
    
    audio.close()
    return output, local_imgs

async def main():
    print("🚀 Launching V9.8 (Telegram Delivery Fix)...")
    try:
        path, imgs = await make_v9_8_video()
        if not path: return

        # Telegram Upload with Error Handling
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(path, "rb") as v:
            res = requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 K-News Today: 2026 Special Broadcast"})
            print(f"📡 Telegram Response: {res.status_code} - {res.text}")

        os.remove(path); os.remove("voice.mp3")
        for img in imgs: os.remove(img)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

