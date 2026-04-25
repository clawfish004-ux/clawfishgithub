import os
import asyncio
import requests
import nest_asyncio
import json
import time
import re
from google import genai
import edge_tts
from gtts import gTTS # Backup TTS အတွက် ထည့်ထားပါသည်
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips

nest_asyncio.apply()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)
YT_INTRO_FILE = "sunshineyt.mp4"

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

def clean_text(text):
    # စာသားထဲမှ သင်္ကေတများကို အကုန်ရှင်းထုတ်ပါသည်
    return re.sub(r'[^\w\s\u1000-\u109F၊။]', '', text).strip()

async def get_audio(text, filename):
    """Edge-TTS ကို အရင်စမ်းပြီး မရပါက gTTS နှင့် အစားထိုးပါသည်"""
    cleaned = clean_text(text)
    try:
        # Strategy 1: Edge-TTS
        communicate = edge_tts.Communicate(cleaned, "my-MM-NanDaNeural")
        await communicate.save(filename)
        if os.path.exists(filename) and os.path.getsize(filename) > 1000:
            return True
    except:
        pass
    
    try:
        # Strategy 2: gTTS (Google TTS) as Backup
        tts = gTTS(text=cleaned, lang='my')
        tts.save(filename)
        if os.path.exists(filename):
            return True
    except Exception as e:
        send_telegram_msg(f"❌ All TTS Engines Failed: {str(e)}")
        return False

async def create_test_video(topic):
    data_prompt = f"Write a 40-second news about {topic} in Burmese. JSON: {{\"news\": \"text\", \"query\": \"keyword\"}}"
    try:
        # gemini-3-flash-preview ကို အသုံးပြုသည်
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=data_prompt)
        data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
        
        audio_fn = "final_audio.mp3"
        if not await get_audio(data['news'], audio_fn):
            return None

        # Pexels images
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=4", headers=headers).json()
        
        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"t_{i}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=1280).set_position("center") for m in img_paths]
        
        final = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((1280, 720))
        output = "One_Minute_Done.mp4"
        final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        final.close()
        return output
    except Exception as e:
        send_telegram_msg(f"❌ Error: {str(e)}")
        return None

async def run():
    send_telegram_msg("🔄 Starting Final TTS-Fix Test (1-Minute)...")
    video = await create_test_video("Digitalization in Myanmar")
    if video:
        send_telegram_msg(f"✅ Success! Video created using backup TTS engine.")
    else:
        send_telegram_msg("❌ Still failing to get audio.")

if __name__ == "__main__":
    asyncio.run(run())

