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
                requests.post(url, files={'video': video}, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}, timeout=360)
    except Exception as e:
        send_telegram_msg(f"❌ Video Delivery Failed: {e}")

def extract_hour(time_str):
    """
    Logic: 'Off' ဖြစ်နေရင် ကျော်မယ်။ 
    အချိန်ပါလာရင် (ဥပမာ '07:00') ရှေ့က နာရီ '07' ကိုပဲ ယူမယ်။
    """
    if not time_str or str(time_str).lower() == "off":
        return "SKIP_MODE"
    return str(time_str).split(":")[0].zfill(2)

async def get_news_data(topic):
    prompt = f"၂၀၂၆ ခုနှစ်၏ {topic} သတင်းကို မြန်မာလို ၁ မိနစ်စာ ရေးပေးပါ။ JSON သာ ထုတ်ပေးပါ: {{\"news\": \"သတင်းစာသား\", \"query\": \"search_keyword\"}}"
    response = client.models.generate_content(model="gemini-3.1-flash", contents=prompt)
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

async def create_segment(topic, is_yt=True):
    res = (640, 360) if is_yt else (360, 640)
    try:
        data = await get_news_data(topic)
        audio_fn = f"audio_{topic[:3].replace(' ', '')}.mp3"
        await edge_tts.Communicate(data['news'], "my-MM-NanDaNeural").save(audio_fn)
        
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=5", headers=headers).json()
        
        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res.get('photos', [])):
            img_data = requests.get(p['src']['large2x']).content
            path = f"i_{i}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)
            
        if not img_paths: return None

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=res[0] if is_yt else None, height=None if is_yt else res[1]).set_position("center") for m in img_paths]
        segment_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size(res)
        
        output_fn = f"seg_{'yt' if is_yt else 'tt'}_{topic[:3]}.mp4"
        segment_video.write_videofile(output_fn, fps=24, codec="libx264", logger=None)
        
        audio_clip.close()
        segment_video.close()
        return output_fn
    except:
        return None

# --- Main Engine ---

async def run_clawfish_engine():
    try:
        # Get Data from Firestore
        doc = db.collection("clawfishaimews").document("dLGEejnpO6Bbt3Qqpr9o").get().to_dict()
        
        # Get Current Myanmar Time
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=6, minutes=30)
        current_hour = now.strftime("%H") # "07", "15" etc.
        
        send_telegram_msg(f"🔎 Engine Active: {now.strftime('%H:%M')} (Hour: {current_hour})")
        topics = ["World News 2026", "Military & Tech Update", "Myanmar Current Events"]

        # 1. YouTube Production Logic
        yt_hours = [extract_hour(doc.get(f'yt_time_{i}')) for i in range(1, 4)]
        if doc.get('yt_auto_mode') is True and current_hour in yt_hours:
            send_telegram_msg(f"📺 YouTube Production Starting (Hour: {current_hour})")
            yt_segs = [await create_segment(t, is_yt=True) for t in topics]
            yt_segs = [s for s in yt_segs if s]
            if yt_segs:
                intro = VideoFileClip(YT_INTRO_FILE).resize((640, 360))
                clips = [intro] + [VideoFileClip(s) for s in yt_segs]
                final = concatenate_videoclips(clips, method="compose")
                out_name = f"Final_YT_{current_hour}.mp4"
                final.write_videofile(out_name, codec="libx264")
                final.close()
                send_telegram_video(out_name, f"✅ YouTube Done (Hour: {current_hour})")

        # 2. TikTok Production Logic
        tt_hours = [extract_hour(doc.get(f'tt_time_{i}')) for i in range(1, 4)]
        if doc.get('tt_auto_mode') is True and current_hour in tt_hours:
            send_telegram_msg(f"📱 TikTok Production Starting (Hour: {current_hour})")
            tt_segs = [await create_segment(t, is_yt=False) for t in topics]
            tt_segs = [s for s in tt_segs if s]
            if tt_segs:
                intro = VideoFileClip(TT_INTRO_FILE).resize((360, 640))
                clips = [intro] + [VideoFileClip(s) for s in tt_segs]
                final = concatenate_videoclips(clips, method="compose")
                out_name = f"Final_TT_{current_hour}.mp4"
                final.write_videofile(out_name, codec="libx264")
                final.close()
                send_telegram_video(out_name, f"✅ TikTok Done (Hour: {current_hour})")

        # 3. Cleanup Files
        for f in os.listdir():
            if any(x in f for x in ["audio_", "i_", "seg_", "Final"]) and f not in [YT_INTRO_FILE, TT_INTRO_FILE]:
                try: os.remove(f)
                except: pass
                
    except Exception as e:
        send_telegram_msg(f"❌ Engine Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_clawfish_engine())
    
