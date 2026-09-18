import urllib.request
import json
import re
import html

url = 'https://www.youtube.com/watch?v=mfDQuupYyE8'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
page_html = urllib.request.urlopen(req).read().decode('utf-8')

# Try finding ytInitialPlayerResponse
match = re.search(r'ytInitialPlayerResponse\s*=\s*({.*?});', page_html)
if not match:
    match = re.search(r'\"captionTracks\":(\[.*?\])', page_html)
    if match:
        tracks = json.loads(match.group(1))
    else:
        tracks = []
else:
    player_response = json.loads(match.group(1))
    tracks = player_response.get('captions', {}).get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])

print(f"Found {len(tracks)} caption tracks")
for idx, t in enumerate(tracks):
    track_url = t.get('baseUrl')
    lang = t.get('languageCode')
    print(f"Track {idx}: language {lang}")
    req_t = urllib.request.Request(track_url, headers={'User-Agent': 'Mozilla/5.0'})
    xml_data = urllib.request.urlopen(req_t).read().decode('utf-8')
    xml_data = html.unescape(xml_data)
    
    # Extract text with timestamps
    lines = []
    for m in re.finditer(r'<text start="([\d\.]+)" dur="([\d\.]+)">(.*?)</text>', xml_data):
        start_sec = float(m.group(1))
        mins = int(start_sec // 60)
        secs = int(start_sec % 60)
        txt = re.sub(r'<.*?>', '', m.group(3))
        lines.append(f"[{mins:02d}:{secs:02d}] {txt}")
    
    full_transcript = "\n".join(lines)
    filename = f"yt_transcript_{idx}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(full_transcript)
    print(f"Saved {len(lines)} transcript lines to {filename}")
