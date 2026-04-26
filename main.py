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

def get_k_entertainment_script():
    prompt = """
    Act as a professional K-News anchor for 'K-News Today'.
    Write a 3-minute detailed news script (700 words) about 3 SPECIFIC topics:
    1. A trending K-Drama or TV Series in 2026.
    2. A major K-Pop comeback or concert news (BTS, Blackpink, or NewJeans).
    3. News about a famous Korean actor or actress.
    
    STRICT RULE FOR IMAGES: Provide 20 keywords focusing on PEOPLE.
    Use keywords like: 'Korean actor on stage', 'Kpop idol dancing', 'Beautiful Korean woman portrait', 'Korean man fashion model', 'K-Drama filming set with people'.
    
    Format:
    STORY: [The 700-word script]
    TAGS: [kw1, kw2, ..., kw20]
    """
    print("🧠 Gemini 3 Flash is writing K-Entertainment news...")
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

async def make_v9_7_video():
    target_duration = 180 
    story_text, keywords = get_k_entertainment_script()
    
    await edge_tts.Communicate(story_text, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    actual_duration = min(audio.duration, target_duration)
    final_audio = audio.subclip(0, actual_duration)

    local_imgs = []
    # Dual-Engine Fetching focusing on PEOPLE
    for kw in keywords:
        if len(local_imgs) >= 35: break
        try:
            # Unsplash Search
            u_headers = {"Authorization": f"Client-ID {UNSPLASH_KEY}"}
            res = requests.get(f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(kw)}&per_page=3", headers=u_headers, timeout=5).json()
            for p in res.get('results', []):
                r = requests.get(p['urls']['regular'], timeout=10)
                if r.status_code == 200:
                    fname = f"img_{len(local_imgs)}.jpg"
                    with open(fname, "wb") as f: f.write(r.content)
                    local_imgs.append(fname)
            
            # Pexels Search (Backup)
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

    # Rendering Process
    img_dur = actual_duration / len(local_imgs)
    clips = []
    for i, p in enumerate(local_imgs):
        clip = ImageClip(p).set_duration(img_dur + 0.6).set_fps(12).resize(width=1920)
        clip = clip.fx(resize, lambda t: 1 + 0.02 * t) 
        if i > 0: clip = clip.crossfadein(0.6)
        clips.append(clip)
    
    final_video = concatenate_videoclips(clips, method="compose", padding=-0.6)
    final_video = final_video.set_audio(final_audio).set_duration(actual_duration)
    
    output = "knews_star_edition.mp4"
    final_video.write_videofile(output, fps=12, codec="libx264", bitrate="3500k", audio_codec="aac", logger=None)
    
    audio.close()
    return output, local_imgs

async def main():
    print("🚀 Launching V9.7 (K-Star & People Focus)...")
    try:
        path, imgs = await make_v9_7_video()
        if not path:
            print("❌ Failure: Could not find human-centric images.")
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(path, "rb") as v:
            requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "📺 K-News Today: Stars, Dramas & K-Pop Special (V9.7)"})
        
        os.remove(path); os.remove("voice.mp3")
        for img in imgs: os.remove(img)
        print("✅ Finished. Humans and Stars should appear now!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

