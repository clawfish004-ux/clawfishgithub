import os
import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
VOICE = "en-US-AndrewNeural"

# သတင်းတစ်ပုဒ်စာ စာသား (၁ မိနစ်စာအတွက်)
STORY_TEXT = """
Welcome to your daily K-Entertainment update. Today's main story focuses on the 
extraordinary global success of South Korean artists in 2026. From record-breaking 
music charts to massive worldwide tours, K-pop continues to influence the world. 
Stay tuned as we bring you more exclusive news and behind-the-scenes updates 
from your favorite idols and actors. Thank you for watching.
"""

def get_pexels_images(query):
    headers = {"Authorization": PEXELS_API_KEY}
    # ပုံ ၆ ပုံပဲ ယူပါမယ်
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page=6&orientation=landscape"
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        # Medium size က Render လုပ်ရတာ အမြန်ဆုံးပါ
        return [p['src']['medium'] for p in res.get('photos', [])]
    except:
        return []

async def make_light_video():
    target_duration = 60 # ၁ မိနစ် (စက္ကန့် ၆၀)
    
    # 1. Audio Generation
    audio_file = "news_1min.mp3"
    print("🎙️ Generating Audio...")
    await edge_tts.Communicate(STORY_TEXT, VOICE).save(audio_file)
    
    audio = AudioFileClip(audio_file)
    # အသံကို စက္ကန့် ၆၀ ပြည့်အောင် loop ပတ်မယ် (သို့မဟုတ်) လိုသလောက်ယူမယ်
    if audio.duration < target_duration:
        # အသံတိုနေရင် စာသားထပ်ပေါင်းပြီး ပြန်ထုတ်ပါမယ်
        await edge_tts.Communicate(STORY_TEXT * 2, VOICE).save(audio_file)
        audio = AudioFileClip(audio_file)
    
    audio = audio.subclip(0, target_duration)
    
    # 2. Image Fetching
    print("📸 Fetching Images...")
    all_urls = get_pexels_images("kpop idol performance")
    if not all_urls:
        all_urls = ["https://images.pexels.com/photos/2307221/pexels-photo-2307221.jpeg"]
        
    # 3. Clip Creation
    sec_per_img = target_duration / len(all_urls)
    clips = []
    
    for url in all_urls:
        # FPS ကို ၈ ပဲထားပြီး Render ကို ပေါ့ပါးအောင်လုပ်မယ်
        img_clip = ImageClip(url).set_duration(sec_per_img).resize(newsize=(640, 360)).set_fps(8)
        clips.append(img_clip)
        
    # 4. Final Video Construction
    print("🎬 Stitching video parts...")
    video = concatenate_videoclips(clips, method="chain")
    video = video.set_audio(audio)
    
    output = "knews_1min.mp4"
    # Bitrate ကို လျှော့ချပြီး Render မြန်အောင် လုပ်မယ်
    video.write_videofile(output, fps=8, codec="libx264", bitrate="600k", threads=4, logger=None)
    
    audio.close()
    return output

async def main():
    print("🚀 Starting 1-Minute Production...")
    try:
        path = await make_light_video()
        if os.path.exists(path):
            print("📤 Sending to Telegram...")
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 1-Minute K-News (Daily)"})
            
            # Cleanup
            os.remove(path)
            if os.path.exists("news_1min.mp3"): os.remove("news_1min.mp3")
            print("✅ Done!")
    except Exception as e:
        print(f"❌ Error Detail: {e}")

if __name__ == "__main__":
    asyncio.run(main())

