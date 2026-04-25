import os
import asyncio
import requests
import nest_asyncio
import json
import time
import re
from google import genai
import edge_tts
from PIL import Image
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips

nest_asyncio.apply()

# Pillow compatibility fix
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

def clean_for_tts(text):
    """Unicode Error ကာကွယ်ရန် စာသားသန့်စင်ခြင်း"""
    # မြန်မာစာသားနှင့် ကိန်းဂဏန်းများမှလွဲ၍ ကျန်တာများကို ဖယ်ရှားပါသည်
    clean = re.sub(r'[^\u1000-\u109F\u0030-\u0039\s၊။\-]', '', text)
    return clean.strip()

async def get_news_data(topic):
    prompt = f"Write a 1-minute news story about {topic} in Burmese. JSON only: {{\"news\": \"text\", \"query\": \"keyword\"}}"
    try:
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except: return None

async def generate_audio_safe(text, filename):
    """Voice ၂ မျိုးစလုံးဖြင့် ၅ ကြိမ်အထိ အပြင်းအထန် ပြန်ကြိုးစားပေးမည့် logic"""
    voices = ["my-MM-NanDaNeural", "my-MM-ThihaNeural"]
    clean_text = clean_for_tts(text)
    
    for attempt in range(5):
        voice = voices[attempt % 2] # Voice အလှည့်ကျ ပြောင်းစမ်းခြင်း
        try:
            communicate = edge_tts.Communicate(clean_text, voice)
            await communicate.save(filename)
            
            if os.path.exists(filename) and os.path.getsize(filename) > 1000:
                return True
        except Exception as e:
            send_telegram_msg(f"⏳ TTS Attempt {attempt+1} ({voice}) failed. Retrying...")
            await asyncio.sleep(3)
    return False

async def create_one_minute_video(topic):
    try:
        data = await get_news_data(topic)
        if not data: return None
        
        audio_fn = f"news_audio_{int(time.time())}.mp3"
        
        # အသံဖိုင်ရအောင် အသေအချာ လုပ်ဆောင်ခြင်း
        if not await generate_audio_safe(data['news'], audio_fn):
            send_telegram_msg("❌ TTS Error: Microsoft Server နှင့် ချိတ်ဆက်၍ မရပါ။")
            return None
        
        # 2. Pexels Image Fetching
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=6", headers=headers).json()
        
        if 'photos' not in img_res or not img_res['photos']: return None

        # 3. Processing
        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"img_{i}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=1280) for m in img_paths]
        
        output_fn = "Final_One_Minute.mp4"
        final_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((1280, 720))
        final_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        final_video.close()
        return output_fn
    except Exception as e:
        send_telegram_msg(f"❌ Production Error: {str(e)}")
        return None

async def run_engine():
    send_telegram_msg("🚀 1-Minute Production: Advanced TTS & Resize Fix Active...")
    video = await create_one_minute_video("Advancement of AI in 2026")
    if video:
        send_telegram_msg(f"✅ Success! 1-Minute Video is Ready: {video}")

if __name__ == "__main__":
    asyncio.run(run_engine())

