import os
import sys
import subprocess

# --- AUTO INSTALLER & FIXER ---
def install_and_fix():
    libs = ["google-generativeai", "openai", "edge-tts", "moviepy", "requests", "nest_asyncio", "Pillow==9.5.0"]
    for lib in libs:
        pkg = lib.split("==")[0]
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            print(f"📦 Installing {lib}...")
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
from PIL import Image

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else 1

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_O4_MINI") # GitHub Secret နာမည်
VOICE = "en-US-AndrewNeural"

# Gemini Config
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# OpenAI Config
client = OpenAI(api_key=OPENAI_API_KEY)

def get_smart_long_news():
    prompt = """
    Create a very long, detailed 2-minute professional news broadcast about South Korean celebrity trends in 2026.
    STRICT RULES:
    1. The story content MUST be at least 400 words long. 
    2. Provide 8 Pexels search keywords for images.
    Output format:
    STORY: [Your 400-word story here]
    TAGS: [kw1, kw2, kw3, kw4, kw5, kw6, kw7, kw8]
    """
    
    # ၁။ Gemini ကို အရင်စမ်းမယ်
    print("🧠 Trying Gemini for news content...")
    try:
        response = gemini_model.generate_content(prompt, generation_config={"temperature": 0.8})
        text = response.text
        if "STORY:" in text:
            print("✅ Gemini successfully generated the news.")
            return parse_output(text)
    except Exception as e:
        print(f"⚠️ Gemini failed: {e}")

    # ၂။ Gemini မရရင် OpenAI (o4-mini) ကို သုံးမယ်
    print("🤖 Gemini failed or limited. Switching to OpenAI (o4-mini)...")
    try:
        response = client.chat.completions.create(
            model="o4-mini", # ကိုကိုပေးထားတဲ့ နာမည်အတိုင်း သုံးထားပါတယ်
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content
        if "STORY:" in text:
            print("✅ OpenAI successfully generated the news.")
            return parse_output(text)
    except Exception as e:
        print(f"❌ Both AI Models failed: {e}")
        return "Breaking news from Seoul today. " * 50, ["kpop", "korean actor"]

def parse_output(text):
    try:
        story = text.split("STORY:")[1].split("TAGS:")[0].strip()
        tags = text.split("TAGS:")[1].strip().replace("[","").replace("]","").split(",")
        return story, [t.strip() for t in tags]
    except:
        return "Error in parsing AI response.", ["kpop", "seoul"]

async def make_video():
    target_duration = 120
    story_text, keywords = get_smart_long_news()
    
    if len(story_text.split()) < 300:
        story_text = (story_text + " ") * 2
        
    # Audio
    await edge_tts.Communicate(story_text, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    final_audio = audio.subclip(0, min(audio.duration, target_duration))
    actual_duration = final_audio.duration
    
    # Images
    print("📸 Downloading Images...")
    headers = {"Authorization": PEXELS_API_KEY}
    local_imgs = []
    for i, kw in enumerate(keywords):
        url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(kw)}&per_page=2&orientation=landscape"
        try:
            res = requests.get(url, headers=headers).json()
            for p in res.get('photos', []):
                fname = f"img_{len(local_imgs)}.jpg"
                r = requests.get(p['src']['large'], headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    with open(fname, "wb") as f: f.write(r.content)
                    local_imgs.append(fname)
        except: continue
    
    if not local_imgs: return None
        
    # Clips
    sec_per_img = actual_duration / len(local_imgs)
    clips = [ImageClip(p).set_duration(sec_per_img).set_fps(8).resize(width=640) for p in local_images]
    
    print(f"🎬 Rendering {actual_duration:.1f}s video...")
    video = concatenate_videoclips(clips, method="chain").set_audio(final_audio)
    video.write_videofile("news_final.mp4", fps=8, codec="libx264", bitrate="500k", logger=None)
    
    audio.close()
    return "news_final.mp4", local_imgs, story_text

async def main():
    print("🚀 Starting Production with Dual-AI Support...")
    try:
        result = await make_video()
        if result:
            path, imgs, story = result
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 2-Minute Smart News (Dual-AI Support)"})
            
            os.remove(path); os.remove("voice.mp3")
            for img in imgs: os.remove(img)
            print("✅ Completed!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

