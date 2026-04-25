import os
import asyncio
import requests
import nest_asyncio
import json
import time
import re
from google import genai
import edge_tts
# PIL error ကို ဖြေရှင်းရန် import လုပ်ပါသည်
from PIL import Image
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips

nest_asyncio.apply()

# Pillow version အသစ်များအတွက် ANTIALIAS ကို LANCZOS နှင့် အစားထိုးခြင်း
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)
YT_INTRO_FILE = "sunshineyt.mp4"

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

async def get_news_data(topic):
    prompt = f"Write a 1-minute news story about {topic} in Burmese. JSON only: {{\"news\": \"text\", \"query\": \"keyword\"}}"
    try:
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except: return None

async def create_one_minute_video(topic):
    try:
        data = await get_news_data(topic)
        if not data: return None
        
        # 1. TTS Logic (အသံရပြီမို့ အရင်အတိုင်း ထားပါတယ်)
        audio_fn = "news_audio.mp3"
        communicate = edge_tts.Communicate(data['news'], "my-MM-NanDaNeural")
        await communicate.save(audio_fn)
        
        # 2. Pexels Image Fetching
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=6", headers=headers).json()
        
        if 'photos' not in img_res or not img_res['photos']: return None

        # 3. Processing (ANTIALIAS Error ပြင်ဆင်ထားသည့်အပိုင်း)
        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"img_{i}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        duration = audio_clip.duration / len(img_paths)
        
        # Resize logic ကို တည်ငြိမ်အောင် ရေးသားခြင်း
        clips = []
        for m in img_paths:
            # Resize method ကို သေသေချာချာ သတ်မှတ်ပေးလိုက်ပါသည်
            clip = ImageClip(m).set_duration(duration).resize(width=1280)
            clips.append(clip)
        
        final_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((1280, 720))
        output_fn = "Final_One_Minute.mp4"
        final_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        final_video.close()
        return output_fn
    except Exception as e:
        send_telegram_msg(f"❌ Production Error: {str(e)}")
        return None

async def run_engine():
    send_telegram_msg("🚀 Fix Mode: Correcting PIL Resize Error...")
    topic = "Tech Revolution in Myanmar"
    video = await create_one_minute_video(topic)
    if video:
        send_telegram_msg(f"✅ Success! 1-Minute Video is Ready: {video}")

if __name__ == "__main__":
    asyncio.run(run_engine())

