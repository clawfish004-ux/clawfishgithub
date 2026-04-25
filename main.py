import os
import asyncio
import requests
import nest_asyncio
import json
from google import genai
from google.genai import types

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

async def get_grounded_news():
    """Google Search Grounding ကိုသုံးပြီး သတင်းရင်းမြစ်ကို ကန့်သတ်ခြင်း"""
    
    # ကိုကို လိုချင်တဲ့ အရင်းအမြစ်တွေကို အလေးပေးဖို့ ညွှန်ကြားချက်
    prompt = (
        "မြန်မာနိုင်ငံ၏ လက်ရှိမြေပြင် စစ်ရေးနှင့် နိုင်ငံရေးအခြေအနေများကို အခြေခံ၍ ၁ မိနစ်စာ သတင်းရေးပေးပါ။ "
        "သတင်းရင်းမြစ်များကို Khit Thit Media, DVB, Mizzima နှင့် Myanmar Now ကဲ့သို့သော "
        "အတိုက်အခံ အင်အားစုဘက်က သတင်းဌာနများထံမှသာ အဓိကထား ရယူပါ။ "
        "ပကတိမြေပြင်တွင် ဖြစ်ပျက်နေသော ဆင်းရဲဒုက္ခများနှင့် တိုက်ပွဲသတင်းများကို ထည့်သွင်းပါ။ "
        "Return ONLY JSON: {\"news\": \"burmese_text\", \"query\": \"visual_search_keyword\"}"
    )

    try:
        # Gemini 3 Flash ၏ Search Tool ကို အသုံးပြုခြင်း
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search_retrieval=types.GoogleSearchRetrieval())]
            )
        )
        
        # JSON ထုတ်ယူခြင်း
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        # တစ်ခါတလေ Search လုပ်လျှင် အပိုစာသားများ ပါလာတတ်၍ JSON ကိုသာ ဖြတ်ယူပါသည်
        json_start = clean_text.find('{')
        json_end = clean_text.rfind('}') + 1
        return json.loads(clean_text[json_start:json_end])
    except Exception as e:
        send_telegram_msg(f"❌ Grounding Error: {str(e)}")
        return None

async def run_engine():
    send_telegram_msg("🚀 Engine Active: Fetching Grounded News from Resistance Sources...")
    
    data = await get_grounded_news()
    if data:
        report = (
            f"📰 **မြေပြင်အခြေအနေအခြေခံသတင်း (Resistance Sources Focus)**\n\n"
            f"{data['news']}\n\n"
            f"🔍 Keywords for Visuals: {data['query']}"
        )
        send_telegram_msg(report)
        send_telegram_msg("✅ Grounded text generated! အသံဖိုင်ပိုင်း ပြန်ဆက်ရမလား ကိုကို?")

if __name__ == "__main__":
    asyncio.run(run_engine())

