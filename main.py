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
YT_INTRO_FILE = "sunshineyt.mp4"

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except: pass

def clean_text_for_tts(text):
    """မြန်မာစာသားမှ မလိုအပ်သော သင်္ကေတများ ရှင်းလင်းရန်"""
    # edge-tts error မတက်အောင် အထူးသင်္ကေတများကို ဖယ်ရှားပါသည်
    clean = re.sub(r'[*#_`]', '', text) 
    return clean

async def get_news_data(topic):
    # Gemini 3 Flash Preview အား JSON ထုတ်ခိုင်းခြင်း
    prompt = f"Write a professional 1-minute news story about {topic} in Burmese. JSON only: {{\"news\": \"text content\", \"query\": \"english keyword\"}}"
    try:
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        send_telegram_msg(f"❌ Gemini Error: {str(e)}")
        return None

async def create_one_minute_video(topic):
    try:
        data = await get_news_data(topic)
        if not data: return None
        
        # 1. အသံဖိုင် ထုတ်ခြင်း (TTS)
        audio_fn = "test_audio.mp3"
        tts_text = clean_text_for_tts(data['news'])
        
        # အသံနှုန်းကို အနည်းငယ် လျှော့ထားပါသည်
        communicate = edge_tts.Communicate(tts_text, "my-MM-NanDaNeural", rate="-5%")
        await communicate.save(audio_fn)
        
        if not os.path.exists(audio_fn) or os.path.getsize(audio_fn) < 500:
            send_telegram_msg("❌ TTS Failed: အသံဖိုင် မထွက်လာပါ။")
            return None

        # 2. ပုံရှာဖွေခြင်း (Pexels)
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=6", headers=headers).json()
        
        if 'photos' not in img_res or not img_res['photos']:
            send_telegram_msg(f"⚠️ ပုံရှာမတွေ့ပါ: {data['query']}")
            return None

        # 3. ဗီဒီယို ဖန်တီးခြင်း
        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"test_img_{i}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=1280).set_position("center") for m in img_paths]
        
        final_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((1280, 720))
        output_fn = "One_Minute_Test.mp4"
        final_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        final_video.close()
        return output_fn
    except Exception as e:
        send_telegram_msg(f"❌ Production Error: {str(e)}")
        return None

async def run_single_test():
    try:
        send_telegram_msg("🚀 Starting 1-Minute Single Test (Gemini 3 Flash)...")
        
        # စမ်းသပ်ရန် ခေါင်းစဉ် တစ်ခုတည်းသာ ထားပါသည်
        topic = "Future of AI in Southeast Asia 2026"
        
        video_file = await create_one_minute_video(topic)
        
        if video_file:
            send_telegram_msg(f"✅ Success! 1-Minute Video Created: {video_file}")
            # Delivery logic ကို GitHub Actions artifacts ထဲမှာ သွားစစ်နိုင်ပါတယ်
        else:
            send_telegram_msg("❌ Failed to create video segment.")
                
    except Exception as e:
        send_telegram_msg(f"❌ Fatal Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_single_test())

