import base64
import os
import uuid
import json
import mimetypes
import requests
from dotenv import load_dotenv
from google import genai
from PIL import Image
load_dotenv()

# GEMINI - ANALYSIS
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def analyze_thumbnail(image_path):
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
    mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    prompt = """
        Analyze this YouTube thumbnail and return ONLY valid JSON.
        Use this structure:
        {
            "detected_text": "All clearly visible text in the thumbnail",
            "ai_analysis": "Detailed analysis of visual quality, colors, text readability, composition, and improvement suggestions.",
            "ctr_prediction": {"click_probability": 0,"engagement_potential": 0,"predicted_ctr_score": 0,"message": "Short explanation"}
        }

        Rules:
            - detected_text must contain the actual visible words.
            - Preserve spelling as accurately as possible.
            - If there is no visible text, return "No text detected."
            - Use scores between 0 and 100.
            - Estimate scores using visual features only.
            - Do not claim these are actual measured CTR values.
            - Provide practical improvement suggestions.
        """
    models = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]

    last_error = None

    for model in models:
        try:
            print(f"Trying Gemini model: {model}")
            response = client.models.generate_content(model=model, contents=[{"inline_data": {"mime_type": mime_type,"data": image_data}},prompt])
            raw_text = (response.text or "").strip()

            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```json", "")
                raw_text = raw_text.replace("```", "").strip()

            result = json.loads(raw_text)
            print(f"Gemini analysis successful using: {model}")
            return result

        except Exception as e:
            last_error = str(e)
            print(f"{model} failed: {last_error}")

    return {
        "ai_analysis": "AI recommendations are temporarily unavailable. Please try again later.",
        "ctr_prediction": {
            "click_probability": None,
            "engagement_potential": None,
            "predicted_ctr_score": None,
            "message": "AI CTR prediction unavailable."
        }
    }

# CLOUDFLARE FLUX - BUILDER
def generate_thumbnail_from_prompt(prompt, aspect_ratio="16:9"):
    print("Starting Cloudflare thumbnail generation...")

    try:
        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        api_token = os.getenv("CLOUDFLARE_API_TOKEN")

        if not account_id:
            return {"success": False, "error": "CLOUDFLARE_ACCOUNT_ID is missing in .env"}

        if not api_token:
            return {"success": False,"error": "CLOUDFLARE_API_TOKEN is missing in .env"}

        model = "@cf/black-forest-labs/flux-1-schnell"
        api_url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/ai/run/{model}"
        )
        headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

        # Add thumbnail-specific instructions
        final_prompt = f"""
            Create a professional YouTube thumbnail.
            {prompt}
            Requirements:
            - cinematic and eye-catching
            - strong focal subject
            - high contrast
            - dramatic lighting
            - clean composition
            - professional YouTube thumbnail style
            - 16:9 composition
            - leave some empty space for headline text
            - no watermark
        """

        payload = {"prompt": final_prompt,"steps": 4}
        print("Sending request to Cloudflare FLUX...")
        response = requests.post( api_url, headers=headers, json=payload, timeout=120)
        print("Cloudflare response:", response.status_code)

        if response.status_code != 200:
            return {"success": False, "error": f"Cloudflare API error {response.status_code}: {response.text}"}

        data = response.json()

        if not data.get("success"):
            return {"success": False,"error": f"Cloudflare generation failed: {data}"}

        image_base64 = data["result"]["image"]

        # Decode Base64
        image_bytes = base64.b64decode(image_base64)

        output_folder = "static/uploads"
        os.makedirs(output_folder, exist_ok=True)

        temp_filename = f"ai_temp_{uuid.uuid4().hex}.jpg"
        temp_path = os.path.join(output_folder, temp_filename)

        with open(temp_path, "wb") as image_file:
            image_file.write(image_bytes)

        # CONVERT TO 16:9 THUMBNAIL
        image = Image.open(temp_path).convert("RGB")
        target_width = 1280
        target_height = 720
        target_ratio = target_width / target_height
        image_ratio = image.width / image.height

        if image_ratio > target_ratio:
            # Image is too wide
            new_width = int(image.height * target_ratio)
            left = (image.width - new_width) // 2
            image = image.crop((left, 0, left + new_width, image.height))

        else:
            # Image is too tall
            new_height = int(image.width / target_ratio)
            top = (image.height - new_height) // 2
            image = image.crop((0, top, image.width, top + new_height))

        image = image.resize((target_width, target_height),Image.LANCZOS)
        filename = f"ai_{uuid.uuid4().hex}.jpg"
        output_path = os.path.join(output_folder, filename)
        image.save(output_path, "JPEG", quality=95)

        # Remove temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        print("Cloudflare thumbnail generated successfully.")
        return {"success": True,"image_url": "/" + output_path.replace("\\", "/")}

    except Exception as e:
        print("Cloudflare generation error:", str(e))
        return {"success": False,"error": str(e)}