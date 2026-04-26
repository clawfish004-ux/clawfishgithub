import os
import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
import google.generativeai as genai
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image

# PIL fix
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else 1

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VOICE = "en-US-AndrewNeural"

# Gemini Setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash') # ပိုမြန်တဲ့ flash model သုံးလိုက်ပါမယ်

def get_trending_knews():
    prompt = """
    Today is April 26, 2026. Act as a K-Entertainment reporter. 
    1. Write 2 trending news stories about Korean celebrities (Total 120 words).
    2. Provide 6 search keywords for Pexels to match these stories (focus on actors/idols).
    Format the response EXACTLY like this:
    STORY: [The stories]
    TAGS: [kw1, kw2, kw3, kw4, kw5, kw6]
    """
    try:
        response = model.generate_content(prompt).text
        # Parsing logic ကို ပိုခိုင်မာအောင်လုပ်မယ်
        story = response.split("STORY:")[1].split("TAGS:")[0].strip()
        tags = response.split("TAGS:")[1].strip().replace("[","").replace("]","").split(",")
        return story, [t.strip() for t in tags]
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "New K-pop global tour announced for 2026.", ["korean idol", "seoul", "stage"]

def get_pexels_urls(keywords):
    headers = {"Authorization": PEXELS_API_KEY}
    urls = []
    for kw in keywords:
        url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(kw)}&per_page=2&orientation=landscape"
        try:
            res = requests.get(url, headers=headers, timeout=15).json()
            urls.extend([p['src']['large'] for p in res.get('photos', [])])
        except: continue
    return urls[:12]

async def make_2min_video():
    target_duration = 120 
    
    print("🧠 Gemini is fetching trends...")
    story_text, keywords = get_trending_knews()
    final_script = (story_text + " ") * 2 
    
    # 1. Audio
    audio_file = "voice.mp3"
    await edge_tts.Communicate(final_script, VOICE).save(audio_file)
    audio = AudioFileClip(audio_file).subclip(0, target_duration)
    
    # 2. Images
    print(f"🔎 Pexels Keywords: {keywords}")
    urls = get_pexels_urls(keywords)
    local_images = []
    for i, url in enumerate(urls):
        fname = f"img_{i}.jpg"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            with open(fname, "wb") as f: f.write(res.content)
            local_images.append(fname)
            
    if not local_images: return None
        
    # 3. Clips & Render
    sec_per_img = target_duration / len(local_images)
    clips = [ImageClip(p).set_duration(sec_per_img).resize(newsize=(640, 360)).set_fps(8) for p in local_images]
    
    print("🎬 Rendering...")
    video = concatenate_videoclips(clips, method="chain").set_audio(audio)
    output = "final.mp4"
    video.write_videofile(output, fps=8, codec="libx264", bitrate="500k", threads=2, logger=None)
    
    audio.close()
    return output, local_images, story_text

async def main():
    print("🚀 Starting Production...")
    try:
        result = await make_2min_video()
        if result:
            path, imgs, story = result
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
            with open(path, "rb") as v:
                requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🇰🇷 {story[:100]}..."})
            
            # Cleanup
            os.remove(path)
            os.remove("voice.mp3")
            for img in imgs: os.remove(img)
            print("✅ Done!")
    except Exception as e:
        print(f"❌ Main Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

