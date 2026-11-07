import pytesseract
import cv2
import os
import uuid
import numpy as np
from PIL import Image, ImageStat
from dotenv import load_dotenv

load_dotenv()

import shutil

if os.name == "nt":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
else:
    pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
# IMAGE ANALYSIS
def analyze_image(image_path):
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    stats = ImageStat.Stat(image)
    brightness = sum(stats.mean) / 3
    cv_image = cv2.imread(image_path)
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    contrast = gray.std()
    aspect_ratio = round(width / height, 2)
    resolution_score = (20 if width >= 1280 and height >= 720 else 10)
    brightness_score = (20 if 70 <= brightness <= 190 else 10)
    contrast_score = (20 if contrast >= 40 else 10)
    aspect_score = (20 if 1.6 <= aspect_ratio <= 1.85 else 10)
    sharpness = cv2.Laplacian( gray, cv2.CV_64F).var()
    sharpness_score = (20 if sharpness >= 100 else 10)
    quality_score = (resolution_score + brightness_score + contrast_score + aspect_score + sharpness_score)

    return {
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "brightness": round(brightness, 2),
        "contrast": round(float(contrast), 2),
        "sharpness": round(float(sharpness), 2),
        "quality_score": quality_score,
        "resolution": f"{width}x{height}"
    }

# OCR
def run_ocr(image):
    data = pytesseract.image_to_data(image,config="--oem 3 --psm 11", output_type=pytesseract.Output.DICT)
    words = []
    confidences = []

    for i, word in enumerate(data["text"]):
        word = word.strip()
        try:
            confidence = float(data["conf"][i])
        except:
            confidence = 0

        if word and confidence >= 30:
            # Remove very short OCR noise
            if len(word) >= 2:
                words.append(word)
                confidences.append(confidence)
    text = " ".join(words).strip()
    average_confidence = (sum(confidences) / len(confidences) if confidences else 0)
    return text, average_confidence, len(words)

def detect_text(image_path):
    image = cv2.imread(image_path)
    if image is None:
        return {"success": False,"text_detected": False,"extracted_text": "","word_count": 0,"confidence": 0,"error": "Unable to read image"}

    image = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    data = pytesseract.image_to_data(gray,config="--oem 3 --psm 11",output_type=pytesseract.Output.DICT)
    words = []
    confidences = []

    for i, word in enumerate(data["text"]):
        word = word.strip()
        try:
            confidence = float(data["conf"][i])
        except:
            confidence = 0

        if word and confidence >= 30:
            words.append(word)
            confidences.append(confidence)
    text = " ".join(words).strip()
    average_confidence = (sum(confidences) / len(confidences)if confidences else 0)

    return {
        "success": True,
        "text_detected": bool(text),
        "extracted_text": text if text else "No text detected.",
        "word_count": len(words),
        "confidence": round(average_confidence, 2)
    }

# CTR PREDICTION
def predict_ctr(image_analysis, text_analysis):
    quality_score = image_analysis.get("quality_score", 0)
    brightness = image_analysis.get("brightness", 0)
    contrast = image_analysis.get("contrast", 0)
    width = image_analysis.get("width", 0)
    height = image_analysis.get("height", 0)
    text_detected = text_analysis.get("text_detected", False)
    extracted_text = text_analysis.get("extracted_text","")
    score = 0
    score += quality_score * 0.45

    if 35 <= contrast <= 100:
        score += 15

    elif contrast > 20:
        score += 8

    if 40 <= brightness <= 210:
        score += 10

    if width >= 1280 and height >= 720:
        score += 10

    if text_detected and extracted_text.strip():
        score += 10
    score = min(round(score), 100)
    click_probability = min(round(score * 0.9), 95)
    engagement_potential = min(round(score * 0.95), 98)

    return {
        "predicted_ctr_score": score,
        "click_probability": click_probability,
        "engagement_potential": engagement_potential,
        "message": "Estimated using thumbnail visual features"
    }

# HEATMAP ANALYSIS
def analyze_heatmap(image_path):
    image = cv2.imread(image_path)

    if image is None:
        raise ValueError("Unable to load image")
    gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    attention = cv2.addWeighted(edges, 0.5, saturation,0.5, 0)
    attention = cv2.GaussianBlur(attention,(0, 0), 15)
    attention = cv2.normalize(attention, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    heatmap = cv2.applyColorMap(attention, cv2.COLORMAP_JET)
    result = cv2.addWeighted(image, 0.5, heatmap, 0.5, 0)
    filename = f"heatmap_{uuid.uuid4().hex}.jpg"
    output_path = os.path.join("static/uploads", filename)
    cv2.imwrite(output_path,result)
    height, width = gray.shape
    _, _, _, max_location = cv2.minMaxLoc(attention)
    x, y = max_location

    if x < width / 3:
        attention_area = "Left Area"
    elif x > (width * 2 / 3):
        attention_area = "Right Area"
    else:
        attention_area = "Center Area"

    return {
        "heatmap_url": "/" + output_path.replace("\\", "/"),
        "attention_area": attention_area,
        "hotspots": "High-detail and high-color regions",
        "dead_zones": "Low visual activity regions",
        "subject_focus": "Estimated from visual attention intensity"
    }