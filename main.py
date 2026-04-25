# Test Topics for Quick Production
        topics = ["World Politics 2026", "Global Economy"]
        
        # YouTube Video Production
        send_telegram_msg("🎬 Creating YouTube News Video...")
        yt_segs = []
        for t in topics:
            seg = await create_segment(t, is_yt=True)
            if seg: yt_segs.append(seg)

        if yt_segs:
            intro = VideoFileClip(YT_INTRO_FILE).resize((640, 360))
            clips = [intro] + [VideoFileClip(s) for s in yt_segs]
            final = concatenate_videoclips(clips, method="compose")
            final.write_videofile("YT_Final.mp4", codec="libx264", audio_codec="aac")
            final.close()
            send_telegram_video("YT_Final.mp4", "✅ Manual Test Success: YouTube Video is ready!")
            for c in clips: c.close()
        else:
            send_telegram_msg("❌ Error: No video segments were created.")

        # Cleanup files
        for f in os.listdir():
            if any(x in f for x in ["audio_", "i_", "seg_", "Final"]) and f not in [YT_INTRO_FILE, TT_INTRO_FILE]:
                try: os.remove(f)
                except: pass
                
    except Exception as e:
        send_telegram_msg(f"❌ Detail Error: {str(e)}")

if name == "main":
    asyncio.run(run_clawfish_engine())
