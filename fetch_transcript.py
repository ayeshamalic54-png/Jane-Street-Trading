from youtube_transcript_api import YouTubeTranscriptApi

try:
    transcript = YouTubeTranscriptApi.get_transcript('mfDQuupYyE8')
    lines = []
    for item in transcript:
        start_sec = item['start']
        mins = int(start_sec // 60)
        secs = int(start_sec % 60)
        text = item['text']
        lines.append(f"[{mins:02d}:{secs:02d}] {text}")
        
    full_text = "\n".join(lines)
    with open("video_transcript_full.txt", "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"SUCCESS! Saved {len(lines)} lines to video_transcript_full.txt")
except Exception as e:
    print("Error fetching transcript:", e)
