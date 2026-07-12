import os
import re
import subprocess
import requests
import cv2
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai

# CONFIGURATION
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
VIDEO_DIR = "videos"
HISTORY_FILE = "history.txt"

genai.configure(api_key=GEMINI_API_KEY)

# ─── AUTO MODEL SELECTOR ───
def get_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        return genai.GenerativeModel(models[0]) if models else genai.GenerativeModel("gemini-1.5-flash")
    except:
        return genai.GenerativeModel("gemini-1.5-flash")

model = get_model()

# ─── FILENAME CLEANER ───
def get_safe_name(filename):
    return re.sub(r'[^a-zA-Z0-9]', '_', os.path.splitext(filename)[0])

# ─── SEO & CONTENT ───
def get_seo(title):
    prompt = f"Give me: YouTube Title, Description, Keywords, Tags for '{title}'. Format exactly: TITLE:|DESCRIPTION:|KEYWORDS:|TAGS:"
    try:
        res = model.generate_content(prompt).text
        return [line.split(":", 1)[1].strip() for line in res.split("\n") if ":" in line]
    except:
        return [title, "Explanation video", "movie, explained", "#movie"]

# ─── MAIN PROCESSING ───
def run_pipeline():
    if not os.path.exists(VIDEO_DIR): return
    videos = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(('.mp4', '.mov'))]
    
    for video in videos:
        safe = get_safe_name(video)
        input_path = os.path.join(VIDEO_DIR, video)
        proc_path = f"{safe}_proc.mp4"
        thumb_path = f"{safe}.jpg"
        
        # 1. SEO & AI
        title, desc, kws, tags = get_seo(video)
        
        # 2. Thumbnail
        cap = cv2.VideoCapture(input_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(thumb_path, frame)
            
        # 3. Processing (High Compression for 5MB limit)
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-map_metadata', '-1',
            '-vf', "scale=640:-2,eq=contrast=1.0:saturation=1.0,drawbox=y=ih*0.53:h=60:color=black@0.7:t=fill,drawtext=text='Explain With Ali':fontcolor=white:fontsize=20:x=(w-text_w)/2:y=h*0.545",
            '-c:v', 'libx264', '-crf', '35', '-preset', 'veryfast', 
            '-c:a', 'aac', '-b:a', '64k', proc_path
        ]
        subprocess.run(cmd, check=True)
        
        # 4. Upload
        files = {'video': open(proc_path, 'rb'), 'thumbnail': open(thumb_path, 'rb')}
        data = {'title': title, 'description': desc, 'keywords': kws, 'tags': tags}
        
        try:
            res = requests.post(MAKE_WEBHOOK_URL, data=data, files=files)
            if res.status_code == 200:
                print(f"✅ Uploaded {video}")
                os.remove(input_path)
                os.remove(proc_path)
                os.remove(thumb_path)
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_pipeline()
