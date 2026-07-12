import os
import requests
import sys
import warnings

# 1. Pillow کی وارننگز کو خودکار خاموش کرنا
warnings.filterwarnings("ignore", category=DeprecationWarning)
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

from moviepy.editor import VideoFileClip
from google import genai 

# کانفیگریشن اور سیٹنگز
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAKE_WEBHOOK_URL = os.getenv("BUFFER_WEBHOOK_URL")
VIDEOS_DIR = "videos"
HISTORY_FILE = "history.txt"

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def get_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f)

def add_to_history(filename):
    with open(HISTORY_FILE, "a") as f:
        f.write(filename + "\n")

def process_video_hd(input_path, output_path):
    """ویڈیو کو 720p پر ری سائز اور کمپریس کرنا تاکہ سائز 5MB کے اندر رہے"""
    clip = VideoFileClip(input_path)
    processed_clip = clip.fx(lambda c: c.resize(1.01))
    
    processed_clip.write_videofile(
        output_path, 
        codec="libx264", 
        audio_codec="aac",
        bitrate="800k",
        preset="fast",   
        ffmpeg_params=["-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280"]
    )
    clip.close()
    processed_clip.close()

def generate_seo(topic_name):
    """جیمنائی سے صرف ایک فائنل اور صاف ستھرا ایس ای او ڈیٹا لینا"""
    default_seo = f"Title: {topic_name} 😱\n\nDescription: Amazing facts about {topic_name}. Subscribe for more!\n\n#Shorts #Facts #Viral"
    
    if not client:
        return default_seo
        
    try:
        # جیمنائی کو سخت انسٹرکشن تاکہ وہ آپشنز نہ بنائے
        prompt = (
            f"You are an expert YouTube Shorts SEO manager. Create metadata for a video about: '{topic_name}'.\n"
            "CRITICAL REQUIRED FORMAT:\n"
            "Provide exactly ONE viral title, ONE short engaging description, and ONE block of hashtags.\n"
            "DO NOT provide Option 1, Option 2, or multiple choices. DO NOT include introductory text like 'Here are options' or conversational filler or tips. "
            "Just output the final clean text that can be directly posted."
        )
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ Gemini Error: {e}")
        return default_seo

def main():
    if not os.path.exists(VIDEOS_DIR):
        os.makedirs(VIDEOS_DIR)
        return

    history = get_history()
    files = [f for f in os.listdir(VIDEOS_DIR) if f.lower().endswith(('.mp4', '.mov'))]
    target_video = None
    
    for f in files:
        if f not in history:
            target_video = f
            break
            
    if not target_video:
        print("✅ تمام ویڈیوز اپلوڈ ہو چکی ہیں یا کوئی نئی ویڈیو نہیں ملی۔")
        return

    input_path = os.path.join(VIDEOS_DIR, target_video)
    output_path = os.path.join(VIDEOS_DIR, "processed_" + target_video)
    
    # 🛑 نام سے یوٹیوب کی فالتو آئی ڈی (مثلًا __3CGI04KITMI) کو صاف کرنا
    base_name = os.path.splitext(target_video)[0]
    if "__" in base_name:
        clean_topic = base_name.split("__")[0].strip()
    else:
        clean_topic = base_name.strip()
        
    print(f"🎬 Processing Video: {clean_topic}")
    try:
        process_video_hd(input_path, output_path)
    except Exception as e:
        print(f"❌ ویڈیو ایڈیٹنگ فیل ہو گئی: {e}")
        return
    
    print("🤖 Generating Clean SEO with Gemini...")
    seo_text = generate_seo(clean_topic)
    
    print("🚀 Sending to Make.com Webhook...")
    try:
        with open(output_path, 'rb') as f:
            files_dict = {"video_file": (target_video, f, "video/mp4")}
            # یہاں اب ویڈیو کا نام اور ٹاپک بالکل کلین (بغیر آئی ڈی کے) جا رہا ہے
            data_dict = {"video_name": clean_topic, "seo_data": seo_text, "topic": clean_topic}
            res = requests.post(MAKE_WEBHOOK_URL, data=data_dict, files=files_dict)
            
        if res.status_code in [200, 201]:
            print("🚀 Successfully uploaded to Make.com!")
            add_to_history(target_video)
            
            os.remove(input_path)
            os.remove(output_path)
            print("🗑️ Cleaned up: Files deleted successfully.")
        else:
            print(f"❌ Webhook Error! Code: {res.status_code}")
            if os.path.exists(output_path): os.remove(output_path)
            
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        if os.path.exists(output_path): os.remove(output_path)

if __name__ == "__main__":
    main()
