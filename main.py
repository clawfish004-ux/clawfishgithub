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

client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

def clean_burmese_text(text):
    """TTS error ဖြစ်စေနိုင်သော သင်္ကေတများကို အကုန်ရှင်းထုတ်ခြင်း"""
    # မြန်မာစာသားနှင့် ကိန်းဂဏန်းများမှလွဲ၍ ကျန်တာများကို ဖယ်ရှားပါသည်
    clean = re.sub(r'[^\u1000-\u109F\u0030-\u0039\s၊။\-]', '', text)
    return clean.strip()

async def get_news_data(topic):
    prompt = f"Write a 1-minute news story about {topic} in Burmese. JSON ONLY: {{\"news\": \"text\", \"query\": \"keyword\"}}"
    try:
        # gemini-3-flash-preview model
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        send_telegram_msg(f"❌ Gemini Error: {str(e)}")
        return None

async def generate_audio_with_retry(text, filename, retries=3):
    """အသံဖိုင်ရအောင် ၃ ကြိမ်အထိ ပြန်ကြိုးစားပေးမည့် logic"""
    clean_text = clean_burmese_text(text)
    for i in range(retries):
        try:
            # rate ကို default ထားပြီး စမ်းကြည့်ပါမယ်
            communicate = edge_tts.Communicate(clean_text, "my-MM-NanDaNeural")
            await communicate.save(filename)
            
            # ဖိုင်တကယ်ထွက်မထွက် စစ်ဆေးခြင်း
            if os.path.exists(filename) and os.path.getsize(filename) > 1000:
                return True
        except Exception as e:
            send_telegram_msg(f"⏳ TTS Retry {i+1}: {str(e)}")
            await asyncio.sleep(5) # ခဏစောင့်ပြီး ပြန်စမ်းပါ
    return False

async def create_test_video(topic):
    try:
        data = await get_news_data(topic)
        if not data: return None
        
        audio_fn = f"audio_{int(time.time())}.mp3"
        
        # TTS logic အသစ်ကို သုံးပါတယ်
        success = await generate_audio_with_retry(data['news'], audio_fn)
        
        if not success:
            send_telegram_msg("❌ TTS Final Failure: အသံဖိုင် လုံးဝမရပါ။ Internet သို့မဟုတ် Voice Name စစ်ပေးပါ။")
            return None

        # Pexels & Video Logic
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=5", headers=headers).json()
        
        if 'photos' not in img_res or not img_res['photos']:
            return None

        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"img_{i}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=1280) for m in img_paths]
        
        output_fn = "Test_Production.mp4"
        final = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((1280, 720))
        final.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        return output_fn
    except Exception as e:
        send_telegram_msg(f"❌ Detail Error: {str(e)}")
        return None

async def run_engine():
    send_telegram_msg("🚀 Engine Testing (Enhanced TTS Fix Mode)...")
    topic = "Digital Future 2026"
    video = await create_test_video(topic)
    if video:
        send_telegram_msg(f"✅ Success! Video ready: {video}")

if __name__ == "__main__":
    asyncio.run(run_engine())

