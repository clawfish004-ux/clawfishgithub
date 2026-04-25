import os
import asyncio
import requests
import nest_asyncio
import json
import time
import re
from google import genai
from google.genai import types
import edge_tts

nest_asyncio.apply()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try: requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

def send_telegram_audio(audio_path, caption):
    """အသံဖိုင်ကို Telegram သို့ ပို့ပေးရန်"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
    try:
        with open(audio_path, 'rb') as audio:
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}, files={'audio': audio}, timeout=30)
    except Exception as e:
        send_telegram_msg(f"❌ Telegram Audio Error: {str(e)}")

def clean_for_tts(text):
    """Unicode အမှားများကြောင့် အသံမထွက်ခြင်းကို ကာကွယ်ရန်"""
    return re.sub(r'[^\u1000-\u109F\s၊။]', '', text).strip()

async def get_grounded_news():
    """Grounding သုံးပြီး အတိုက်အခံဘက်က သတင်းများ ရှာဖွေခြင်း"""
    prompt = (
        "မြန်မာနိုင်ငံ၏ လက်ရှိမြေပြင် စစ်ရေးနှင့် ဆင်းရဲဒုက္ခများကို Khit Thit Media, DVB, Mizzima တို့မှ "
        "အခြေခံ၍ ၁ မိနစ်စာ သတင်းရေးပေးပါ။ JSON ONLY: {\"news\": \"burmese_text\", \"query\": \"keyword\"}"
    )
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search_retrieval=types.GoogleSearchRetrieval())]
            )
        )
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        json_start = clean_text.find('{')
        json_end = clean_text.rfind('}') + 1
        return json.loads(clean_text[json_start:json_end])
    except Exception as e:
        # 429 Error ဖြစ်ပါက Telegram သို့ အသိပေးမည်
        if "429" in str(e):
            send_telegram_msg("⏳ Quota ပြည့်နေဆဲဖြစ်ပါသည်။ ခဏ ထပ်စောင့်ပေးပါ။")
        else:
            send_telegram_msg(f"❌ News Error: {str(e)}")
        return None

async def run_audio_engine():
    send_telegram_msg("🚀 Engine Active: Fetching Grounded News & Generating Audio...")
    
    data = await get_grounded_news()
    if data:
        audio_fn = f"news_{int(time.time())}.mp3"
        clean_text = clean_for_tts(data['news'])
        
        try:
            # Voice အနေဖြင့် NanDa ကို အသုံးပြုပါမည်
            communicate = edge_tts.Communicate(clean_text, "my-MM-NanDaNeural")
            await communicate.save(audio_fn)
            
            if os.path.exists(audio_fn) and os.path.getsize(audio_fn) > 1000:
                caption = f"📰 Grounded News (Resistance Focus)\n\n{data['news'][:200]}..."
                send_telegram_audio(audio_fn, caption)
                send_telegram_msg("✅ အသံဖိုင် ပို့ပြီးပါပြီ ကိုကို။")
            else:
                send_telegram_msg("❌ TTS Failed: အသံဖိုင် မထွက်လာပါ။")
        except Exception as e:
            send_telegram_msg(f"❌ Audio Generation Error: {str(e)}")
    else:
        send_telegram_msg("❌ No data to process.")

if __name__ == "__main__":
    asyncio.run(run_audio_engine())

