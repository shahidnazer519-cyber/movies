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
model = genai.GenerativeModel("gemini-1.5-flash")

# فائل کا نام صاف کرنا
def sanitize_filename(filename):
    name, ext = os.path.splitext(filename)
    clean = re.sub(r'[^a-zA-Z0-9]', '_', name)
    return f"{clean}{ext}"

# SEO اور ڈیٹا جنریشن
def get_seo(title):
    prompt = f"For movie: '{title}', give me: YouTube Title, Description, Keywords, Tags. Format: TITLE:|DESCRIPTION:|KEYWORDS:|TAGS:"
    try:
        res = model.generate_content(prompt).text
        return [line.split(":", 1)[1].strip() for line in res.split("\n") if ":" in line]
    except:
        return [title, "Explain with Ali video", "movies, explained", "#movies"]

# پروسیسنگ اور کاپی رائٹ پروٹیکشن
def process_video(input_path, output_path):
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-map_metadata', '-1',
        '-vf', "scale=640:-2,eq=contrast=1.0:saturation=1.0,drawbox=y=ih*0.53:h=60:color=black@0.7:t=fill,drawtext=text='Explain With Ali':fontcolor=white:fontsize=20:x=(w-text_w)/2:y=h*0.545",
        '-c:v', 'libx264', '-crf', '35', '-preset', 'veryfast', 
        '-c:a', 'aac', '-b:a', '64k', output_path
    ]
    subprocess.run(cmd, check=True)

# مین پائپ لائن
def run_pipeline():
    if not os.path.exists(VIDEO_DIR): os.makedirs(VIDEO_DIR)
    videos = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(('.mp4', '.mov', '.mkv'))]
    
    for video in videos:
        # نام صاف کریں
        safe_name = sanitize_filename(video)
        input_path = os.path.join(VIDEO_DIR, video)
        proc_path = f"{safe_name}_proc.mp4"
        thumb_path = f"{safe_name}_thumb.jpg"
        
        try:
            # 1. AI SEO
            title, desc, kws, tags = get_seo(video)
            
            # 2. تھمب نیل
            cap = cv2.VideoCapture(input_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, 50)
            ret, frame = cap.read()
            if ret: cv2.imwrite(thumb_path, frame)
            
            # 3. ویڈیو پروسیس (FFmpeg)
            process_video(input_path, proc_path)
            
            # 4. اپلوڈ
            files = {'video': open(proc_path, 'rb'), 'thumbnail': open(thumb_path, 'rb')}
            data = {'title': title, 'description': desc, 'keywords': kws, 'tags': tags}
            res = requests.post(MAKE_WEBHOOK_URL, data=data, files=files)
            
            # 5. کلین اپ (ڈیلیٹ)
            if res.status_code == 200:
                os.remove(input_path)
                os.remove(proc_path)
                os.remove(thumb_path)
                print(f"✅ Success: {video}")
            else:
                print(f"❌ Webhook Error: {res.text}")
                
        except Exception as e:
            # AI Error Handling
            print(f"⚠️ Error: {e}")
            prompt = f"Explain this error in 1 line: {e}"
            print(f"AI Analysis: {model.generate_content(prompt).text}")

if __name__ == "__main__":
    run_pipeline()
