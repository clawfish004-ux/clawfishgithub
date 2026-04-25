import os
import asyncio
import requests
import nest_asyncio
import json
import time
from google import genai
from google.api_core import exceptions
import edge_tts
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips

nest_asyncio.apply()

# --- Configuration (GitHub Secrets မှသာ ဆွဲသုံးပါသည်) ---
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

async def get_news_data_with_retry(topic, retries=3, delay=10):
    """503 Error အတွက် အလိုအလျောက် ပြန်ကြိုးစားပေးမည့် Function"""
    prompt = f"Write a professional news script about {topic} in Burmese for 2026. Return ONLY JSON: {{\"news\": \"text\", \"query\": \"keyword\"}}"
    
    for i in range(retries):
        try:
            # gemini-3-flash-preview model အား အသုံးပြုခြင်း
            response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            if "503" in str(e) or "Service Unavailable" in str(e):
                send_telegram_msg(f"⏳ Server Busy (Attempt {i+1}/{retries}). Waiting {delay}s...")
                await asyncio.sleep(delay)
                continue
            send_telegram_msg(f"❌ Gemini Error: {str(e)}")
            return None
    return None

async def create_segment(topic):
    try:
        data = await get_news_data_with_retry(topic)
        if not data: return None
        
        # 1. TTS
        audio_fn = f"audio_{int(time.time())}.mp3"
        await edge_tts.Communicate(data['news'], "my-MM-NanDaNeural").save(audio_fn)
        
        # 2. Pexels
        headers = {"Authorization": PEXELS_API_KEY}
        img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['query']}&per_page=5", headers=headers).json()
        
        if 'photos' not in img_res or not img_res['photos']: return None

        audio_clip = AudioFileClip(audio_fn)
        img_paths = []
        for i, p in enumerate(img_res['photos']):
            img_data = requests.get(p['src']['large2x']).content
            path = f"img_{i}_{int(time.time())}.jpg"
            with open(path, 'wb') as f: f.write(img_data)
            img_paths.append(path)

        duration = audio_clip.duration / len(img_paths)
        clips = [ImageClip(m).set_duration(duration).resize(width=1280).set_position("center") for m in img_paths]
        
        output_fn = f"seg_{int(time.time())}.mp4"
        segment_video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip).set_size((1280, 720))
        segment_video.write_videofile(output_fn, fps=24, codec="libx264", audio_codec="aac", logger=None)
        
        audio_clip.close()
        segment_video.close()
        return output_fn
    except Exception as e:
        send_telegram_msg(f"❌ Segment Error: {str(e)}")
        return None

async def run_news_engine():
    try:
        send_telegram_msg("🚀 Engine Active: Gemini 3 Flash Production Starting...")
        topics = ["Myanmar Tech News 2026", "Global Economy Update"]
        
        yt_segs = []
        for t in topics:
            seg = await create_segment(t)
            if seg: yt_segs.append(seg)
            await asyncio.sleep(5)

        if yt_segs:
            video_clips = [VideoFileClip(s) for s in yt_segs]
            if os.path.exists(YT_INTRO_FILE):
                video_clips.insert(0, VideoFileClip(YT_INTRO_FILE).resize((1280, 720)))
            
            final_name = "Final_News_2026.mp4"
            final = concatenate_videoclips(video_clips, method="compose")
            final.write_videofile(final_name, codec="libx264", audio_codec="aac")
            
            # Telegram သို့ ပို့ရန် logic (လိုအပ်လျှင် send_telegram_video ကို ပြန်သုံးနိုင်သည်)
            send_telegram_msg(f"✅ Production Finished: {final_name}")
            
            final.close()
            for v in video_clips: v.close()
            # Cleanup
            for f in os.listdir():
                if any(ext in f for ext in [".mp3", ".jpg", ".mp4"]) and f != YT_INTRO_FILE:
                    try: os.remove(f)
                    except: pass
        else:
            send_telegram_msg("❌ No segments were created due to high server demand.")
                
    except Exception as e:
        send_telegram_msg(f"❌ Fatal Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_news_engine())

