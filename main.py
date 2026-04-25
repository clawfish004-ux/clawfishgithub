import os
import asyncio
import requests
import nest_asyncio
import json
import time
from google import genai
from PIL import Image
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips

nest_asyncio.apply()

# Pillow version compatibility fix
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Gemini Client Setup
client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

async def create_news_with_gemini_voice(topic):
    try:
        # 1. Gemini ဆီကနေ သတင်း script ရော၊ အသံဖိုင် (Audio Bytes) ပါ တစ်ခါတည်း တောင်းပါတယ်
        # Gemini 3 Flash Preview ၏ Multimodal စွမ်းရည်ကို အသုံးပြုခြင်း
        prompt = f"Read this news in a professional Burmese voice: Write a 1-minute news story about {topic} in Burmese."
        
        audio_fn = "gemini_voice.mp3"
        # Gemini native speech generation logic (Preview API)
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config={"speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": "Aoede"}}}}
        )
        
        # အသံဖိုင်ကို သိမ်းဆည်းခြင်း
        with open(audio_fn, "wb") as f:
            f.write(response.audio) # Gemini ကနေ တိုက်ရိုက်ပြန်ပေးတဲ့ audio data

        # 2. သတင်းအချက်အလက် (JSON) ကို သီးသန့်ပြန်ထုတ်ယူခြင်း
        data_prompt = f"Summarize the previous news into a search keyword for images. Return ONLY JSON: {{\"query\": \"keyword\"}}"
        data_res = client.models.generate_content(model="gemini-3-flash-preview", contents=data_prompt)
        data = json.loads(data_res.text.replace("```json", "").replace("```", "").strip())

        # 3. Pexels Image Fetching
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=5", headers=headers).json()
        
        if 'photos' not in img_res or not img_res['photos']: return None

        # 4. Video Production
        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"img_{i}.jpg"
            with open(path, "wb") as f: f.write(img_data)
            img_paths.append(path)

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=1280) for m in img_paths]
        
        output_fn = "Gemini_Native_News.mp4"
        # 'CompositeVideoClip' error အတွက် set_size အစား size parameter ကို သုံးထားပါတယ်
        final_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip)
        final_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        final_video.close()
        return output_fn

    except Exception as e:
        send_telegram_msg(f"❌ Gemini Voice Error: {str(e)}")
        return None

async def run_engine():
    send_telegram_msg("🚀 Starting Production with Gemini 3 Native Voice...")
    video = await create_news_with_gemini_voice("Future of Tech in Myanmar 2026")
    if video:
        send_telegram_msg(f"✅ Success! Gemini Voice Video Ready: {video}")

if __name__ == "__main__":
    asyncio.run(run_engine())

