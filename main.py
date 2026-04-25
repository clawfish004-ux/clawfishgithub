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

# --- Configuration (GitHub Secrets မှ ယူပါသည်) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try: requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

def clean_text(text):
    # အသံဖိုင်အတွက် စာသားကို သန့်စင်ခြင်း
    return re.sub(r'[^\u1000-\u109F\s၊။\-]', '', text).strip()

async def get_news_data(topic):
    # Gemini 3 Flash Preview အား အသုံးပြုခြင်း
    prompt = f"Write a professional 1-minute news story about {topic} in Burmese. Return ONLY JSON: {{\"news\": \"text content\", \"query\": \"english_keyword\"}}"
    try:
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except: return None

async def create_one_minute_video(topic):
    try:
        data = await get_news_data(topic)
        if not data: return None
        
        # 1. အသံဖိုင် ထုတ်ခြင်း (ThihaNeural ကို ဦးစားပေးသုံးထားသည်)
        audio_fn = "news_audio.mp3"
        tts_text = clean_text(data['news'])
        communicate = edge_tts.Communicate(tts_text, "my-MM-ThihaNeural")
        await communicate.save(audio_fn)
        
        if not os.path.exists(audio_fn): return None

        # 2. ပုံရှာဖွေခြင်း (Pexels)
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=6", headers=headers).json()
        
        # 3. ဗီဒီယို ဖန်တီးခြင်း
        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"img_{i}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=1280).set_position("center") for m in img_paths]
        
        output_name = "Burmese_News_1Min.mp4"
        final_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((1280, 720))
        final_video.write_videofile(output_name, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        return output_name
    except Exception as e:
        send_telegram_msg(f"❌ Production Error: {str(e)}")
        return None

async def main():
    send_telegram_msg("🚀 Producing 1-Minute News Video (Test Run)...")
    # ကိုကို့အတွက် စမ်းသပ်ရန် ခေါင်းစဉ် တစ်ခုတည်း
    topic = "Digital Economy in Myanmar 2026"
    
    video = await create_one_minute_video(topic)
    if video:
        send_telegram_msg(f"✅ Success! Video production complete: {video}")
    else:
        send_telegram_msg("❌ Video creation failed.")

if __name__ == "__main__":
    asyncio.run(main())

