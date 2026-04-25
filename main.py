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
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
import textwrap

nest_asyncio.apply()

# --- CONFIG ---
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
TT_INTRO_FILE = "sunshinett.mp4"

VOICE_LIST = [
    "my-MM-NanDaNeural",
    "en-US-GuyNeural"
]

FONT_PATH = "NotoSansMyanmar-Bold.ttf"

# --- TELEGRAM ---
def send_msg(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text}
        )
    except Exception as e:
        print(e)

def send_video(video, thumb, caption):
    try:
        with open(video, "rb") as v, open(thumb, "rb") as t:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo",
                files={"video": v, "thumb": t},
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                timeout=300
            )
    except Exception as e:
        send_msg(f"❌ Send Error: {e}")

# --- GEMINI ---
async def get_news(topic):
    prompt = f"""
    {topic} အတွက် မြန်မာလို သတင်းရေးပါ။

    JSON:
    {{
      "news": "...",
      "query": "...",
      "title": "စိတ်ဝင်စားစရာ headline"
    }}
    """

    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        txt = res.text.replace("```", "").strip()
        return json.loads(txt)
    except:
        return {
            "news": topic,
            "query": topic,
            "title": topic
        }

# --- TTS ---
async def generate_audio(text, filename):
    for voice in VOICE_LIST:
        try:
            await edge_tts.Communicate(text, voice).save(filename)
            return filename
        except Exception as e:
            print(f"Voice fail: {voice}")
    return None

# --- IMAGES ---
def fetch_images(query):
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        res = requests.get(
            f"https://api.pexels.com/v1/search?query={query}&per_page=5",
            headers=headers,
            timeout=10
        ).json()

        return [p['src']['large2x'] for p in res.get("photos", [])]
    except:
        return []

# --- THUMBNAIL ---
def create_thumbnail(title, image_url, output):
    try:
        img_data = requests.get(image_url, timeout=10).content
        with open("bg.jpg", "wb") as f:
            f.write(img_data)

        img = Image.open("bg.jpg").convert("RGB")
        img = img.resize((1280, 720))

        # dark overlay
        overlay = Image.new('RGBA', img.size, (0,0,0,120))
        img = Image.alpha_composite(img.convert('RGBA'), overlay)

        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(FONT_PATH, 60)

        title = "🔥 " + title
        lines = textwrap.wrap(title, width=15)

        y = 400
        for line in lines:
            draw.text((52, y+2), line, font=font, fill="black")
            draw.text((50, y), line, font=font, fill="yellow")
            y += 70

        img.convert("RGB").save(output)
        return output

    except Exception as e:
        print("Thumbnail error:", e)
        return None

# --- VIDEO ---
def create_video(images, audio_path, output, size):
    try:
        audio = AudioFileClip(audio_path)

        duration = audio.duration / len(images)
        clips = []

        for i, url in enumerate(images):
            img_data = requests.get(url).content
            path = f"img_{i}.jpg"
            with open(path, "wb") as f:
                f.write(img_data)

            clip = ImageClip(path).set_duration(duration)
            clip = clip.resize(width=size[0])
            clips.append(clip)

        video = concatenate_videoclips(clips).set_audio(audio)
        video.write_videofile(output, fps=24, bitrate="800k", logger=None)

        audio.close()
        video.close()

        return output
    except Exception as e:
        print("Video error:", e)
        return None

# --- MAIN SEGMENT ---
async def create_segment(topic, is_yt=True):
    size = (640, 360) if is_yt else (360, 640)

    data = await get_news(topic)

    safe = topic.replace(" ", "_")

    audio = await generate_audio(data["news"], f"{safe}.mp3")
    if not audio:
        return None, None

    images = fetch_images(data["query"])
    if not images:
        return None, None

    video = create_video(images, audio, f"{safe}.mp4", size)
    thumb = create_thumbnail(data["title"], images[0], f"{safe}.jpg")

    return video, thumb

# --- ENGINE ---
async def run_engine():
    try:
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=6, minutes=30)
        hour = now.strftime("%H")

        send_msg(f"🚀 Sunshine Engine Start: {hour}")

        topics = [
            "World News 2026",
            "Tech & Military",
            "Myanmar News"
        ]

        results = []

        for t in topics:
            v, th = await create_segment(t, True)
            if v and th:
                results.append((v, th))

        for v, th in results:
            send_video(v, th, "☀️ Sunshine AI News")

        # cleanup
        for f in os.listdir():
            if any(x in f for x in [".mp3", ".jpg", "img_"]):
                try:
                    os.remove(f)
                except:
                    pass

        send_msg("✅ Done")

    except Exception as e:
        send_msg(f"❌ Engine Error: {e}")

# --- RUN ---
if __name__ == "__main__":
    asyncio.run(run_engine())
