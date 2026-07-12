import os
import subprocess
import requests
import google.generativeai as genai
import cv2
from PIL import Image, ImageDraw, ImageFont

# ─── CONFIGURATION ───
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
VIDEO_DIR = "videos"
PROCESSED_DIR = "processed_videos"
HISTORY_FILE = "history.txt"

genai.configure(api_key=GEMINI_API_KEY)

# ─── SMART AUTO GEMINI MODEL SELECTOR ───
def get_auto_gemini_model():
    """
    یہ فنکشن خودکار طریقے سے چیک کرتا ہے کہ گوگل کا سب سے لیٹسٹ
    اور تیز ترین ماڈل (3.5, 3.0, 2.5, یا 1.5) کون سا دستیاب ہے اور اسے سلیکٹ کرتا ہے۔
    """
    try:
        # گوگل سرور سے تمام دستیاب ماڈلز کی لسٹ حاصل کریں جو ٹیکسٹ جنریٹ کر سکتے ہیں
        available_models = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        
        # لیٹسٹ اور تیز ترین ماڈلز کی ترجیحی لسٹ (Priority List)
        priority_models = [
            'models/gemini-3.5-flash',
            'models/gemini-3.5-pro',
            'models/gemini-3.0-flash',
            'models/gemini-2.5-flash',
            'models/gemini-2.5-pro',
            'models/gemini-2.0-flash',
            'models/gemini-1.5-flash',
            'models/gemini-1.5-pro'
        ]
        
        # جو سب سے لیٹسٹ ماڈل آپ کی کی (Key) پر دستیاب ہو اسے فوراً سلیکٹ کریں
        for p_model in priority_models:
            if p_model in available_models:
                print(f"🤖 Auto-Selected Latest Gemini Model: {p_model}")
                return genai.GenerativeModel(p_model)
                
        # اگر ترجیحی لسٹ میں سے کوئی نہ ملے تو لسٹ کا پہلا دستیاب ماڈل لے لیں
        if available_models:
            print(f"🤖 Default Selected Gemini Model: {available_models[0]}")
            return genai.GenerativeModel(available_models[0])
            
    except Exception as e:
        print(f"⚠️ Model Auto-Selection Warning: {e}. Falling back to default.")
        
    # ایمرجنسی فال بیک (اگر انٹرنیٹ یا لسٹنگ میں کوئی مسئلہ ہو)
    return genai.GenerativeModel("gemini-2.5-flash")

# آٹو ماڈل کو انیشلائز کریں
model = get_auto_gemini_model()

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_to_history(filename):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(filename + "\n")

def clean_title(filename):
    name, _ = os.path.splitext(filename)
    parts = name.split('_')
    if len(parts) > 1 and len(parts[-1]) >= 6:
        name = " ".join(parts[:-1])
    else:
        name = name.replace('_', ' ')
    return name.strip().title()

def generate_seo_content(title):
    prompt = f"""
    Create a catchy YouTube-style title, a detailed and SEO-optimized description, for a movie explanation video titled '{title}'.
    Provide the output in the following format exactly:
    TITLE: [Your Title]
    DESCRIPTION: [Your Description]
    """
    try:
        response = model.generate_content(prompt)
        text = response.text
        title_line = text.split("TITLE:")[1].split("DESCRIPTION:")[0].strip()
        desc_line = text.split("DESCRIPTION:")[1].strip()
        return title_line, desc_line
    except Exception as e:
        print(f"⚠️ AI SEO Generation Error: {e}")
        return title, "Detailed movie explanation with Explain With Ali."

def create_thumbnail(video_path, title, output_thumbnail_path):
    print(f"🖼️ Creating thumbnail for: {title}")
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
    ret, frame = cap.read()
    if ret:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except IOError:
            font = ImageFont.load_default()
        draw.text((20, 20), title, fill="white", font=font)
        img.save(output_thumbnail_path)
    cap.release()

def process_video(input_path, output_path):
    print(f"🎬 Processing Video: {input_path}")
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-map_metadata', '-1',
        '-vf', (
            "scale=720:-2, "
            "eq=contrast=1.02:brightness=0.01:saturation=1.02, "
            "drawbox=y=ih*0.53:h=60:color=black@0.7:t=fill, "
            "drawtext=text='Explain With Ali':fontcolor=white:fontsize=22:"
            "x=(w-text_w)/2:y=h*0.545"
        ),
        '-c:v', 'libx264', '-crf', '28', '-preset', 'faster',
        '-c:a', 'aac', '-b:a', '128k',
        output_path
    ]
    subprocess.run(cmd, check=True)
    print(f"✅ Finished Processing: {output_path}")

def send_to_webhook(video_path, thumbnail_path, title, description):
    print(f"🚀 Sending via Webhook to Make.com: {title}")
    payload = {
        "title": title,
        "description": description,
    }
    with open(video_path, 'rb') as f:
        files = {
            'video': (os.path.basename(video_path), f, 'video/mp4'),
            'thumbnail': (os.path.basename(thumbnail_path), open(thumbnail_path, 'rb'), 'image/jpeg')
        }
        response = requests.post(MAKE_WEBHOOK_URL, data=payload, files=files)
    return response.status_code in [200, 201, 202]

def handle_error(error_msg):
    print(f"⚠️ An error occurred: {error_msg}")
    try:
        prompt = f"Analyze the following error that occurred during video automation and explain what went wrong and how to fix it in 2-3 short bullet points:\n\n{error_msg}"
        response = model.generate_content(prompt)
        print(f"🤖 Gemini AI Error Analysis:\n{response.text}")
    except Exception as e:
        print(f"⚠️ Could not generate AI error analysis: {e}")

def main():
    try:
        history = load_history()
        videos = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(('.mp4', '.mkv', '.mov'))]
        if not videos:
            print("📭 No new videos found in the 'videos' folder.")
            return

        for video in videos:
            if video in history:
                print(f"⏭️ Skipping already uploaded video: {video}")
                continue

            input_path = os.path.join(VIDEO_DIR, video)
            output_path = os.path.join(PROCESSED_DIR, f"processed_{video}")
            thumbnail_path = os.path.join(PROCESSED_DIR, f"thumb_{os.path.splitext(video)[0]}.jpg")

            try:
                clean_name = clean_title(video)
                title, description = generate_seo_content(clean_name)
                
                create_thumbnail(input_path, clean_name, thumbnail_path)
                process_video(input_path, output_path)
                
                success = send_to_webhook(output_path, thumbnail_path, title, description)

                if success:
                    save_to_history(video)
                    if os.path.exists(input_path):
                        os.remove(input_path)
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    if os.path.exists(thumbnail_path):
                        os.remove(thumbnail_path)
                    print(f"🗑️ Cleaned up local files for '{video}' to free storage.")
            except Exception as e:
                handle_error(str(e))
    except Exception as e:
        handle_error(str(e))

if __name__ == "__main__":
    main()
