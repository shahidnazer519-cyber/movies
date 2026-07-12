import os
import re
import subprocess
import requests
import cv2
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai

# ─── CONFIGURATION ───
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
VIDEO_DIR = "videos"
HISTORY_FILE = "history.txt"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def sanitize_filename(filename):
    """صرف انگلش حروف اور نمبرز رکھے گا تاکہ ایرر نہ آئے"""
    return re.sub(r'[^a-zA-Z0-9]', '_', os.path.splitext(filename)[0])

def generate_seo_content(title):
    prompt = f"Create a viral YouTube title, description, keywords, and tags for: '{title}'. Format: TITLE:|DESCRIPTION:|KEYWORDS:|TAGS:"
    response = model.generate_content(prompt)
    text = response.text
    return [line.split(":", 1)[1].strip() for line in text.split("\n") if ":" in line]

def process_video(input_path, output_path):
    # سائز کو بہت زیادہ کمپریس کیا گیا ہے (CRF 32, scale 640p)
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-map_metadata', '-1',
        '-vf', "scale=640:-2,eq=contrast=1.0:brightness=0.0:saturation=1.0,drawbox=y=ih*0.53:h=60:color=black@0.7:t=fill,drawtext=text='Explain With Ali':fontcolor=white:fontsize=20:x=(w-text_w)/2:y=h*0.545",
        '-c:v', 'libx264', '-crf', '32', '-preset', 'veryfast',
        '-c:a', 'aac', '-b:a', '96k', output_path
    ]
    subprocess.run(cmd, check=True)

def main():
    if not os.path.exists(HISTORY_FILE): open(HISTORY_FILE, 'w').close()
    
    videos = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(('.mp4', '.mkv', '.mov'))]
    
    for video in videos:
        safe_name = sanitize_filename(video)
        proc_video = f"{safe_name}.mp4"
        thumb_file = f"{safe_name}.jpg"
        
        # 1. SEO ڈیٹا
        title, desc, kws, tags = generate_seo_content(video)
        
        # 2. تھمب نیل
        cap = cv2.VideoCapture(os.path.join(VIDEO_DIR, video))
        cap.set(cv2.CAP_PROP_POS_FRAMES, 50)
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(thumb_file, frame)
            
        # 3. ویڈیو پروسیسنگ
        process_video(os.path.join(VIDEO_DIR, video), proc_video)
        
        # 4. اپلوڈ
        files = {
            'video': open(proc_video, 'rb'),
            'thumbnail': open(thumb_file, 'rb')
        }
        data = {'title': title, 'description': desc, 'keywords': kws, 'tags': tags}
        
        res = requests.post(MAKE_WEBHOOK_URL, data=data, files=files)
        
        if res.status_code == 200:
            os.remove(os.path.join(VIDEO_DIR, video))
            os.remove(proc_video)
            os.remove(thumb_file)
            print("✅ Uploaded and Cleaned!")
            
if __name__ == "__main__":
    main()
