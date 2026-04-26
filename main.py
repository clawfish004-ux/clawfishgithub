import os
import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image

# PIL version fix
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else 1

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
VOICE = "en-US-AndrewNeural"

STORY_TEXT = """
Welcome to your daily K-Entertainment update for April 2026. Today's main story focuses on the 
extraordinary global success of South Korean artists. From record-breaking 
music charts to massive worldwide tours, K-pop continues to influence the world. 
Stay tuned as we bring you more exclusive news and behind-the-scenes updates 
from your favorite idols and actors. Thank you for watching.
"""

def download_image(url, filename):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            return True
    except:
        return False

def get_pexels_image_urls(query):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page=6&orientation=landscape"
    try:
        res = requests.get(url, headers=headers, timeout=15).json()
        return [p['src']['large'] for p in res.get('photos', [])]
    except:
        return []

async def make_safe_video():
    # 1. Audio Generation
    audio_file = "news_voice.mp3"
    print("🎙️ Generating Audio...")
    await edge_tts.Communicate(STORY_TEXT, VOICE).save(audio_file)
    
    # Audio ရဲ့ အစစ်အမှန်ကြာချိန်ကို ယူမယ်
    audio = AudioFileClip(audio_file)
    actual_duration = audio.duration
    print(f"⏱️ Audio duration is {actual_duration} seconds.")
    
    # 2. Images
    print("📸 Fetching Images...")
    urls = get_pexels_image_urls("kpop stars")
    local_images = []
    for i, url in enumerate(urls):
        filename = f"img_{i}.jpg"
        if download_image(url, filename):
            local_images.append(filename)
            
    if not local_images:
        print("❌ No images found.")
        audio.close()
        return None
        
    # 3. Clips - အသံကြာချိန်ကို ပုံအရေအတွက်နဲ့ မျှလိုက်မယ်
    sec_per_img = actual_duration / len(local_images)
    clips = []
    for img_path in local_images:
        # FPS ကို ၈ ပဲထားမယ် (Render speed အတွက်)
        clip = ImageClip(img_path).set_duration(sec_per_img).resize(newsize=(640, 360)).set_fps(8)
        clips.append(clip)
        
    # 4. Final Render
    print("🎬 Rendering...")
    # method="chain" က memory အသက်သာဆုံးပါ
    video = concatenate_videoclips(clips, method="chain")
    video = video.set_audio(audio)
    
    output = "knews_final.mp4"
    video.write_videofile(output, fps=8, codec="libx264", bitrate="500k", threads=2, logger=None)
    
    audio.close()
    return output, local_images

async def main():
    print("🚀 Starting Production (Duration Fix Version)...")
    try:
        result = await make_safe_video()
        if result:
            path, temp_imgs = result
            print("📤 Sending to Telegram...")
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 K-News Daily Update"})
            
            # Cleanup
            os.remove(path)
            os.remove("news_voice.mp3")
            for img in temp_imgs: os.remove(img)
            print("✅ Successfully Finished!")
    except Exception as e:
        print(f"❌ Error Detail: {e}")

if __name__ == "__main__":
    asyncio.run(main())

