import os
import asyncio
import requests
import nest_asyncio
import json
import time
from google.cloud import firestore
from google.oauth2 import service_account
from google import genai
import edge_tts
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips

nest_asyncio.apply()

# --- Configuration (ကိုကို့ API Key အသစ်ကို ဒီမှာ တိုက်ရိုက်ထည့်ထားပါတယ်) ---
GEMINI_API_KEY = "AIzaSyCO8WyCG2Kv3uGJnfW1OHH6ufyrEHoEN8c" #
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FIREBASE_SECRET = os.getenv("FIREBASE_SERVICE_ACCOUNT")

KEY_PATH = "firebase_key.json"
if FIREBASE_SECRET:
    with open(KEY_PATH, "w") as f:
        f.write(FIREBASE_SECRET)

# --- Clients ---
# Gemini 3 Flash ကို အသုံးပြုရန် GenAI Client တည်ဆောက်ခြင်း
client = genai.Client(api_key=GEMINI_API_KEY)

# Firebase Setup
if os.path.exists(KEY_PATH):
    credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
    db = firestore.Client(credentials=credentials, project="ai-news-channel-d69be")

YT_INTRO_FILE = "sunshineyt.mp4"

# --- Functions ---

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=15)
    except:
        pass

def send_telegram_video(video_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    try:
        if os.path.exists(video_path):
            with open(video_path, 'rb') as video:
                requests.post(url, files={'video': video}, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}, timeout=900)
    except Exception as e:
        send_telegram_msg(f"❌ Video Send Failed: {str(e)}")

async def get_news_data(topic):
    # Gemini 3 Flash model အား ခေါ်ယူခြင်း
    # prompt ထဲတွင် မြန်မာလို ရေးခိုင်းထားပါသည်
    prompt = f"Write a professional 1-minute news script about {topic} in Burmese for the year 2026. Return ONLY a valid JSON object: {{\"news\": \"text content\", \"query\": \"english_search_keyword_for_pexels\"}}"
    
    try:
        # ၂၀၂၆ SDK အရ gemini-3-flash နာမည်ကို အသုံးပြုပါသည်
        response = client.models.generate_content(model="gemini-3-flash", contents=prompt)
        # JSON သန့်စင်ခြင်း
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        send_telegram_msg(f"❌ Gemini 3 Flash Error: {str(e)}")
        return None

async def create_segment(topic):
    try:
        data = await get_news_data(topic)
        if not data: return None
        
        # 1. Audio Generation (Burmese TTS)
        audio_fn = f"audio_{int(time.time())}.mp3"
        await edge_tts.Communicate(data['news'], "my-MM-NanDaNeural").save(audio_fn)
        
        # 2. Image Fetching (Pexels)
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=4", headers=headers, timeout=20).json()
        
        if 'photos' not in img_res or not img_res['photos']:
            send_telegram_msg(f"⚠️ No images for: {data['query']}")
            return None

        # 3. Video Processing
        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"img_{i}_{int(time.time())}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        duration_per_img = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration_per_img).resize(width=1280).set_position("center") for m in img_paths]
        
        segment_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((1280, 720))
        output_fn = f"seg_{int(time.time())}.mp4"
        segment_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        # Memory Cleanup
        audio_clip.close()
        segment_video.close()
        return output_fn
    except Exception as e:
        send_telegram_msg(f"❌ Segment Logic Error: {str(e)}")
        return None

# --- Main Runner ---

async def run_news_engine():
    try:
        send_telegram_msg("🚀 AI News Engine 2026: Starting Production with Gemini 3 Flash...")
        
        # သတင်းခေါင်းစဉ်များ (Manual စမ်းသပ်ရန်)
        topics = ["Myanmar Economy 2026", "Global AI Advancements"]
        
        yt_segs = []
        for t in topics:
            seg = await create_segment(t)
            if seg: 
                yt_segs.append(seg)
                await asyncio.sleep(10) # API Quota အတွက် ခေတ္တစောင့်ခြင်း

        if yt_segs:
            video_clips = [VideoFileClip(s) for s in yt_segs]
            
            # Intro ထည့်သွင်းခြင်း
            if os.path.exists(YT_INTRO_FILE):
                video_clips.insert(0, VideoFileClip(YT_INTRO_FILE).resize((1280, 720)))
            
            final_video = concatenate_videoclips(video_clips, method="compose")
            final_name = "Burmese_News_2026.mp4"
            final_video.write_videofile(final_name, codec="libx264", audio_codec="aac")
            
            send_telegram_video(final_name, "🎬 YouTube News Production Complete! (Gemini 3 Flash)")
            
            # Final Cleanup
            final_video.close()
            for v in video_clips: v.close()
            for file in os.listdir():
                if file.endswith((".mp3", ".jpg", ".mp4")) and file != YT_INTRO_FILE:
                    try: os.remove(file)
                    except: pass
        else:
            send_telegram_msg("❌ Production Failed: No segments created.")
                
    except Exception as e:
        send_telegram_msg(f"❌ Fatal Engine Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_news_engine())

