import os
import asyncio
import requests
import nest_asyncio
import json
import time
import re
from google import genai
import edge_tts
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips

nest_asyncio.apply()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Gemini 3 Flash Preview Client
client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

def clean_text_for_tts(text):
    # edge-tts error မတက်အောင် special characters များကို ရှင်းထုတ်ခြင်း
    return re.sub(r'[*#_`]', '', text)

async def get_news_data(topic):
    prompt = f"Write a professional 1-minute news story about {topic} in Burmese. JSON only: {{\"news\": \"text content\", \"query\": \"english search term\"}}"
    try:
        # gemini-3-flash-preview ကို အသုံးပြုထားပါသည်
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        send_telegram_msg(f"❌ Gemini Error: {str(e)}")
        return None

async def create_one_minute_video(topic):
    try:
        data = await get_news_data(topic)
        if not data: return None
        
        # 1. TTS Generation (edge-tts ကိုသာ အသုံးပြုသည်)
        audio_fn = "test_audio.mp3"
        tts_text = clean_text_for_tts(data['news'])
        communicate = edge_tts.Communicate(tts_text, "my-MM-NanDaNeural")
        await communicate.save(audio_fn)
        
        if not os.path.exists(audio_fn):
            send_telegram_msg("❌ TTS Failed: Audio file not created.")
            return None

        # 2. Image Search (Pexels)
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=5", headers=headers).json()
        
        if 'photos' not in img_res or not img_res['photos']:
            send_telegram_msg(f"⚠️ No images for: {data['query']}")
            return None

        # 3. Video Composition
        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"img_{i}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=1280).set_position("center") for m in img_paths]
        
        final_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((1280, 720))
        output_fn = "One_Minute_Production.mp4"
        final_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        final_video.close()
        return output_fn
    except Exception as e:
        send_telegram_msg(f"❌ Production Error: {str(e)}")
        return None

async def run_test():
    try:
        send_telegram_msg("🚀 Engine Active: Starting 1-Minute Clean Test...")
        video_file = await create_one_minute_video("Advancements in Medicine 2026")
        
        if video_file:
            send_telegram_msg(f"✅ Success! Video created: {video_file}")
        else:
            send_telegram_msg("❌ Production Failed.")
    except Exception as e:
        send_telegram_msg(f"❌ Fatal Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_test())

