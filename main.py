import os
import asyncio
import requests
import nest_asyncio
import edge_tts
import urllib.parse
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

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

# --- 1. AI IMAGE GENERATION (Download to local) ---
def download_ai_images(prompts):
    print("🎨 Generating & Downloading AI Images...")
    local_files = []
    for i, p in enumerate(prompts):
        encoded_prompt = urllib.parse.quote(p)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=768&nologo=true&seed={i}"
        
        filepath = f"img_{i}.jpg"
        img_data = requests.get(url).content
        with open(filepath, "wb") as f:
            f.write(img_data)
        local_files.append(filepath)
    return local_files

# --- 2. VIDEO PRODUCTION ---
def create_story_video(image_files, audio_path, output_path):
    print("🎬 Rendering Video...")
    try:
        audio = AudioFileClip(audio_path)
        # ပုံတစ်ပုံချင်းစီကို အချိန်ဘယ်လောက်ပြမလဲဆိုတာ တွက်တာ (Audio duration / ပုံအရေအတွက်)
        duration_per_clip = audio.duration / len(image_files)
        
        clips = []
        for img in image_files:
            clip = ImageClip(img).set_duration(duration_per_clip).resize(height=720)
            clips.append(clip)
        
        video = concatenate_videoclips(clips, method="compose")
        video = video.set_audio(audio)
        
        # GitHub Action မှာ run မှာဖြစ်လို့ bitrate ကို နည်းနည်းလျှော့ထားပါတယ်
        video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", temp_audiofile="temp-audio.m4a", remove_temp=True)
        
        audio.close()
        return output_path
    except Exception as e:
        print(f"Video Error: {e}")
        return None

# --- 3. TELEGRAM SEND VIDEO ---
def send_telegram_video(video_path, caption):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(video_path, "rb") as v:
            requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption})
    except Exception as e:
        print(f"Telegram Send Error: {e}")

# --- MAIN ---
async def main():
    # Prompts for scenes
    prompts = [
        "Cute shy cartoon star hiding behind clouds, midnight sky, high quality illustration",
        "A small boy lost in dark forest, looking at dark empty sky, storybook style",
        "A small star twinkling bright light from behind a cloud, magic glow",
        "Happy boy back at home, glowing house, star shining in the sky, warm ending"
    ]
    
    # Step 1: TTS
    print("🎙️ Generating Voice...")
    audio_file = "voice.mp3"
    await edge_tts.Communicate(STORY_DATA["content"], VOICE).save(audio_file)
    
    # Step 2: Images
    img_files = download_ai_images(prompts)
    
    # Step 3: Video
    video_file = "luma_story_video.mp4"
    result = create_story_video(img_files, audio_file, video_file)
    
    # Step 4: Send
    if result:
        print("🚀 Sending to Telegram...")
        send_telegram_video(result, f"🎬 Full Story Video: {STORY_DATA['title']}")
    
    # Cleanup
    for f in img_files + [audio_file, video_file]:
        if os.path.exists(f): os.remove(f)
    print("✅ Process Completed!")

if __name__ == "__main__":
    asyncio.run(main())

