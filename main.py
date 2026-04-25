import os
import asyncio
import requests
import nest_asyncio
import json
from google.cloud import firestore
from google.oauth2 import service_account
from google import genai
import edge_tts
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips

nest_asyncio.apply()

# --- Configuration (GitHub Secrets) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FIREBASE_SECRET = os.getenv("FIREBASE_SERVICE_ACCOUNT")

KEY_PATH = "firebase_key.json"
if FIREBASE_SECRET:
    with open(KEY_PATH, "w") as f:
        f.write(FIREBASE_SECRET)

# --- Clients ---
# Gemini 3 Flash Model ကို အသုံးပြုခြင်း
client = genai.Client(api_key=GEMINI_API_KEY)
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
db = firestore.Client(credentials=credentials, project="ai-news-channel-d69be")

YT_INTRO_FILE = "sunshineyt.mp4"

# --- Functions ---

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=10)
    except:
        pass

def send_telegram_video(video_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    try:
        if os.path.exists(video_path):
            with open(video_path, 'rb') as video:
                requests.post(url, files={'video': video}, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}, timeout=600)
    except Exception as e:
        send_telegram_msg(f"❌ Video Delivery Failed: {e}")

async def get_news_data(topic):
    # Gemini 3 Flash model ကို တိုက်ရိုက်ခေါ်ယူခြင်း
    prompt = f"Write a 1-minute news story about {topic} in Burmese for 2026. Return ONLY JSON format: {{\"news\": \"Burmese text here\", \"query\": \"english_search_term\"}}"
    try:
        # Gemini 3 Flash ကို အသုံးပြုထားပါသည်
        response = client.models.generate_content(model="gemini-3-flash", contents=prompt)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        send_telegram_msg(f"❌ Gemini 3 Flash Error: {str(e)}")
        return None

async def create_segment(topic):
    try:
        data = await get_news_data(topic)
        if not data: return None
        
        # Audio generation (Edge TTS)
        audio_fn = f"audio_{topic[:3].replace(' ', '')}.mp3"
        await edge_tts.Communicate(data['news'], "my-MM-NanDaNeural").save(audio_fn)
        
        # Image search (Pexels)
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=3", headers=headers, timeout=20).json()
        
        if 'photos' not in img_res or not img_res['photos']:
            send_telegram_msg(f"⚠️ Pexels: No images found for '{data['query']}'")
            return None

        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"i_{i}_{topic[:3].replace(' ', '')}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        # Video composition
        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=640).set_position("center") for m in img_paths]
        segment_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((640, 360))
        
        output_fn = f"seg_{topic[:3].replace(' ', '')}.mp4"
        segment_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        segment_video.close()
        return output_fn
    except Exception as e:
        send_telegram_msg(f"❌ Segment Error: {str(e)}")
        return None

# --- Main Engine (Manual Run) ---

async def run_clawfish_engine():
    try:
        send_telegram_msg("🚀 Engine Start: Running with Gemini 3 Flash")
        
        # စမ်းသပ်ရန် topic တစ်ခုပဲ အရင်သုံးပါမယ် (Quota သက်သာစေရန်)
        topics = ["World Technology 2026"]
        
        yt_segs = []
        for t in topics:
            seg = await create_segment(t)
            if seg: 
                yt_segs.append(seg)
                await asyncio.sleep(5) 

        if yt_segs:
            video_clips = [VideoFileClip(s) for s in yt_segs]
            
            # Intro file ရှိမရှိ စစ်ဆေးခြင်း
            if os.path.exists(YT_INTRO_FILE):
                video_clips.insert(0, VideoFileClip(YT_INTRO_FILE).resize((640, 360)))
            
            final = concatenate_videoclips(video_clips, method="compose")
            final_name = "Final_News_Gemini3.mp4"
            final.write_videofile(final_name, codec="libx264", audio_codec="aac")
            
            send_telegram_video(final_name, "✅ Production Success: Gemini 3 Flash Video Ready!")
            
            # Closing clips to release memory
            final.close()
            for v in video_clips: v.close()
            
            # Cleanup temporary files
            for f in os.listdir():
                if any(x in f for x in ["audio_", "i_", "seg_"]):
                    try: os.remove(f)
                    except: pass
        else:
            send_telegram_msg("❌ Manual Test Failed: No segments created.")
                
    except Exception as e:
        send_telegram_msg(f"❌ Fatal Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_clawfish_engine())

