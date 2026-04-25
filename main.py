import os
import asyncio
import requests
import nest_asyncio
import json
import datetime
from google import genai
import edge_tts

nest_asyncio.apply()

# --- CONFIG ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)

# English Voice for 1-minute feel
VOICE = "en-US-AndrewNeural" 

# --- TELEGRAM ---
def send_msg(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text}
        )
    except Exception as e:
        print(f"Error: {e}")

def send_audio(audio_path, caption):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
        with open(audio_path, "rb") as audio:
            files = {"audio": audio}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            res = requests.post(url, files=files, data=data)
            print(f"Telegram response: {res.status_code}")
    except Exception as e:
        send_msg(f"❌ Audio Send Error: {e}")

# --- GEMINI (English Content) ---
async def get_news_text(topic):
    # တစ်မိနစ်စာအတွက် စာလုံးရေ ၂၀၀ ကနေ ၂၅၀ ဝန်းကျင် ရေးခိုင်းထားပါတယ်
    prompt = f"""
    Write a professional news report about {topic} in English.
    The length should be around 200 words (suitable for a 1-minute voiceover).
    Focus on clarity and a modern tone.
    
    Return ONLY JSON:
    {{
      "title": "Headline here",
      "content": "Full news text here..."
    }}
    """
    try:
        res = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        txt = res.text.replace("```json", "").replace("```", "").strip()
        return json.loads(txt)
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

# --- TTS ---
async def generate_mp3(text, filename):
    try:
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(filename)
        return filename
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

# --- TEST RUN ---
async def test_audio_engine():
    topic = "The Future of AI and Robotics in 2026"
    print(f"🚀 Starting Audio Test: {topic}")
    
    # 1. Get Text
    data = await get_news_text(topic)
    if not data:
        send_msg("❌ Failed to get news from Gemini")
        return

    # 2. Generate Audio
    filename = "test_news.mp3"
    audio_file = await generate_mp3(data["content"], filename)
    
    if audio_file and os.path.exists(audio_file):
        # 3. Send to Telegram
        caption = f"🎙️ AI News Audio Test\nTitle: {data['title']}\nLanguage: English"
        send_audio(audio_file, caption)
        print("✅ Audio sent successfully")
        
        # Cleanup
        os.remove(audio_file)
    else:
        send_msg("❌ Failed to generate MP3 file")

if __name__ == "__main__":
    asyncio.run(test_audio_engine())

