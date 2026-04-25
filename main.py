import os
import asyncio
import requests
import nest_asyncio
import json
import time
from google import genai

nest_asyncio.apply()

# --- Configuration ---
# ကိုကို့ရဲ့ API Key အသစ်
GEMINI_API_KEY = "AIzaSyCO8WyCG2Kv3uGJnfW1OHH6ufyrEHoEN8c"
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Gemini 3 Flash Preview Model ကို အသုံးပြုခြင်း
client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except:
        pass

async def get_news_data(topic):
    # ၂၀၂၆ Preview model ဖြစ်လို့ နာမည်ကို အတိအကျပေးရပါမယ်
    prompt = f"Write a professional 1-minute news script about {topic} in Burmese. Return ONLY JSON: {{\"news\": \"text\", \"query\": \"search_keyword\"}}"
    try:
        # Model name ကို gemini-3-flash-preview လို့ ပြောင်းလဲလိုက်ပါတယ်
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=prompt
        )
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        send_telegram_msg(f"❌ Gemini Error: {str(e)}")
        return None

async def run_engine():
    try:
        send_telegram_msg("🚀 Engine Manual Start - Producing Video Now...")
        
        topics = ["World Politics 2026", "Global Economy"]
        
        for t in topics:
            data = await get_news_data(t)
            if data:
                send_telegram_msg(f"✅ News Generated for: {t}\n\n{data['news'][:100]}...")
                # Video segment logic က ကိုကို့ရဲ့ local file တွေ လိုအပ်လို့ 
                # အခု Gemini model အလုပ်လုပ်မလုပ် အရင် test လုပ်ပါမယ်
            await asyncio.sleep(5)
            
    except Exception as e:
        send_telegram_msg(f"❌ Fatal Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_engine())

