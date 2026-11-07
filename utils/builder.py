from PIL import Image, ImageDraw, ImageFont
import os
import uuid
OUTPUT_FOLDER = "static/uploads"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def get_font(font_size):
    font_paths = ["C:/Windows/Fonts/arialbd.ttf","C:/Windows/Fonts/calibrib.ttf","C:/Windows/Fonts/impact.ttf"]

    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, font_size)

    return ImageFont.load_default()

def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = (word if not current_line else current_line + " " + word)

        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)

def get_fitted_text(draw, text, requested_size, max_width):
    font_size = requested_size

    while font_size >= 35:
        font = get_font(font_size)
        wrapped_text = wrap_text(draw,text,font,max_width)
        bbox = draw.multiline_textbbox((0, 0),wrapped_text,font=font,spacing=8,stroke_width=3)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_width:
            return font, wrapped_text, bbox
        font_size -= 5

    font = get_font(35)
    wrapped_text = wrap_text(draw,text,font,max_width)
    bbox = draw.multiline_textbbox((0, 0),wrapped_text,font=font,spacing=8,stroke_width=3)
    return font, wrapped_text, bbox

def build_thumbnail(image_path, text, font_size, text_color, position, person_image_path=None):

    # OPEN AI IMAGE
    image = Image.open(image_path).convert("RGB")
    target_width = 1280
    target_height = 720
    target_ratio = target_width / target_height
    image_ratio = image.width / image.height

    # CROP TO 16:9
    if image_ratio > target_ratio:
        new_width = int(image.height * target_ratio)
        left = (image.width - new_width) // 2
        image = image.crop((left,0,left + new_width,image.height))

    elif image_ratio < target_ratio:
        new_height = int(image.width / target_ratio)
        top = (image.height - new_height) // 2
        image = image.crop((0, top, image.width, top + new_height))

    image = image.resize((target_width, target_height),Image.LANCZOS)

    # ADD USER IMAGE - OPTIONAL
    person_width = 0
    person_height = 0

    if person_image_path and os.path.exists(person_image_path):
        person = Image.open(person_image_path).convert("RGBA")

        # Crop transparent/background area
        bbox = person.getbbox()

        if bbox:
            person = person.crop(bbox)

        # Make person larger
        person.thumbnail((600, 680))
        person_width = person.width
        person_height = person.height

        # Bottom-left placement
        person_x = 35
        person_y = (target_height - person.height - 20)
        image.paste(person,(person_x, person_y),person)

    # TEXT - OPTIONAL
    text = (text or "").strip()

    # Only add text if user entered a headline
    if text:
        draw = ImageDraw.Draw(image)
        margin = 45

        # Give text more space when no person exists
        if person_width:
            max_text_width = 650
        else:
            max_text_width = 950
        font, wrapped_text, bbox = get_fitted_text(draw, text, font_size, max_text_width)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # TEXT POSITION
        if position == "top":
            x = ( target_width - text_width) // 2
            y = 45

        elif position == "bottom":
            x = (target_width - text_width) // 2
            y = (target_height - text_height - 45)

        elif position == "center":
            x = (target_width - text_width) // 2
            y = (target_height - text_height) // 2

        elif position == "left":
            x = margin
            if person_height:
                available_top = 40
                available_bottom = (target_height - person_height - 35)
                available_height = (available_bottom - available_top)

                if text_height > available_height:
                    font, wrapped_text, bbox = get_fitted_text(draw, text, max(font_size - 10, 35), max_text_width)
                    text_width = (bbox[2] - bbox[0])
                    text_height = (bbox[3] - bbox[1])
                y = max(available_top, available_top + (available_height - text_height) // 2)

            else:
                y = (target_height - text_height) // 2

        else:
            x = margin
            y = margin

        # TEXT BACKGROUND
        padding_x = 18
        padding_y = 12

        box_left = max(10, x - padding_x)
        box_top = max(10, y - padding_y)
        box_right = min(target_width - 10, x + text_width + padding_x)
        box_bottom = min(target_height - 10, y + text_height + padding_y)
        overlay = Image.new("RGBA", image.size,(0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle((box_left, box_top, box_right, box_bottom), radius=14, fill=(0, 0, 0, 145))
        image = Image.alpha_composite(image.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(image)

        # TEXT SHADOW
        draw.multiline_text((x + 5, y + 5), wrapped_text, font=font, fill="black", spacing=8, stroke_width=4, stroke_fill="black")

        # MAIN TEXT
        draw.multiline_text((x, y), wrapped_text, font=font, fill=text_color, spacing=8, stroke_width=3, stroke_fill="black")

    # SAVE FINAL THUMBNAIL
    filename = f"built_{uuid.uuid4().hex}.jpg"

    output_path = os.path.join(OUTPUT_FOLDER,filename)
    image.convert("RGB").save(output_path,"JPEG",quality=95)

    return output_path