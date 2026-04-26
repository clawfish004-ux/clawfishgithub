import os
import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
import google.generativeai as genai
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image

# PIL fix for new versions
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else 1

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VOICE = "en-US-AndrewNeural"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# ၁။ Gemini ကို Trend ဖြစ်တဲ့ သတင်း ၂ ပုဒ်နဲ့ Keyword ထုတ်ခိုင်းခြင်း
def get_trending_knews():
    prompt = """
    Today is April 26, 2026. Act as a K-Entertainment reporter. 
    1. Provide 2 trending news stories about Korean celebrities (approx 150 words total).
    2. Provide 6 search keywords for Pexels to match these stories (focus on actors/idols).
    Format the response exactly like this:
    NEWS: [The stories here]
    KEYWORDS: [kw1, kw2, kw3, kw4, kw5, kw6]
    """
    try:
        response = model.generate_content(prompt).text
        news_part = response.split("NEWS:")[1].split("KEYWORDS:")[0].strip()
        keywords_part = response.split("KEYWORDS:")[1].strip().replace("[","").replace("]","").split(",")
        return news_part, [k.strip() for k in keywords_part]
    except:
        # Fallback in case of AI error
        return "BTS and Blackpink dominate the global music charts in 2026.", ["kpop stage", "korean singer", "seoul fashion"]

def download_image(url, filename):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code == 200:
            with open(filename, "wb") as f: f.write(res.content)
            return True
    except: return False

def get_pexels_urls(keywords):
    headers = {"Authorization": PEXELS_API_KEY}
    urls = []
    for kw in keywords:
        url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(kw)}&per_page=2&orientation=landscape"
        try:
            res = requests.get(url, headers=headers).json()
            urls.extend([p['src']['large'] for p in res.get('photos', [])])
        except: continue
    return urls[:12] # ၂ မိနစ်စာအတွက် ပုံ ၁၂ ပုံလောက်ယူမယ်

async def make_2min_video():
    target_duration = 120 # ၂ မိနစ်
    
    # Get News & Keywords
    print("🧠 Gemini is picking the hottest trends...")
    story_text, keywords = get_trending_knews()
    # ၂ မိနစ်ပြည့်အောင် စာသားကို ၂ ခါပတ်မယ်
    final_script = (story_text + " ") * 2
    
    # 1. Audio
    audio_file = "trend_voice.mp3"
    await edge_tts.Communicate(final_script, VOICE).save(audio_file)
    audio = AudioFileClip(audio_file).subclip(0, target_duration)
    
    # 2. Images
    print(f"🔎 Searching Pexels for: {keywords}")
    urls = get_pexels_urls(keywords)
    local_images = []
    for i, url in enumerate(urls):
        fname = f"img_{i}.jpg"
        if download_image(url, fname): local_images.append(fname)
            
    if not local_images: return None
        
    # 3. Clips (၁ မိနစ်မှာ ပုံ ၆ ပုံနှုန်းဖြစ်သွားမယ်)
    sec_per_img = target_duration / len(local_images)
    clips = [ImageClip(p).set_duration(sec_per_img).resize(newsize=(640, 360)).set_fps(8) for p in local_images]
    
    # 4. Render
    print("🎬 Rendering 2-minute video...")
    video = concatenate_videoclips(clips, method="chain").set_audio(audio)
    output = "trend_2min.mp4"
    video.write_videofile(output, fps=8, codec="libx264", bitrate="500k", threads=2, logger=None)
    
    audio.close()
    return output, local_images, story_text

async def main():
    print("🚀 Starting 2-Minute Trend Video Production...")
    try:
        result = await make_2min_video()
        if result:
            path, imgs, story = result
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🇰🇷 Trending News:\n{story[:100]}..."})
            
            # Cleanup
            os.remove(path)
            os.remove("trend_voice.mp3")
            for img in imgs: os.remove(img)
            print("✅ 2-Minute Trend Video Done!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

