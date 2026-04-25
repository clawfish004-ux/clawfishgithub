import os
import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse

nest_asyncio.apply()

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
VOICE = "en-US-EmmaNeural"

STORY_DATA = {
    "title": "The Little Star Who Forgot to Shine",
    "content": """
    The Little Star Who Forgot to Shine.
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

# --- AI IMAGE GENERATION (Pollinations AI) ---
def generate_ai_images(prompts):
    print("🎨 Generating AI Images...")
    image_urls = []
    for p in prompts:
        # စာသားကို URL format ပြောင်းပြီး Pollinations ဆီက ပုံတောင်းတာ
        encoded_prompt = urllib.parse.quote(p)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        image_urls.append(url)
    return image_urls

# --- TELEGRAM: SEND ALBUM ---
def send_media_group(images, caption):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMediaGroup"
        media = []
        for i, img_url in enumerate(images):
            media.append({
                "type": "photo",
                "media": img_url,
                "caption": caption if i == 0 else ""
            })
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "media": media})
    except Exception as e:
        print(f"Telegram Error: {e}")

# --- TTS & TELEGRAM AUDIO ---
async def generate_and_send_audio():
    filename = "luma_story.mp3"
    communicate = edge_tts.Communicate(STORY_DATA["content"], VOICE)
    await communicate.save(filename)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
    with open(filename, "rb") as audio:
        requests.post(url, files={"audio": audio}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": "🎙️ AI Voice Story"})
    os.remove(filename)

# --- MAIN ---
async def main():
    # ပုံပြင်ရဲ့ အဓိက အခန်းကဏ္ဍ (၄) ခုကို AI အတွက် Prompt ရေးထားပါတယ်
    prompts = [
        "A cute shy little cartoon star hiding behind a fluffy cloud in a midnight sky, cinematic lighting, 3d render style",
        "A small boy lost in a dark forest looking up at a dark empty sky, sad atmosphere, fairytale illustration",
        "A small glowing star peeking from a cloud shining a bright warm light down on earth, magical atmosphere",
        "A happy boy reaching his cozy house in the night, a small star twinkling brightly in the sky above, warm family vibe"
    ]
    
    # 1. AI နဲ့ ပုံထုတ်မယ်
    image_urls = generate_ai_images(prompts)
    
    # 2. Telegram ကို Album ပို့မယ်
    send_media_group(image_urls, f"✨ AI Illustrations for: {STORY_DATA['title']}")
    
    # 3. အသံဖိုင် ပို့မယ်
    await generate_and_send_audio()
    print("✅ AI Story with Custom Images Sent!")

if __name__ == "__main__":
    asyncio.run(main())

