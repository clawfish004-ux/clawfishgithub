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
from PIL import Image

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else 1

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# ကိုကို့ရဲ့ Secret နာမည်ကို Environment မှာပါ သတ်မှတ်ပေးလိုက်မယ် (OpenAI SDK အတွက်)
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_O4_MINI", "")
VOICE = "en-US-AndrewNeural"

def get_smart_long_news():
    prompt = """
    Create a very long, detailed 2-minute professional news broadcast about South Korean celebrity trends.
    The story content MUST be at least 400 words. Provide 8 Pexels keywords.
    Format:
    STORY: [The content]
    TAGS: [kw1, kw2, kw3, kw4, kw5, kw6, kw7, kw8]
    """
    
    # ၁။ Gemini အသစ် (gemini-3-flash) ကို စမ်းမယ်
    print("🧠 Trying Gemini (3-Flash)...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # ၂၀၂၆ အတွက် Model နာမည်ကို update လုပ်ထားပါတယ်
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        response = model.generate_content(prompt)
        if "STORY:" in response.text:
            print("✅ Gemini Success!")
            return parse_output(response.text)
    except Exception as e:
        print(f"⚠️ Gemini skipped/failed: {e}")

    # ၂။ OpenAI (o4-mini သို့မဟုတ် gpt-5.5-preview)
    print("🤖 Switching to OpenAI...")
    try:
        client = OpenAI() # OS environment ကနေ auto ယူပါလိမ့်မယ်
        response = client.chat.completions.create(
            model="o4-mini", 
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content
        print("✅ OpenAI Success!")
        return parse_output(text)
    except Exception as e:
        print(f"❌ OpenAI Error: {e}")
        return "Breaking news from Seoul. " * 50, ["kpop", "seoul"]

def parse_output(text):
    try:
        story = text.split("STORY:")[1].split("TAGS:")[0].strip()
        tags = text.split("TAGS:")[1].strip().replace("[","").replace("]","").split(",")
        return story, [t.strip() for t in tags]
    except:
        return "New K-pop trends update.", ["korean idol", "seoul"]

async def make_video():
    target_duration = 120
    story_text, keywords = get_smart_long_news()
    
    # အသံဖိုင်လုပ်ခြင်း
    await edge_tts.Communicate(story_text, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    final_audio = audio.subclip(0, min(audio.duration, target_duration))
    
    # ပုံများရှာခြင်း
    local_imgs = []
    headers = {"Authorization": PEXELS_API_KEY}
    for kw in keywords:
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
        
    sec_per_img = final_audio.duration / len(local_imgs)
    clips = [ImageClip(p).set_duration(sec_per_img).set_fps(8).resize(width=640) for p in local_imgs]
    
    video = concatenate_videoclips(clips, method="chain").set_audio(final_audio)
    video.write_videofile("news_v4.mp4", fps=8, codec="libx264", bitrate="500k", logger=None)
    
    audio.close()
    return "news_v4.mp4", local_imgs, story_text

async def main():
    print("🚀 Starting Production (Stable Dual-AI)...")
    try:
        result = await make_video()
        if result:
            path, imgs, story = result
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🎬 K-News Today: {story[:100]}..."})
            
            os.remove(path); os.remove("voice.mp3")
            for img in imgs: os.remove(img)
            print("✅ All Done!")
    except Exception as e:
        print(f"❌ Main Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

