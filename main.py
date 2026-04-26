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
    "title": "K-Entertainment Daily Update",
    "scenes": [
        {"text": "Breaking news: BTS solo comeback rumors spark excitement.", "query": "kpop stage"},
        {"text": "The latest K-drama Eternal Love breaks records.", "query": "korean drama"},
        {"text": "Lim Young-woong dominates music charts again.", "query": "korean singer"},
        {"text": "Blackpink members seen together at a private event.", "query": "kpop idol"},
        {"text": "Actor Lee Min-ho confirms lead role in new series.", "query": "korean actor"},
        {"text": "Behind the scenes of the most expensive K-drama.", "query": "movie set"},
        {"text": "Song Hye-kyo wins best actress at global awards.", "query": "red carpet"},
        {"text": "Trending: K-beauty products taking over the world.", "query": "skincare"},
        {"text": "New idol group debuts with massive fan following.", "query": "seoul night"},
        {"text": "Why K-culture is the most influential force in 2026.", "query": "korea fashion"}
    ]
}

def get_pexels_images(query, count=5):
    headers = {"Authorization": PEXELS_API_KEY}
    # Query ကို ပိုရှင်းအောင် encode လုပ်ပါတယ်
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page={count}&orientation=landscape"
    try:
        res = requests.get(url, headers=headers, timeout=15).json()
        urls = [p['src']['large2x'] for p in res.get('photos', [])]
        print(f"🔍 Found {len(urls)} images for '{query}'")
        return urls
    except Exception as e:
        print(f"⚠️ Pexels Error for '{query}': {e}")
        return []

async def make_long_knews_video():
    target_duration = 240 # 4 Minutes
    
    # 1. AUDIO GENERATION
    full_script = ". ".join([s['text'] for s in STORY_DATA['scenes']])
    # ၄ မိနစ် ပြည့်အောင် စာသားကို ချိန်ညှိပါတယ်
    words = full_script.split()
    needed_words = 150 * 4 # တစ်မိနစ် ၁၅၀ လုံးနှုန်းနဲ့ တွက်ထားပါတယ်
    extended_script = (full_script + " ") * (needed_words // len(words) + 1)
    
    audio_file = "long_knews.mp3"
    print("🎙️ Generating 4-minute Audio...")
    await edge_tts.Communicate(extended_script, VOICE).save(audio_file)
    
    audio = AudioFileClip(audio_file).subclip(0, target_duration)
    
    # 2. IMAGE FETCHING
    print("📸 Fetching Images...")
    all_image_urls = []
    for scene in STORY_DATA['scenes']:
        all_image_urls.extend(get_pexels_images(scene['query']))
    
    # ပုံ လုံးဝ ရှာမတွေ့ရင် fallback အနေနဲ့ ပုံသေ query တစ်ခုနဲ့ ထပ်ရှာမယ်
    if not all_image_urls:
        all_image_urls = get_pexels_images("korea kpop", count=10)
    
    # အခုမှ ပုံမရှိရင်တော့ ရပ်ပါမယ်
    if not all_image_urls:
        print("❌ Error: Absolutely no images found. Check API Key.")
        return None

    # 3. CLIP CREATION
    # ပုံအရေအတွက် ဘယ်လောက်ပဲရရ ၄ မိနစ်ပြည့်အောင် တွက်ချက်ပါတယ်
    sec_per_img = target_duration / len(all_image_urls)
    # တစ်ပုံကို အရမ်းမကြာအောင် ညှိပါတယ် (အများဆုံး ၁၀ စက္ကန့်)
    if sec_per_img > 10: sec_per_img = 10
    
    clips = []
    overlap = 0.8
    
    print(f"🎬 Creating clips for {len(all_image_urls)} images...")
    for url in all_image_urls:
        try:
            img_clip = (ImageClip(url)
                        .set_duration(sec_per_img + overlap)
                        .resize(lambda t: 1 + 0.03 * t)
                        .set_fps(24)
                        .resize(newsize=(640, 360))
                        .crossfadein(overlap))
            clips.append(img_clip)
        except Exception as e:
            continue
    
    if not clips: return None

    # 4. CONCATENATE
    video = concatenate_videoclips(clips, method="compose", padding=-overlap)
    # ဗီဒီယိုကြာချိန်ကို အသံနဲ့ ကွက်တိဖြစ်အောင် ညှိပါတယ်
    video = video.set_duration(target_duration).set_audio(audio)
    
    output = "knews_4min.mp4"
    video.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", bitrate="1000k", logger=None)
    
    audio.close()
    return output

async def main():
    print("🚀 Starting 4-Minute Production...")
    try:
        video_path = await make_long_knews_video()
        if video_path and os.path.exists(video_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(video_path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎬 4-Minute K-News Update"})
            os.remove(video_path)
            print("✅ Done!")
    except Exception as e:
        print(f"❌ Main Loop Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

