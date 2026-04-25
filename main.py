import os
import asyncio
import requests
import nest_asyncio
import edge_tts

nest_asyncio.apply()

# --- CONFIG ---
# Gemini မသုံးတော့တဲ့အတွက် API KEY မလိုပါဘူး
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# English Voice Selection
VOICE = "en-US-EmmaNeural" # ပုံပြင်လေးဆိုတော့ အမျိုးသမီးအသံ Emma နဲ့ ပိုလိုက်ဖက်နိုင်ပါတယ်

# --- DIRECT STORY DATA ---
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

# --- TELEGRAM ---
def send_msg(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text}
        )
    except Exception as e:
        print(f"Error: {e}")

def send_audio(audio_path, caption):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
        with open(audio_path, "rb") as audio:
            files = {"audio": audio}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            res = requests.post(url, files=files, data=data)
            print(f"Telegram status: {res.status_code}")
    except Exception as e:
        print(f"❌ Telegram Send Error: {e}")

# --- TTS ---
async def generate_mp3(text, filename):
    try:
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(filename)
        return filename
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

# --- RUN TEST ---
async def run_story_test():
    print(f"🚀 Processing Story: {STORY_DATA['title']}")
    
    filename = "luma_story.mp3"
    
    # Generate Audio from the hardcoded story
    audio_file = await generate_mp3(STORY_DATA["content"], filename)
    
    if audio_file and os.path.exists(audio_file):
        caption = f"⭐ Story Audio Test\nTitle: {STORY_DATA['title']}\nVoice: {VOICE}"
        send_audio(audio_file, caption)
        print("✅ Story MP3 sent to Telegram!")
        
        # Cleanup
        if os.path.exists(audio_file):
            os.remove(audio_file)
    else:
        print("❌ Failed to generate MP3")

if __name__ == "__main__":
    asyncio.run(run_story_test())

