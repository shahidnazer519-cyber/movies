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

# جیمنائی اے پی آئی سیٹ اپ
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ─── SMART AUTO GEMINI MODEL SELECTOR ───
def get_auto_gemini_model():
    """جیمنائی کا تیز ترین اور لیٹسٹ ماڈل خودکار طریقے سے سلیکٹ کرتا ہے"""
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority_models = [
            'models/gemini-3.5-flash', 'models/gemini-3.0-flash',
            'models/gemini-2.5-flash', 'models/gemini-2.0-flash',
            'models/gemini-1.5-flash'
        ]
        for p_model in priority_models:
            if p_model in available_models:
                print(f"🤖 Selected Gemini Model: {p_model}")
                return genai.GenerativeModel(p_model)
        if available_models:
            return genai.GenerativeModel(available_models[0])
    except Exception as e:
        print(f"⚠️ Gemini Model Selection Warning: {e}")
    return genai.GenerativeModel("gemini-1.5-flash")

model = get_auto_gemini_model()
os.makedirs(VIDEO_DIR, exist_ok=True)

# ─── FILENAME SANITIZER ───
def sanitize_filename(filename):
    """نام سے #، سپیس اور اسپیشل کریکٹرز ہٹا کر محفوظ بناتا ہے"""
    name, ext = os.path.splitext(filename)
    clean_name = re.sub(r'[^a-zA-Z0-9]', '_', name)
    clean_name = re.sub(r'_+', '_', clean_name).strip('_')
    return f"{clean_name}{ext}"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_to_history(filename):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(filename + "\n")

def clean_title_for_ai(filename):
    name, _ = os.path.splitext(filename)
    parts = name.split('_')
    if len(parts) > 1 and len(parts[-1]) >= 6:
        name = " ".join(parts[:-1])
    else:
        name = name.replace('_', ' ')
    return name.strip().title()

# ─── AI SEO GENERATOR (TITLE, DESC, KEYWORDS, TAGS) ───
def generate_seo_content(title):
    print(f"🤖 Generating AI SEO (Title, Description, Keywords, Tags) for: {title}")
    prompt = f"""
    You are an expert YouTube SEO specialist. For a movie explanation video titled '{title}' on the channel 'Explain With Ali', generate:
    1. A catchy, viral, high-CTR YouTube Title (in Hindi/Urdu context).
    2. A detailed, professional, SEO-optimized Description.
    3. High-ranking search Keywords (comma-separated).
    4. Viral Hashtags/Tags.

    Provide EXACTLY in this format without any extra markdown:
    TITLE: [Your Title]
    DESCRIPTION: [Your Description]
    KEYWORDS: [Keyword1, Keyword2, Keyword3, ...]
    TAGS: [#tag1 #tag2 #tag3 ...]
    """
    try:
        response = model.generate_content(prompt)
        text = response.text
        title_val = text.split("TITLE:")[1].split("DESCRIPTION:")[0].strip()
        desc_val = text.split("DESCRIPTION:")[1].split("KEYWORDS:")[0].strip()
        keywords_val = text.split("KEYWORDS:")[1].split("TAGS:")[0].strip()
        tags_val = text.split("TAGS:")[1].strip()
        return title_val, desc_val, keywords_val, tags_val
    except Exception as e:
        print(f"⚠️ AI SEO Generation failed: {e}. Using fallback SEO.")
        fallback_desc = f"Welcome to Explain With Ali! 🎬\n\nIn this video, we provide a complete plot breakdown and explanation of '{title}'. We decode the complex ending and hidden secrets!\n\n👍 Like and Subscribe to Explain With Ali!"
        return f"{title} | Movie Explained in Hindi/Urdu", fallback_desc, f"{title}, movie explained, ending explained, explain with ali, hindi explanation", "#ExplainWithAli #MovieExplanation #EndingExplained #HindiUrdu"

# ─── AI THUMBNAIL GENERATOR ───
def create_thumbnail(video_path, title, output_thumb_path):
    print(f"🖼️ Creating Thumbnail for: {title}")
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(1, total_frames // 2))
    ret, frame = cap.read()
    if ret:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 45)
        except IOError:
            font = ImageFont.load_default()
        # ٹائٹل کا پہلا حصہ تھمب نیل پر لکھنا
        short_title = title[:25] + "..." if len(title) > 25 else title
        draw.text((30, 30), f"EXPLAINED:\n{short_title}", fill="yellow", font=font)
        img.save(output_thumb_path, "JPEG", quality=90)
    cap.release()

