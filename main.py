import os
import asyncio
import requests
import nest_asyncio
import json
import time
import re
from google import genai
import edge_tts

nest_asyncio.apply()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

def clean_for_tts(text):
    # မြန်မာစာသားကလွဲလို့ ကျန်တာ အကုန်ရှင်းပါတယ် (Unicode errors ကာကွယ်ရန်)
    return re.sub(r'[^\u1000-\u109F\s၊။]', '', text).strip()

async def get_news_data(topic):
    prompt = f"Write 2 sentences about {topic} in Burmese. JSON: {{\"news\": \"text\"}}"
    try:
        # gemini-3-flash-preview
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except: return None

async def try_generate_audio(text, filename):
    # စမ်းသပ်မည့် Voice List
    voices = ["my-MM-NanDaNeural", "my-MM-ThihaNeural"]
    clean_text = clean_for_tts(text)
    
    for voice in voices:
        try:
            send_telegram_msg(f"🎙️ Trying Voice: {voice}...")
            communicate = edge_tts.Communicate(clean_text, voice)
            await communicate.save(filename)
            
            if os.path.exists(filename) and os.path.getsize(filename) > 500:
                return True
        except Exception as e:
            send_telegram_msg(f"⚠️ {voice} failed: {str(e)[:50]}")
            continue
    return False

async def run_test():
    send_telegram_msg("🚀 Starting Ultra TTS Fix Test...")
    data = await get_news_data("Latest Technology")
    
    if data:
        audio_fn = "final_test.mp3"
        success = await try_generate_audio(data['news'], audio_fn)
        
        if success:
            send_telegram_msg("✅ Success! Audio file generated successfully.")
            # ဗီဒီယိုအပိုင်းကို အသံဖိုင်ရမှ ပြန်ဆက်ပါမယ်
        else:
            send_telegram_msg("❌ All voices failed. This might be a GitHub Actions IP Block.")
    else:
        send_telegram_msg("❌ Gemini could not generate news text.")

if __name__ == "__main__":
    asyncio.run(run_test())

