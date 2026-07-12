import os
import subprocess
import requests

# ─── CONFIGURATION ───
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "YOUR_MAKE_COM_WEBHOOK_URL_HERE")
VIDEO_DIR = "videos"
PROCESSED_DIR = "processed_videos"
HISTORY_FILE = "history.txt"

os.makedirs(PROCESSED_DIR, exist_ok=True)

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_to_history(filename):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(filename + "\n")

def clean_title(filename):
    """
    ویڈیو کے نام سے رینڈم آئی ڈی ہٹا کر ایس ای او فرینڈلی ٹائٹل بناتا ہے۔
    """
    name, _ = os.path.splitext(filename)
    parts = name.split('_')
    
    if len(parts) > 1 and len(parts[-1]) >= 6:
        name = " ".join(parts[:-1])
    else:
        name = name.replace('_', ' ')
        
    return name.strip().title()

def process_video(input_path, output_path):
    print(f"🎬 Processing & Applying Anti-Copyright Filters: {input_path}")
    
    # ─── ADVANCED FFMPEG ANTI-COPYRIGHT COMMAND ───
    # 1. -map_metadata -1: پرانا تمام خفیہ میٹا ڈیٹا اور ہیش ڈیلیٹ کرنا
    # 2. eq=...: کلرز اور کنٹراسٹ میں 1% سے 2% باریک تبدیلی (جو انسان کو محسوس نہیں ہوگی لیکن بوٹس کے لیے ویڈیو نئی بن جائے گی)
    # 3. واٹرمارک ریپلیسمنٹ: 'Explain with Arifa' کو چھپا کر 'Explain With Ali' لگانا
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-map_metadata', '-1',  # 🛡️ تمام پرانا میٹا ڈیٹا اور ہیش اڑا دیں
        '-vf', (
            "scale=720:-2, "                                                    # سائز کنٹرول
            "eq=contrast=1.02:brightness=0.01:saturation=1.02, "                # 🛡️ کلر گریڈنگ (Visual Footprint Change)
            "drawbox=y=ih*0.53:h=60:color=black@0.7:t=fill, "                   # پرانا لوگو کور کرنا
            "drawtext=text='Explain With Ali':fontcolor=white:fontsize=22:"     # نیا برانڈ نیم
            "x=(w-text_w)/2:y=ih*0.545"
        ),
        '-c:v', 'libx264', '-crf', '28', '-preset', 'faster',
        '-c:a', 'aac', '-b:a', '128k',                                          # 🛡️ آڈیو دوبارہ انکوڈ کر کے فٹ پرنٹ بدلنا
        output_path
    ]
    
    subprocess.run(cmd, check=True)
    print(f"✅ Finished Processing (Copyright Protected): {output_path}")

def send_to_webhook(video_path, title):
    print(f"🚀 Sending via Webhook to Make.com: {title}")
    
    payload = {
        "title": f"{title} | Movie Explained in Hindi/Urdu",
        "description": (
            f"Welcome to Explain With Ali! 🎬\n\n"
            f"In this video, we are diving deep into the storyline and complete plot breakdown of: {title}.\n"
            f"We decode the complex ending, character motives, and hidden secrets so you don't miss a single twist.\n\n"
            f"👍 Like this video and Subscribe to 'Explain With Ali' for more international movie breakdowns!"
        ),
        "hashtags": "#ExplainWithAli #MovieExplanation #KoreanMoviesHindi #HollywoodExplained #EndingExplained"
    }
    
    try:
        with open(video_path, 'rb') as f:
            files = {'video': (os.path.basename(video_path), f, 'video/mp4')}
            response = requests.post(MAKE_WEBHOOK_URL, data=payload, files=files)
            
        if response.status_code in [200, 201, 202]:
            print("🎉 Successfully uploaded and triggered Webhook!")
            return True
        else:
            print(f"❌ Webhook Error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to send webhook: {str(e)}")
        return False

def main():
    history = load_history()
    
    if not os.path.exists(VIDEO_DIR):
        os.makedirs(VIDEO_DIR)
        print(f"📁 Created '{VIDEO_DIR}' directory. Please put your videos here.")
        return

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
        
        try:
            # 1. ویڈیو ایڈٹ، کلر چینج اور کمپریس کریں
            process_video(input_path, output_path)
            
            # 2. کلین ایس ای او ٹائٹل بنائیں
            clean_vid_title = clean_title(video)
            
            # 3. ویب ہک پر بھیجیں
            success = send_to_webhook(output_path, clean_vid_title)
            
            if success:
                # 4. ہسٹری میں سیو کریں اور دونوں فائلز ڈیلیٹ کر دیں
                save_to_history(video)
                if os.path.exists(input_path):
                    os.remove(input_path)
                if os.path.exists(output_path):
                    os.remove(output_path)
                print(f"🗑️ Deleted local source and processed files for '{video}' to save storage.")
                
        except Exception as e:
            print(f"⚠️ Error processing '{video}': {str(e)}")

if __name__ == "__main__":
    main()
