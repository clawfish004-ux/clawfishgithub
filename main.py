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

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

FIREBASE_SECRET = os.getenv("FIREBASE_SERVICE_ACCOUNT")
KEY_PATH = "firebase_key.json"
if FIREBASE_SECRET:
    with open(KEY_PATH, "w") as f: f.write(FIREBASE_SECRET)

client = genai.Client(api_key=GEMINI_API_KEY)
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
db = firestore.Client(credentials=credentials, project="ai-news-channel-d69be")

YT_INTRO_FILE = "sunshineyt.mp4"
TT_INTRO_FILE = "sunshinett.mp4"

# --- Functions ---

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message})

def send_telegram_video(video_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    try:
        with open(video_path, 'rb') as video:
            requests.post(url, files={'video': video}, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption})
    except Exception as e: print(f"Telegram Video Error: {e}")

def download_pexels_images(query, count=6):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page={count}&orientation=landscape"
    try:
        response = requests.get(url, headers=headers).json()
        image_paths = []
        for i, photo in enumerate(response.get("photos", [])):
            img_data = requests.get(photo["src"]["large2x"]).content
            path = f"img_{i}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            image_paths.append(path)
        return image_paths
    except: return []

async def get_news_data(topic):
    prompt = f"၂၀၂၆ ခုနှစ်၏ {topic} သတင်းကို မြန်မာလို ၁ မိနစ်စာ ရေးပေးပါ။ JSON: {{\"news\": \"...\", \"query\": \"keyword\"}}"
    response = client.models.generate_content(model="gemini-3.1-flash", contents=prompt)
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

async def create_segment(topic, is_yt=True):
    """is_yt=True ဆိုရင် 640x360 (YouTube)၊ False ဆိုရင် 360x640 (TikTok) ထုတ်ပေးမည်"""
    data = await get_news_data(topic)
    res = (640, 360) if is_yt else (360, 640)
    
    audio_fn = f"audio_{topic[:5]}.mp3"
    await edge_tts.Communicate(data['news'], "my-MM-NanDaNeural").save(audio_fn)
    
    image_list = download_pexels_images(data['query'])
    audio_clip = AudioFileClip(audio_fn)
    
    if not image_list:
        segment_video = ImageClip(None, duration=audio_clip.duration).set_size(res).set_color((0,0,0)).set_audio(audio_clip)
    else:
        duration = audio_clip.duration / len(image_list)
        # Image Resize & Centering
        clips = [ImageClip(img).set_duration(duration).resize(width=res[0] if is_yt else None, height=None if is_yt else res[1]).set_position("center") for img in image_list]
        segment_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size(res)
    
    output_fn = f"seg_{'yt' if is_yt else 'tt'}_{topic[:5]}.mp4"
    segment_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
    return output_fn

async def run_clawfish_engine():
    try:
        send_telegram_msg("🚀 Engine Started (Low Res Mode - 2026)")
        doc = db.collection("clawfishaimews").document("dLGEejnpO6Bbt3Qqpr9o").get().to_dict()

        topics = ["World Politics 2026", "Military News", "Business", "Tech", "Myanmar Update"]

        # YouTube Production (Landscape 640x360)
        if doc.get('yt_auto_mode'):
            yt_segs = [await create_segment(t, is_yt=True) for t in topics]
            final_yt = concatenate_videoclips([VideoFileClip(YT_INTRO_FILE).resize((640, 360))] + [VideoFileClip(s) for s in yt_segs])
            final_yt.write_videofile("YT_Final.mp4", codec="libx264", logger=None)
            send_telegram_video("YT_Final.mp4", "✅ YouTube (640x360) Done!")

        # TikTok Production (Portrait 360x640)
        if doc.get('tt_auto_mode'):
            tt_segs = [await create_segment(t, is_yt=False) for t in topics]
            final_tt = concatenate_videoclips([VideoFileClip(TT_INTRO_FILE).resize((360, 640))] + [VideoFileClip(s) for s in tt_segs])
            final_tt.write_videofile("TT_Final.mp4", codec="libx264", logger=None)
            send_telegram_video("TT_Final.mp4", "✅ TikTok (360x640) Done!")

        # Cleanup
        for f in os.listdir():
            if (f.endswith(".mp3") or f.endswith(".jpg") or "seg_" in f) or "Final" in f:
                if f not in [YT_INTRO_FILE, TT_INTRO_FILE]: os.remove(f)
        
        send_telegram_msg("၅၁! အကုန်ပြီးပါပြီ။")
    except Exception as e: send_telegram_msg(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_clawfish_engine())
  
