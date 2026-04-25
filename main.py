import os
import asyncio
import requests
import nest_asyncio
import json
import datetime
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

# AI & Firestore Clients
client = genai.Client(api_key=GEMINI_API_KEY)
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
db = firestore.Client(credentials=credentials, project="ai-news-channel-d69be")

YT_INTRO_FILE = "sunshineyt.mp4"
TT_INTRO_FILE = "sunshinett.mp4"

# --- Helper Functions ---

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
    prompt = f"၂၀၂၆ ခုနှစ်၏ {topic} သတင်းကို မြန်မာလို ၁ မိနစ်စာ ရေးပေးပါ။ JSON သာ ထုတ်ပေးပါ: {{\"news\": \"သတင်းစာသား\", \"query\": \"search_keyword\"}}"
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

async def create_segment(topic, is_yt=True):
    res = (640, 360) if is_yt else (360, 640)
    try:
        data = await get_news_data(topic)
        audio_fn = f"audio_{topic[:3].replace(' ', '')}.mp3"
        await edge_tts.Communicate(data['news'], "my-MM-NanDaNeural").save(audio_fn)
        
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=5", headers=headers, timeout=20).json()
        
        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res.get('photos', [])):
            img_data = requests.get(p['src']['large2x']).content
            path = f"i_{i}_{topic[:3]}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)
            
        if not img_paths: return None

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=res[0] if is_yt else None, height=None if is_yt else res[1]).set_position("center") for m in img_paths]
        segment_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size(res)
        
        output_fn = f"seg_{'yt' if is_yt else 'tt'}_{topic[:3]}.mp4"
        segment_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        segment_video.close()
        return output_fn
    except Exception as e:
        print(f"Segment Error: {e}")
        return None

async def run_clawfish_engine():
    try:
        send_telegram_msg("🚀 Engine Active: Starting Manual Production Test...")
        topics = ["World Politics 2026", "Global Economy"]
        
        yt_segs = []
        for t in topics:
            seg = await create_segment(t, is_yt=True)
            if seg: yt_segs.append(seg)

        if yt_segs:
            intro = VideoFileClip(YT_INTRO_FILE).resize((640, 360))
            clips = [intro] + [VideoFileClip(s) for s in yt_segs]
            final = concatenate_videoclips(clips, method="compose")
            final.write_videofile("YT_Final.mp4", codec="libx264", audio_codec="aac")
            final.close()
            send_telegram_video("YT_Final.mp4", "✅ YouTube Video is ready!")
            for c in clips: c.close()
        else:
            send_telegram_msg("❌ Error: No video segments were created.")

        for f in os.listdir():
            if any(x in f for x in ["audio_", "i_", "seg_", "Final"]) and f not in [YT_INTRO_FILE, TT_INTRO_FILE]:
                try: os.remove(f)
                except: pass
                
    except Exception as e:
        send_telegram_msg(f"❌ Detail Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_clawfish_engine())
        
