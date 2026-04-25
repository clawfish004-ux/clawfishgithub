import os
import asyncio
import requests
import nest_asyncio
import json
import time
from google import genai

nest_asyncio.apply()

# --- Configuration (လုံခြုံရေးအတွက် Secrets မှသာ ဆွဲသုံးပါသည်) ---
# ဒီနေရာမှာ Key ကို တိုက်ရိုက်မရေးတော့ဘဲ GitHub Secrets ကနေပဲ ယူပါမယ်
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Client Setup
client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

async def get_news_data(topic):
    # Screenshot ထဲကအတိုင်း gemini-3-flash-preview ကို သုံးပါမယ်
    prompt = f"Write a professional news script about {topic} in Burmese. JSON only: {{\"news\": \"text\", \"query\": \"keyword\"}}"
    try:
        # ကိုကို့ Key အသစ်က ဒီ model ကို access ရမှာပါ
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        send_telegram_msg(f"❌ Gemini Error: {str(e)}")
        return None

async def run_engine():
    if not GEMINI_API_KEY:
        send_telegram_msg("❌ Error: API Key missing in GitHub Secrets!")
        return

    send_telegram_msg("🚀 Engine Active with New Secure Key...")
    data = await get_news_data("World News 2026")
    if data:
        send_telegram_msg(f"✅ Success! News: {data['news'][:50]}...")

if __name__ == "__main__":
    asyncio.run(run_engine())