# ─── FFMPEG ANTI-COPYRIGHT & WATERMARK PROCESSING ───
def process_video(input_path, output_path):
    print(f"🎬 Processing & Applying Anti-Copyright Filters: {input_path}")
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-map_metadata', '-1',  # تمام خفیہ میٹا ڈیٹا اور ہیش ڈیلیٹ
        '-vf', (
            "scale=720:-2, "  # سائز آپٹمائزیشن
            "eq=contrast=1.02:brightness=0.01:saturation=1.02, "  # کلر گریڈنگ (Visual Footprint Change)
            "drawbox=y=ih*0.53:h=60:color=black@0.7:t=fill, "  # پرانا لوگو کور کرنا
            "drawtext=text='Explain With Ali':fontcolor=white:fontsize=22:x=(w-text_w)/2:y=h*0.545"  # نیا برانڈ
        ),
        '-c:v', 'libx264', '-crf', '28', '-preset', 'faster',
        '-c:a', 'aac', '-b:a', '128k',  # آڈیو ری-انکوڈنگ
        output_path
    ]
    subprocess.run(cmd, check=True)
    print("✅ Video processing complete!")

# ─── WEBHOOK SENDER (MAKE.COM) ───
def send_to_webhook(video_path, thumb_path, title, desc, keywords, tags):
    print(f"🚀 Sending via Webhook to Make.com: {title}")
    payload = {
        "title": title,
        "description": desc,
        "keywords": keywords,
        "tags": tags,
        "channel": "Explain With Ali"
    }
    try:
        with open(video_path, 'rb') as vf, open(thumb_path, 'rb') as tf:
            files = {
                'video': (os.path.basename(video_path), vf, 'video/mp4'),
                'thumbnail': (os.path.basename(thumb_path), tf, 'image/jpeg')
            }
            response = requests.post(MAKE_WEBHOOK_URL, data=payload, files=files)
        if response.status_code in [200, 201, 202]:
            print("🎉 Successfully uploaded and triggered Webhook!")
            return True
        else:
            print(f"❌ Webhook Error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to send webhook: {e}")
        return False

# ─── AI ERROR HANDLER ───
def handle_error_with_ai(error_msg):
    print(f"⚠️ Error occurred: {error_msg}")
    try:
        prompt = f"Explain this Python/FFmpeg error in 2 bullet points and suggest a quick fix:\n\n{error_msg}"
        response = model.generate_content(prompt)
        print(f"🤖 Gemini AI Error Diagnosis:\n{response.text}")
    except Exception as e:
        print(f"⚠️ Could not generate AI diagnosis: {e}")

# ─── MAIN AUTOMATION PIPELINE (NO EXTRA FOLDERS) ───
def main():
    try:
        history = load_history()
        videos = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(('.mp4', '.mkv', '.mov'))]
        
        if not videos:
            print("📭 No new videos found in 'videos/' folder.")
            return

        for video in videos:
            if video in history:
                print(f"⏭️ Skipping already uploaded video: {video}")
                continue

            original_path = os.path.join(VIDEO_DIR, video)
            safe_filename = sanitize_filename(video)
            
            # پروسیسڈ ویڈیو اور تھمب نیل کسی الگ فولڈر میں نہیں بلکہ عارضی نام سے روٹ پر ہی بنیں گے
            temp_proc_video = f"temp_proc_{safe_filename}"
            temp_thumb = f"temp_thumb_{os.path.splitext(safe_filename)[0]}.jpg"

            try:
                # 1. ٹائٹل کلین کریں اور ایس ای او (Keywords/Tags/Desc) بنائیں
                clean_name = clean_title_for_ai(video)
                title, desc, keywords, tags = generate_seo_content(clean_name)
                
                # 2. تھمب نیل اور ویڈیو پروسیس کریں
                create_thumbnail(original_path, clean_name, temp_thumb)
                process_video(original_path, temp_proc_video)
                
                # 3. ویب ہک پر مکمل ڈیٹا بھیجیں
                success = send_to_webhook(temp_proc_video, temp_thumb, title, desc, keywords, tags)

                if success:
                    # 4. ہسٹری میں سیو کریں اور فوراً تمام فائلز ڈیلیٹ کر دیں (زیرو سٹوریج ویسٹیج!)
                    save_to_history(video)
                    if os.path.exists(original_path): os.remove(original_path)
                    if os.path.exists(temp_proc_video): os.remove(temp_proc_video)
                    if os.path.exists(temp_thumb): os.remove(temp_thumb)
                    print(f"🗑️ Successfully deleted all local files for '{video}'. Storage completely cleaned!")
                else:
                    print(f"⚠️ Webhook failed for '{video}'. Files retained for retry.")
                    
            except Exception as e:
                handle_error_with_ai(str(e))
                # ارر کی صورت میں بھی عارضی فائلز ڈیلیٹ کر دیں تاکہ سرور فل نہ ہو
                if os.path.exists(temp_proc_video): os.remove(temp_proc_video)
                if os.path.exists(temp_thumb): os.remove(temp_thumb)

    except Exception as e:
        handle_error_with_ai(str(e))

if __name__ == "__main__":
    main()
