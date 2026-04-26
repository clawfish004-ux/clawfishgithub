import os
import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image

nest_asyncio.apply()

# --- PIL FIXED ---
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
VOICE = "en-US-AndrewNeural"

# ၄ မိနစ်စာအတွက် သတင်းခေါင်းစဉ်များစွာ ထည့်ထားပါတယ်
STORY_DATA = {
    "title": "K-Entertainment Mega Update (4-Minute Special)",
    "scenes": [
        {"text": "Breaking news: BTS V and RM's solo comeback rumors spark global excitement.", "query": "kpop star stage performance"},
        {"text": "The latest K-drama 'Eternal Love' breaks all-time viewership records on its first week.", "query": "korean drama cinema lighting"},
        {"text": "Lim Young-woong continues to dominate music charts for a record-breaking month.", "query": "korean singer concert microphone"},
        {"text": "Blackpink members seen together at a private event, fueling group comeback theories.", "query": "kpop idols red carpet fashion"},
        {"text": "Popular actor Lee Min-ho confirms lead role in an upcoming Netflix sci-fi series.", "query": "handsome korean actor professional"},
        {"text": "Behind the scenes of the most expensive K-drama ever produced in Jeju Island.", "query": "jeju island scenic filming location"},
        {"text": "Song Hye-kyo wins best actress at the international awards ceremony tonight.", "query": "korean actress award ceremony dress"},
        {"text": "Trending: How K-beauty products are taking over the US and European markets.", "query": "korean beauty skin care products"},
        {"text": "New idol group 'Supernova' debuts with a massive fan following in Seoul.", "query": "seoul city night lights kpop"},
        {"text": "Analysis: Why K-Entertainment is the most influential cultural force in 2026.", "query": "korean culture high quality background"}
    ]
}

# --- 1. PEXELS IMAGE FETCH ---
def get_pexels_images(query, count=4):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page={count}&orientation=landscape"
    try:
        res = requests.get(url, headers=headers).json()
        return [p['src']['large2x'] for p in res.get('photos', [])]
    except:
        return []

# --- 2. VIDEO ENGINE ---
async def make_long_knews_video():
    full_script = ". ".join([s['text'] for s in STORY_DATA['scenes']])
    # ၄ မိနစ် (၂၄၀ စက္ကန့်) ပြည့်အောင် စာသားကို ၃ ခါလောက် ထပ်ခါဖတ်ခိုင်းပါမယ်
    extended_script = (full_script + " ") * 3 
    
    audio_file = "long_knews.mp3"
    print("🎙️ Generating 4-minute Audio...")
    await edge_tts.Communicate(extended_script, VOICE).save(audio_file)
    
    audio = AudioFileClip(audio_file)
    # အကယ်၍ audio က ၄ မိနစ်ထက် ကျော်ရင် ဖြတ်လိုက်မယ်၊ လိုရင် ထပ်ဖြည့်မယ်
    target_duration = 240 # 4 Minutes
    audio = audio.subclip(0, target_duration)
    
    print(f"📸 Fetching Images to match {target_duration} seconds...")
    
    # ပုံ ၄၀ လောက် သုံးပါမယ် (တစ်ပုံကို ၆ စက္ကန့်နှုန်း)
    all_images = []
    for scene in STORY_DATA['scenes']:
        all_images.extend(get_pexels_images(scene['query'], count=4))
    
    if not all_images:
        print("Error: No images found.")
        return None

    sec_per_img = target_duration / len(all_images)
    clips = []
    
    for img_url in all_images:
        try:
            img_clip = (ImageClip(img_url)
                        .set_duration(sec_per_img)
                        .resize(lambda t: 1 + 0.03 * t) # Slow & Smooth Zoom
                        .set_fps(24)
                        .resize(newsize=(640, 360))
                        .crossfadein(0.8))
            clips.append(img_clip)
        except:
            continue
            
    print("🎬 Stitching video clips together...")
    video = concatenate_videoclips(clips, method="compose", padding=-0.8)
    video = video.set_audio(audio)
    
    output = "knews_4min.mp4"
    video.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", bitrate="1200k", logger=None)
    
    audio.close()
    return output

# --- MAIN ---
async def main():
    print("🚀 Starting 4-Minute K-News Production...")
    video_path = await make_long_knews_video()
    
    if video_path and os.path.exists(video_path):
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(video_path, "rb") as v:
            requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 K-Entertainment Mega Update\nDuration: 4:00 Minutes"})
        
        # Cleanup
        os.remove(video_path)
        if os.path.exists("long_knews.mp3"): os.remove("long_knews.mp3")
        print("✅ 4-Minute Video Sent Successfully!")

if __name__ == "__main__":
    asyncio.run(main())

