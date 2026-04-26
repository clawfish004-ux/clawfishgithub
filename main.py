import os
import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image

nest_asyncio.apply()

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
VOICE = "en-US-AndrewNeural"

STORY_DATA = {
    "title": "K-Update Daily (2-Minute Edition)",
    "scenes": [
        {"text": "Breaking news: BTS solo project rumors are taking over social media.", "query": "kpop group stage"},
        {"text": "The latest K-drama hit is breaking records on global streaming platforms.", "query": "korean drama movie"},
        {"text": "Lim Young-woong maintains his top spot on music charts for weeks.", "query": "korean singer"},
        {"text": "Blackpink members spotted together, sparking comeback rumors.", "query": "kpop stars red carpet"},
        {"text": "Top Korean actors confirmed for a new high-budget action series.", "query": "korean actor handsome"},
        {"text": "New fashion trends from Seoul are influencing global markets this year.", "query": "korean fashion style"},
        {"text": "A famous celebrity couple announces their wedding date officially.", "query": "korean wedding"},
        {"text": "Fan meetings are back in full swing across major Asian cities.", "query": "fan meeting audience"},
    ]
}

def get_pexels_images(query, count=3):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page={count}&orientation=landscape"
    try:
        res = requests.get(url, headers=headers, timeout=15).json()
        return [p['src']['large2x'] for p in res.get('photos', [])]
    except:
        return []

async def make_2min_knews_video():
    target_duration = 120 # 2 Minutes
    
    # 1. AUDIO GENERATION
    full_script = ". ".join([s['text'] for s in STORY_DATA['scenes']])
    # ၂ မိနစ် ပြည့်အောင် script ကို ၂ ခါ ပတ်ခိုင်းပါမယ်
    extended_script = (full_script + " ") * 2
    
    audio_file = "knews_2min.mp3"
    print("🎙️ Generating 2-minute Audio...")
    await edge_tts.Communicate(extended_script, VOICE).save(audio_file)
    
    audio = AudioFileClip(audio_file).subclip(0, target_duration)
    
    # 2. IMAGE FETCHING
    print("📸 Fetching Images for 2 minutes...")
    all_image_urls = []
    for scene in STORY_DATA['scenes']:
        all_image_urls.extend(get_pexels_images(scene['query']))
    
    if not all_image_urls:
        all_image_urls = get_pexels_images("korea kpop", count=10)
    
    if not all_image_urls:
        print("❌ Error: No images found.")
        return None

    # 3. CLIP CREATION
    sec_per_img = target_duration / len(all_image_urls)
    clips = []
    overlap = 0.8
    
    print(f"🎬 Creating clips for {len(all_image_urls)} images...")
    for url in all_image_urls:
        try:
            img_clip = (ImageClip(url)
                        .set_duration(sec_per_img + overlap)
                        .resize(lambda t: 1 + 0.04 * t) # Zoom Effect
                        .set_fps(24)
                        .resize(newsize=(640, 360))
                        .crossfadein(overlap))
            clips.append(img_clip)
        except:
            continue
    
    if not clips: return None

    # 4. CONCATENATE
    video = concatenate_videoclips(clips, method="compose", padding=-overlap)
    video = video.set_duration(target_duration).set_audio(audio)
    
    output = "knews_2min.mp4"
    video.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", bitrate="1000k", logger=None)
    
    audio.close()
    return output

async def main():
    print("🚀 Starting 2-Minute Production...")
    try:
        video_path = await make_2min_knews_video()
        if video_path and os.path.exists(video_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(video_path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 K-News Daily (2-Minute Edition)"})
            os.remove(video_path)
            print("✅ 2-Minute Video Sent!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

