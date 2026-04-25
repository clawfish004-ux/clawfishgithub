import os
import asyncio
import requests
import nest_asyncio
import json
import time
import re
from google import genai
import edge_tts
from PIL import Image
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips

nest_asyncio.apply()

# Pillow version compatibility
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# --- Configuration (GitHub Secrets) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Client setup using Gemini 3 Flash Preview
client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except Exception as e:
        print(f"Telegram Error: {e}")

async def get_news_data(topic):
    """Gemini မှ သတင်းစာသား ထုတ်ယူခြင်း"""
    # တစ်မိနစ်စာ ခန့်မှန်းခြေ စာလုံးရေ ၃၀၀ ကျော် ထည့်ခိုင်းထားပါတယ်
    prompt = (
        f"Write a professional 1-minute long news script about {topic} in Burmese for the year 2026. "
        "The script should be detailed enough to last for 60 seconds. "
        "Return ONLY a valid JSON object: {\"news\": \"burmese_text\", \"query\": \"english_keyword\"}"
    )
    
    try:
        # gemini-3-flash-preview model နာမည်ကို အသုံးပြုပါသည်
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=prompt
        )
        
        # Markdown backticks များကို ဖယ်ရှားခြင်း
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        return data
    except Exception as e:
        send_telegram_msg(f"❌ Gemini Content Error: {str(e)}")
        return None

async def run_text_test():
    try:
        send_telegram_msg("🚀 Starting 1-Minute Text Generation Test...")
        
        topic = "Future of Digital Economy in Myanmar 2026"
        data = await get_news_data(topic)
        
        if data:
            news_content = data.get("news", "No news content")
            search_query = data.get("query", "No query")
            
            # Telegram ကို စာသား အပြည့်အစုံ ပို့ခြင်း
            # စာသားအရမ်းရှည်ရင် Telegram က လက်မခံတတ်လို့ ဖြတ်ပို့တာမျိုး မလုပ်ဘဲ အကုန်ပို့ပါတယ်
            report = (
                f"📰 **Generated News Script (1 Minute)**\n\n"
                f"Topic: {topic}\n\n"
                f"Script:\n{news_content}\n\n"
                f"Pexels Query: {search_query}"
            )
            send_telegram_msg(report)
            send_telegram_msg("✅ Text successfully generated and sent! Now we can proceed to Audio logic.")
        else:
            send_telegram_msg("❌ Failed to get data from Gemini.")
            
    except Exception as e:
        send_telegram_msg(f"❌ Fatal System Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_text_test())

