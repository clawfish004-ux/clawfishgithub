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

STORY_TEXT = """
Welcome to your daily K-Entertainment update for April 2026. Today's main story focuses on the 
extraordinary global success of South Korean artists. From record-breaking 
music charts to massive worldwide tours, K-pop continues to influence the world. 
Stay tuned as we bring you more exclusive news and behind-the-scenes updates 
from your favorite idols and actors. Thank you for watching.
"""

def download_image(url, filename):
    # Header ထည့်မှ 403 Forbidden Error မတက်မှာပါ
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Download Error: {e}")
    return False

def get_pexels_image_urls(query):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page=6&orientation=landscape"
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        return [p['src']['large'] for p in res.get('photos', [])]
    except:
        return []

async def make_light_video():
    target_duration = 60 
    
    # 1. Audio
    audio_file = "news_1min.mp3"
    print("🎙️ Generating Audio...")
    await edge_tts.Communicate(STORY_TEXT, VOICE).save(audio_file)
    audio = AudioFileClip(audio_file).subclip(0, target_duration)
    
    # 2. Images
    print("📸 Fetching & Downloading Images...")
    urls = get_pexels_image_urls("kpop concert")
    local_images = []
    
    for i, url in enumerate(urls):
        filename = f"img_{i}.jpg"
        if download_image(url, filename):
            local_images.append(filename)
            
    if not local_images:
        print("❌ No images downloaded.")
        return None
        
    # 3. Clips
    sec_per_img = target_duration / len(local_images)
    clips = []
    
    for img_path in local_images:
        # Resize လုပ်တဲ့အခါ error မတက်အောင် ImageClip ကို file ကနေ တိုက်ရိုက်ယူပါတယ်
        clip = ImageClip(img_path).set_duration(sec_per_img).resize(newsize=(640, 360)).set_fps(8)
        clips.append(clip)
        
    # 4. Final Render
    print("🎬 Rendering...")
    video = concatenate_videoclips(clips, method="chain")
    video = video.set_audio(audio)
    
    output = "knews_final.mp4"
    video.write_videofile(output, fps=8, codec="libx264", bitrate="600k", threads=4, logger=None)
    
    audio.close()
    return output, local_images

async def main():
    print("🚀 Starting Production with 403 Fix...")
    try:
        result = await make_light_video()
        if result:
            path, temp_imgs = result
            print("📤 Sending to Telegram...")
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 1-Minute K-News (Fixed)"})
            
            # Cleanup
            os.remove(path)
            os.remove("news_1min.mp3")
            for img in temp_imgs: os.remove(img)
            print("✅ Process Completed!")
    except Exception as e:
        print(f"❌ Error Detail: {e}")

if __name__ == "__main__":
    asyncio.run(main())

