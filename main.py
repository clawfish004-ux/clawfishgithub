import os
import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image

nest_asyncio.apply()

# --- PIL FIXED ---
# Pillow version 10 အထက်မှာ ANTIALIAS မရှိတော့လို့ ဒါလေး ထည့်ပေးရပါတယ်။
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

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

# --- 1. AI IMAGE GENERATION ---
def download_ai_images(prompts):
    print("🎨 Generating & Downloading AI Images...")
    local_files = []
    for i, p in enumerate(prompts):
        encoded_prompt = urllib.parse.quote(p)
        # Video size နဲ့ ကိုက်အောင် 640x360 ပဲ တောင်းလိုက်ပါတယ်
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=640&height=360&nologo=true&seed={i+51}"
        
        filepath = f"img_{i}.jpg"
        img_data = requests.get(url).content
        with open(filepath, "wb") as f:
            f.write(img_data)
        local_files.append(filepath)
    return local_files

# --- 2. VIDEO PRODUCTION ---
def create_story_video(image_files, audio_path, output_path):
    print("🎬 Rendering Video (640x360)...")
    try:
        audio = AudioFileClip(audio_path)
        duration_per_clip = audio.duration / len(image_files)
        
        clips = []
        for img in image_files:
            # size ကို (640, 360) သတ်မှတ်လိုက်ပါတယ်
            clip = ImageClip(img).set_duration(duration_per_clip).resize(newsize=(640, 360))
            clips.append(clip)
        
        video = concatenate_videoclips(clips, method="compose")
        video = video.set_audio(audio)
        
        # GitHub Actions အတွက် ပေါ့ပါးအောင် bitrate လျှော့ထားပါတယ်
        video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="500k", logger=None)
        
        audio.close()
        return output_path
    except Exception as e:
        print(f"Video Production Error: {e}")
        return None

# --- 3. TELEGRAM ---
def send_telegram_video(video_path, caption):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(video_path, "rb") as v:
            requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption})
    except Exception as e:
        print(f"Telegram Send Error: {e}")

# --- MAIN ---
async def main():
    prompts = [
        "Cute shy star cartoon character hiding behind fluffy clouds, night sky, children's book style",
        "Small boy lost in a dark forest, looking up at an empty black sky, emotional illustration",
        "Small glowing star peeking out and shining bright warm light, magical fairytale atmosphere",
        "Happy boy standing in front of his home, twinkling star in the sky, cozy warm night vibe"
    ]
    
    # TTS
    audio_file = "voice.mp3"
    await edge_tts.Communicate(STORY_DATA["content"], VOICE).save(audio_file)
    
    # Images
    img_files = download_ai_images(prompts)
    
    # Video
    video_file = "luma_story.mp4"
    result = create_story_video(img_files, audio_file, video_file)
    
    # Send
    if result:
        print("🚀 Sending to Telegram...")
        send_telegram_video(result, f"🎬 Full Video: {STORY_DATA['title']}\nSize: 640x360")
    
    # Cleanup
    for f in img_files + [audio_file, video_file]:
        if os.path.exists(f): os.remove(f)
    print("✅ Done!")

if __name__ == "__main__":
    asyncio.run(main())

