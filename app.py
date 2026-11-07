from bson import ObjectId
from datetime import datetime
from flask import (Flask, render_template, request, jsonify, session, redirect, url_for, send_file)
from werkzeug.security import (generate_password_hash, check_password_hash)
from utils.database import (users_collection, thumbnails_collection)
from werkzeug.utils import secure_filename
from utils.analyzer import (analyze_image, detect_text, predict_ctr, analyze_heatmap)
from utils.ai_service import (analyze_thumbnail, generate_thumbnail_from_prompt)
from utils.builder import build_thumbnail
import os
import uuid

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return ("." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS)

@app.route("/")
def index():
    return render_template("index.html")

# THUMBNAIL ANALYSIS - GEMINI

@app.route("/api/analyze", methods=["POST"])
def analyze():
    if "thumbnail" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    
    file = request.files["thumbnail"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file format"}), 400

    extension = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"
    filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
    file.save(filepath)

    try:
        image_analysis = analyze_image(filepath)
        text_analysis = detect_text(filepath)
        ctr_prediction = predict_ctr(image_analysis, text_analysis)
        heatmap_analysis = analyze_heatmap(filepath)

# AI analysis should not stop the complete analysis
        try:
            ai_result = analyze_thumbnail(filepath)
            gemini_text = ai_result.get("detected_text", "").strip()
            if gemini_text and gemini_text != "No text detected.":
                text_analysis = {
                    "success": True,
                    "text_detected": True,
                    "extracted_text": gemini_text,
                    "word_count": len(gemini_text.split()),
                    "confidence": None
                }
            ai_analysis = ai_result.get("ai_analysis", "")
            ai_ctr = ai_result.get("ctr_prediction")

        except Exception as e:
            print("AI analysis unavailable:", str(e))
            ai_analysis = "AI recommendations are temporarily unavailable. Please try again later."
            ai_ctr = None

        return jsonify({
            "success": True,
            "image_analysis": image_analysis,
            "text_analysis": text_analysis,
            "heatmap_analysis": heatmap_analysis,
            "ai_analysis": ai_analysis,
            "ctr_prediction": ai_ctr or ctr_prediction
        })

    except Exception as e:
    import traceback
    traceback.print_exc()
    return jsonify({
        "success": False,
        "error": str(e)
    }), 500

# MANUAL THUMBNAIL BUILDER - PILLOW
@app.route("/api/build", methods=["POST"])
def build():
    if "thumbnail" not in request.files:
        return jsonify({"error": "No thumbnail uploaded"}), 400

    file = request.files["thumbnail"]

    if file.filename == "":
        return jsonify({"error": "No thumbnail selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid thumbnail format"}), 400

    # Thumbnail text settings
    text = request.form.get("text","").strip()

    try:
        font_size = int(request.form.get("font_size",60))
    except ValueError:
        return jsonify({"error": "Invalid font size"}), 400

    text_color = request.form.get("text_color", "#FFFFFF")
    position = request.form.get("position", "center")

    # Save thumbnail
    extension = file.filename.rsplit(".",    1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"
    filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
    file.save(filepath)

    # Save user's image
    person_path = None
    person_file = request.files.get("person")

    if person_file and person_file.filename:
        if not allowed_file(person_file.filename):
            return jsonify({"error": "Invalid personal image format"}), 400

        person_extension = person_file.filename.rsplit(".",    1)[1].lower()
        person_filename = (f"person_{uuid.uuid4().hex}."f"{person_extension}")
        person_path = os.path.join(UPLOAD_FOLDER,secure_filename(person_filename))
        person_file.save(person_path)

    # Build thumbnail
    try:
        output_path = build_thumbnail(filepath, text, font_size, text_color, position, person_path)
        from datetime import datetime
        output_filename = os.path.basename(output_path)
        thumbnail_document = {
            "user_id": session.get("user_id"),
            "filename": output_filename,
            "prompt": request.form.get("prompt", ""),
            "headline": text,
            "aspect_ratio": request.form.get("aspect_ratio","16:9"),
            "created_at": datetime.utcnow(),
            "downloaded_at": None
        }
        result = thumbnails_collection.insert_one(thumbnail_document)
        output_url = "/" + output_path.replace("\\","/")
        return jsonify({"success": True, "image_url": output_url, "thumbnail_id": str(result.inserted_id)})

    except Exception as e: 
        print("Builder error:", str(e))
        return jsonify({"error": str(e)}), 500

# AI THUMBNAIL GENERATION - CLOUDFLARE FLUX
@app.route("/api/generate-thumbnail", methods=["POST"])
def generate_thumbnail():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    prompt = data.get("prompt","").strip()
    aspect_ratio = data.get("aspect_ratio","16:9")
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    try:
        print("Starting Cloudflare AI thumbnail generation...")
        result = generate_thumbnail_from_prompt(prompt,aspect_ratio)
        print("Cloudflare generation function completed.")
        if not result.get("success"):
            return jsonify({"error": result.get("error", "Generation failed")}), 500
        return jsonify(result)

    except Exception as e:
        print("Cloudflare generation error:",str(e))
        return jsonify({"error": str(e)}), 500

# AUTHENTICATION / COLLECTION PAGES
@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "GET":
        return render_template("signin.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("signin.html",error="Email and password are required.")
    user = users_collection.find_one({"email": email})

    if not user or not check_password_hash(user["password"],password):
        return render_template("signin.html",error="Invalid email or password.")
    session["user_id"] = str(user["_id"])
    session["user_name"] = user["name"]
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template("signup.html",error="All fields are required.")
    existing_user = users_collection.find_one({"email": email})

    if existing_user:
        return render_template("signup.html", error="Email already registered.")

    user = {"name": name, "email": email, "password": generate_password_hash(password)}
    result = users_collection.insert_one(user)
    session["user_id"] = str(result.inserted_id)
    session["user_name"] = name
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/collection")
def collection():
    if "user_id" not in session:
        return redirect(url_for("signin"))
    thumbnails = list(thumbnails_collection.find({"user_id": session["user_id"]}).sort("created_at",    -1))
    return render_template("collection.html", thumbnails=thumbnails, user_name=session.get("user_name"))

@app.route("/download/<thumbnail_id>")
def download_thumbnail(thumbnail_id):
    if "user_id" not in session:
            return redirect(url_for("signin"))
    thumbnail = thumbnails_collection.find_one({"_id": ObjectId(thumbnail_id), "user_id": session["user_id"]})

    if not thumbnail:
        return "Thumbnail not found", 404
    filepath = os.path.join(UPLOAD_FOLDER, thumbnail["filename"])

    if not os.path.exists(filepath):
        return "File not found", 404
    thumbnails_collection.update_one({"_id": ObjectId(thumbnail_id),"user_id": session["user_id"]},{"$set": {"downloaded_at": datetime.utcnow()}})
    return send_file(filepath, as_attachment=True, download_name="thumbai-thumbnail.jpg")

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))