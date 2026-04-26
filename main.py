import os
import sys
import subprocess

# --- AUTO INSTALLER ---
def install_package(package):
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

for lib in ["google-generativeai", "edge-tts", "moviepy", "requests", "nest_asyncio"]:
    install_package(lib)

import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
import google.generativeai as genai
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VOICE = "en-US-AndrewNeural"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_long_trending_news():
    # ဒီမှာ Prompt ကို အသေအချာ ပြင်ထားပါတယ် (စာလုံးရေ ၃၀၀ ကျော်ရမယ်လို့ အမိန့်ပေးထားပါတယ်)
    prompt = """
    Write a VERY LONG and DETAILED news report for a 2-minute video. 
    The topic is 'Top 2 K-Entertainment Trends of April 2026'.
    Requirement:
    1. The script MUST be at least 350 words long to cover 2 minutes of speaking time.
    2. Write in a storytelling broadcast style.
    3. Provide 8 specific Pexels search keywords for these stories.
    Format exactly:
    STORY: [Your very long detailed 350-word story here]
    TAGS: [kw1, kw2, kw3, kw4, kw5, kw6, kw7, kw8]
    """
    try:
        response = model.generate_content(prompt).text
        story = response.split("STORY:")[1].split("TAGS:")[0].strip()
        tags_raw = response.split("TAGS:")[1].strip().replace("[","").replace("]","")
        tags = [t.strip() for t in tags_raw.split(",")]
        return story, tags
    except:
        return "Please check the script generation logic.", ["kpop", "seoul"]

async def make_video():
    target_duration = 120
    print("🧠 Requesting a LONG 2-minute script from Gemini...")
    story_text, keywords = get_long_trending_news()
    
    print(f"📝 Script Length: {len(story_text.split())} words.")
    
    # စာသားက ၂ မိနစ်အတွက် တိုနေသေးရင် ထပ်ခါတလဲလဲ ပေါင်းပေးမယ့် logic
    words_count = len(story_text.split())
    if words_count < 280: # ၂ မိနစ်စာအတွက် အနည်းဆုံး စာလုံး ၃၀၀ နီးပါး လိုပါတယ်
        print("⚠️ Script too short, looping content to fill 2 minutes...")
        final_script = (story_text + " ") * 2
    else:
        final_script = story_text

    # Audio
    print("🎙️ Generating Audio...")
    await edge_tts.Communicate(final_script, VOICE).save("voice.mp3")
    audio = AudioFileClip("voice.mp3")
    
    # အကယ်၍ Gemini က အရှည်ကြီးပေးလာလို့ ၂ မိနစ်ထက် ကျော်သွားရင်လည်း ဖြတ်လိုက်မယ်
    # တိုနေရင်လည်း ၁၂၀ အထိ ပြည့်အောင် လုပ်မယ်
    if audio.duration > target_duration:
        audio = audio.subclip(0, target_duration)
        final_duration = target_duration
    else:
        final_duration = audio.duration
        print(f"ℹ️ Final video will be {final_duration} seconds.")

    # Images (Keywords ကို ၈ ခုထိ တိုးထားလို့ ပုံတွေ ပိုစုံလာပါမယ်)
    print(f"🔎 Pexels Keywords: {keywords}")
    headers = {"Authorization": PEXELS_API_KEY}
    all_urls = []
    for kw in keywords:
        url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(kw)}&per_page=2&orientation=landscape"
        try:
            res = requests.get(url, headers=headers).json()
            all_urls.extend([p['src']['large'] for p in res.get('photos', [])])
        except: continue
    
    local_imgs = []
    for i, url in enumerate(all_urls[:15]): # ပုံ ၁၅ ပုံထိ တိုးယူမယ်
        fname = f"img_{i}.jpg"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            with open(fname, "wb") as f: f.write(res.content)
            local_imgs.append(fname)
            
    if not local_imgs: return None
        
    # Clips & Render
    sec_per_img = final_duration / len(local_imgs)
    clips = [ImageClip(p).set_duration(sec_per_img).resize(newsize=(640, 360)).set_fps(8) for p in local_imgs]
    
    print("🎬 Rendering Final Video...")
    video = concatenate_videoclips(clips, method="chain").set_audio(audio)
    video.write_videofile("trend_2min.mp4", fps=8, codec="libx264", bitrate="500k", logger=None)
    
    audio.close()
    return "trend_2min.mp4", local_imgs, story_text

async def main():
    print("🚀 Starting 2-Minute Production...")
    try:
        result = await make_video()
        if result:
            path, imgs, story = result
            print("📤 Sending to Telegram...")
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 2-Minute Smart News"})
            
            # Cleanup
            os.remove(path)
            os.remove("voice.mp3")
            for img in imgs: os.remove(img)
            print("✅ Done!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

