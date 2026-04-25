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
    with open(KEY_PATH, "w") as f:
        f.write(FIREBASE_SECRET)

client = genai.Client(api_key=GEMINI_API_KEY)
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
db = firestore.Client(credentials=credentials, project="ai-news-channel-d69be")

YT_INTRO_FILE = "sunshineyt.mp4"

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message})

def send_telegram_video(video_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    if os.path.exists(video_path):
        with open(video_path, 'rb') as video:
            requests.post(url, files={'video': video}, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}, timeout=600)

async def get_news_data(topic):
    prompt = f"Write a 1-minute news about {topic} in Burmese. Return ONLY JSON: {{\"news\": \"text\", \"query\": \"search_keyword\"}}"
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_json)

async def create_segment(topic):
    try:
        data = await get_news_data(topic)
        audio_fn = f"audio_{topic[:3]}.mp3"
        await edge_tts.Communicate(data['news'], "my-MM-NanDaNeural").save(audio_fn)
        
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=3", headers=headers).json()
        
        if 'photos' not in img_res or not img_res['photos']:
            send_telegram_msg(f"⚠️ No images found for: {data['query']}")
            return None

        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"i_{i}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=640).set_position("center") for m in img_paths]
        segment_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((640, 360))
        
        output_fn = f"seg_{topic[:3]}.mp4"
        segment_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        return output_fn
    except Exception as e:
        send_telegram_msg(f"❌ Segment Error ({topic}): {str(e)}")
        return None

async def run_clawfish_engine():
    try:
        send_telegram_msg("🚀 Engine Test Start...")
        topics = ["World News", "Technology"]
        
        yt_segs = []
        for t in topics:
            seg = await create_segment(t)
            if seg: yt_segs.append(seg)

        if yt_segs:
            # Intro မရှိရင် Intro မပါဘဲ ပေါင်းမယ်
            video_clips = [VideoFileClip(s) for s in yt_segs]
            if os.path.exists(YT_INTRO_FILE):
                video_clips.insert(0, VideoFileClip(YT_INTRO_FILE).resize((640, 360)))
            
            final = concatenate_videoclips(video_clips, method="compose")
            final.write_videofile("Final_News.mp4", codec="libx264", audio_codec="aac")
            send_telegram_video("Final_News.mp4", "✅ Production Success!")
        else:
            send_telegram_msg("❌ No segments created. Check API keys.")
                
    except Exception as e:
        send_telegram_msg(f"❌ Main Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_clawfish_engine())
    
