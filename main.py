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
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
VOICE = "en-US-EmmaNeural"

# ပုံပြင်အသစ် စာသားထည့်သွင်းခြင်း
STORY_DATA = {
    "title": "The Brave Little Turtle",
    "content": """
    The Brave Little Turtle. In a green forest near a river, there lived a little turtle named Toby. 
    All the animals in the forest were fast and strong, but Toby was slow. 
    The rabbit often laughed. "You will never be fast like us!" Toby felt sad, but he kept quiet. 
    One day, heavy rain came, and the river began to rise. The water started flooding the forest. 
    All the animals ran quickly to the hill, but a small baby bird was stuck on a low branch near the water. 
    "Help!" the bird cried. The fast animals were already far away. Only Toby was still nearby. 
    Slowly, step by step, Toby walked into the rising water. He reached the branch and said, "Climb on my back!" 
    The bird climbed on, and Toby carefully carried it to safety. 
    When they reached the hill, all the animals cheered. 
    The rabbit said, "We were wrong. You are the bravest of all." 
    Toby smiled. He didn’t need to be fast—he just needed to be kind and brave. The end.
    """
}

# --- 1. AI IMAGE GENERATION ---
def download_ai_images(prompts):
    print("🎨 Generating Images for Toby the Turtle...")
    local_files = []
    for i, p in enumerate(prompts):
        encoded_prompt = urllib.parse.quote(p)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&nologo=true&seed={i+200}"
        filepath = f"img_{i}.jpg"
        with open(filepath, "wb") as f:
            f.write(requests.get(url).content)
        local_files.append(filepath)
    return local_files

# --- 2. VIDEO PRODUCTION ---
def create_fancy_video(image_files, audio_path, output_path):
    print("🎬 Rendering Toby's Story Video...")
    try:
        audio = AudioFileClip(audio_path)
        duration_per_clip = audio.duration / len(image_files)
        overlap = 1.0 
        
        clips = []
        for img in image_files:
            clip = (ImageClip(img)
                    .set_duration(duration_per_clip + overlap)
                    .resize(lambda t: 1 + 0.04 * t)
                    .set_fps(24)
                    .resize(newsize=(640, 360))
                    .crossfadein(overlap))
            clips.append(clip)
        
        video = concatenate_videoclips(clips, method="compose", padding=-overlap)
        video = video.set_audio(audio)
        
        video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", bitrate="800k", logger=None)
        audio.close()
        return output_path
    except Exception as e:
        print(f"Video Error: {e}")
        return None

# --- TELEGRAM ---
def send_telegram_video(video_path, caption):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(video_path, "rb") as v:
            requests.post(url, files={"video": v}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption})
    except Exception as e:
        print(f"Telegram Error: {e}")

# --- MAIN ---
async def main():
    # Toby အတွက် Scene Prompts ၅ ခု ပြင်ထားပါတယ်
    prompts = [
        "Cute little turtle Toby in a lush green forest near a sparkling river, 3D Pixar style, bright colors",
        "A fast rabbit laughing at a slow turtle in a forest, sunny day, cartoon illustration",
        "Heavy rain flooding a green forest, rising river water, dramatic atmosphere",
        "A brave turtle swimming in water to save a small baby bird on a tree branch, heroic scene",
        "All forest animals cheering for a small turtle on a sunny hill, warm ending, happy vibe"
    ]
    
    # Generate Audio
    audio_file = "voice.mp3"
    await edge_tts.Communicate(STORY_DATA["content"], VOICE).save(audio_file)
    
    # Generate Images
    img_files = download_ai_images(prompts)
    
    # Create Video
    video_file = "toby_story.mp4"
    result = create_fancy_video(img_files, audio_file, video_file)
    
    # Send
    if result:
        send_telegram_video(result, f"🐢 {STORY_DATA['title']}\nA story about courage and kindness. #KidsStory")
    
    # Cleanup
    for f in img_files + [audio_file, video_file]:
        if os.path.exists(f): os.remove(f)
    print("✅ Toby's Video Completed!")

if __name__ == "__main__":
    asyncio.run(main())

