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
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip
from moviepy.video.fx.all import resize
from PIL import Image

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else 1

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_O4_MINI", "")
VOICE = "en-US-AndrewNeural"

def get_3min_news():
    # Intro 'K-News Today' ကို အတင်းထည့်ခိုင်းထားပါတယ်
    prompt = """
    Act as a professional news anchor for 'K-News Today' channel.
    Write a 3-minute news script covering 3 major trending topics in the Korean Entertainment industry for April 2026.
    
    STRICT RULES:
    1. Start the script with: 'Welcome to K-News Today, your daily source for the latest in Korean entertainment.'
    2. The total story content MUST be around 550-600 words to cover 3 minutes.
    3. Clearly separate the 3 topics with detailed descriptions.
    4. Provide 15 high-quality Pexels keywords for image search.
    
    Format:
    STORY: [The 600-word script]
    TAGS: [kw1, kw2, kw3, ..., kw15]
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash') 
        response = model.generate_content(prompt, generation_config={"temperature": 0.8})
        return parse_output(response.text)
    except:
        try:
            client = OpenAI()
            response = client.chat.completions.create(model="o1-mini", messages=[{"role": "user", "content": prompt}])
            return parse_output(response.choices[0].message.content)
        except:
            return "Welcome to K-News Today. " + ("Latest updates on Korean stars. " * 60), ["kpop idols", "korean drama", "seoul fashion"]

def parse_output(text):
    story = text.split("STORY:")[1].split("TAGS:")[0].strip()
    tags = text.split("TAGS:")[1].strip().replace("[","").replace("]","").split(",")
    return story, [t.strip() for t in tags]

def apply_ken_burns(clip, duration):
    # Smooth Zoom-in Effect
    return clip.fx(resize, lambda t: 1 + 0.03 * t)

async def make_3min_video():
    target_duration = 180 # ၃ မိနစ်
    print("🧠 K-News Today is drafting the 3-minute report...")
    story_text, keywords = get_3min_news()
    
    # Audio Generation
    await edge_tts.Communicate(story_text, VOICE).save("voice_3min.mp3")
    audio = AudioFileClip("voice_3min.mp3")
    
    # ၃ မိနစ် အတိဖြစ်အောင် ညှိမယ် (တိုနေရင် loop ပတ်မယ်)
    if audio.duration < target_duration:
        from moviepy.video.fx.all import loop
        final_audio = audio.subclip(0, audio.duration) # အသံအတိုင်းပဲယူမယ် (သို့) loop ပတ်မယ်
        actual_duration = audio.duration
    else:
        final_audio = audio.subclip(0, target_duration)
        actual_duration = target_duration

    # Images (၃၀ ပုံ ရအောင် Keyword တစ်ခုကို ၂ ပုံနှုန်း ယူမယ်)
    print("📸 Downloading 30 Professional Images...")
    local_imgs = []
    headers = {"Authorization": PEXELS_API_KEY}
    for kw in keywords:
        if len(local_imgs) >= 30: break
        url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(kw)}&per_page=3&orientation=landscape"
        try:
            res = requests.get(url, headers=headers).json()
            for p in res.get('photos', []):
                if len(local_imgs) >= 30: break
                fname = f"img_{len(local_imgs)}.jpg"
                r = requests.get(p['src']['large'], headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    with open(fname, "wb") as f: f.write(r.content)
                    local_imgs.append(fname)
        except: continue

    # Clips Processing with Transitions
    print(f"🎬 Processing {len(local_imgs)} clips with Zoom & Crossfade...")
    img_duration = actual_duration / len(local_imgs)
    clips = []
    
    for i, p in enumerate(local_imgs):
        # ၀.၅ စက္ကန့်စီ overlap လုပ်ဖို့ duration ကို နည်းနည်းတိုးထားမယ်
        clip = ImageClip(p).set_duration(img_duration + 0.5).set_fps(8).resize(width=1280)
        clip = apply_ken_burns(clip, img_duration)
        
        if i > 0:
            clip = clip.crossfadein(0.5) # Crossfade effect
        clips.append(clip)
    
    final_video = concatenate_videoclips(clips, method="compose", padding=-0.5)
    final_video = final_video.set_audio(final_audio).set_duration(actual_duration)
    
    output_name = "knews_3min.mp4"
    print(f"🚀 Final Rendering of {actual_duration:.1f}s video...")
    final_video.write_videofile(output_name, fps=8, codec="libx264", bitrate="1200k", threads=4, logger=None)
    
    audio.close()
    return output_name, local_imgs

async def main():
    print("🔥 Starting K-News Today (V6 - 3 Minute Special)...")
    try:
        path, imgs = await make_3min_video()
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(path, "rb") as v:
            requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "📺 K-News Today: 3-Minute Special Broadcast"})
        
        # Cleanup
        os.remove(path); os.remove("voice_3min.mp3")
        for img in imgs: os.remove(img)
        print("✅ Broadcast Success!")
    except Exception as e:
        print(f"❌ V6 Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

