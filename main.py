import os
import sys
import subprocess

# --- AUTO INSTALLER ---
def install_and_fix():
    # Pillow 9.5.0 က ANTIALIAS error အတွက် အသေချာဆုံးမို့ သူ့ကိုပဲ ဆက်သုံးပါမယ်
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
# ကိုကို့ရဲ့ Secret နာမည်အတိုင်း ပြန်ယူထားပါတယ်
MY_OPENAI_KEY = os.getenv("OPENAI_O4_MINI") 
VOICE = "en-US-AndrewNeural"

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
    
    # ၁။ Gemini အရင်စမ်းမယ်
    print("🧠 Trying Gemini...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        text = response.text
        if "STORY:" in text:
            return parse_output(text)
    except Exception as e:
        print(f"⚠️ Gemini skipped: {e}")

    # ၂။ OpenAI (o4-mini) ဘက်ကူးမယ်
    print("🤖 Switching to OpenAI (o4-mini)...")
    try:
        # ဒီနေရာမှာ Key ကို တိုက်ရိုက်ထည့်ပေးလိုက်လို့ Error မတက်တော့ပါဘူး
        client = OpenAI(api_key=MY_OPENAI_KEY)
        response = client.chat.completions.create(
            model="o1-mini", # OpenAI ရဲ့ နာမည်မှန်က o1-mini သို့မဟုတ် o3-mini ဖြစ်နိုင်လို့ စစ်ပေးပါ
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content
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
        return "Long news update about K-pop.", ["kpop", "korean actor"]

async def make_video():
    target_duration = 120
    story_text, keywords = get_smart_long_news()
    
    if len(story_text.split()) < 300:
        story_text = (story_text + " ") * 2
        
    await edge_tts.Communicate(story_text, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    final_audio = audio.subclip(0, min(audio.duration, target_duration))
    
    print("📸 Fetching Pexels Images...")
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
    
    print("🎬 Rendering...")
    video = concatenate_videoclips(clips, method="chain").set_audio(final_audio)
    video.write_videofile("final.mp4", fps=8, codec="libx264", bitrate="500k", logger=None)
    
    audio.close()
    return "final.mp4", local_imgs, story_text

async def main():
    print("🚀 Starting Production (Fixed Key Logic)...")
    try:
        result = await make_video()
        if result:
            path, imgs, story = result
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 2-Minute Smart News"})
            
            os.remove(path); os.remove("voice.mp3")
            for img in imgs: os.remove(img)
            print("✅ Success!")
    except Exception as e:
        print(f"❌ Main Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

