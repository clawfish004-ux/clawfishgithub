import os
import asyncio
import requests
import nest_asyncio
import edge_tts

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

VOICE = "en-US-EmmaNeural"

STORY_DATA = {
    "title": "The Little Star Who Forgot to Shine",
    "query": "night sky, small star, little boy, dark forest, twinkle star", # ပုံရှာဖို့ Keywords
    "content": """
    Once upon a time, in a quiet night sky, there was a little star named Luma. 
    Unlike the other stars, Luma was shy. She often hid behind clouds because she thought her light was too small.
    One night, the sky became very dark. A lost little boy on Earth was trying to find his way home. 
    He looked up and saw no stars at all.
    The moon whispered gently, "Luma, the boy needs you."
    Luma trembled. "But I’m too small…"
    Still, she slowly peeked out from behind a cloud. She gave the tiniest twinkle she could.
    Down on Earth, the boy saw a soft light. "A star!" he said happily. 
    He followed it step by step until he reached home.
    From that night on, Luma understood something important— even the smallest light can guide someone home.
    And so, she never hid again.
    The end.
    """
}

# --- FETCH IMAGES FROM PEXELS ---
def fetch_story_images(query):
    print(f"🖼️ Fetching images for: {query}")
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        url = f"https://api.pexels.com/v1/search?query={query}&per_page=5"
        res = requests.get(url, headers=headers, timeout=15).json()
        return [p['src']['large2x'] for p in res.get("photos", [])]
    except Exception as e:
        print(f"Pexels Error: {e}")
        return []

# --- TELEGRAM: SEND MEDIA GROUP (Album) ---
def send_media_group(images, caption):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMediaGroup"
        media = []
        for i, img_url in enumerate(images):
            media.append({
                "type": "photo",
                "media": img_url,
                "caption": caption if i == 0 else "" # ပထမဆုံးပုံမှာပဲ စာတန်းထည့်မယ်
            })
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "media": media
        }
        requests.post(url, json=payload)
        print("✅ Images sent as album")
    except Exception as e:
        print(f"Telegram Media Error: {e}")

# --- TTS ---
async def generate_mp3(text, filename):
    try:
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(filename)
        return filename
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

def send_audio(audio_path, caption):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
        with open(audio_path, "rb") as audio:
            files = {"audio": audio}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            requests.post(url, files=files, data=data)
    except Exception as e:
        print(f"Audio Error: {e}")

# --- MAIN RUN ---
async def run_story_with_images():
    # 1. Generate Audio
    audio_file = await generate_mp3(STORY_DATA["content"], "luma.mp3")
    
    # 2. Fetch Images
    image_urls = fetch_story_images(STORY_DATA["query"])
    
    # 3. Send to Telegram
    if image_urls:
        send_media_group(image_urls, f"📸 Visuals for: {STORY_DATA['title']}")
    
    if audio_file:
        send_audio(audio_file, f"🎙️ Audio Story: {STORY_DATA['title']}")
        os.remove(audio_file)
        print("✅ Done!")

if __name__ == "__main__":
    asyncio.run(run_story_with_images())

