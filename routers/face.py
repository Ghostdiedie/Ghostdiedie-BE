import base64
import io
import logging
import uuid

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

router = APIRouter(tags=["Face"])
logger = logging.getLogger("ghostdiedie.face")

# In-memory store: face_id → face_url (base64 data URL)
faces: dict[str, str] = {}

# Haar cascade for frontal face detection (bundled with OpenCV)
_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_face_cascade = cv2.CascadeClassifier(_CASCADE_PATH)

OUTPUT_SIZE = 256  # px — square output for the face texture


def _detect_face(gray: np.ndarray):
    """Return (x, y, w, h) of the largest detected face, or None."""
    faces = _face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(60, 60),
    )
    if len(faces) == 0:
        return None
    # Pick largest face
    return max(faces, key=lambda f: f[2] * f[3])


def _crop_and_mask(img_bgr: np.ndarray, face_rect) -> Image.Image:
    """Crop the face with 30 % padding, resize to OUTPUT_SIZE, apply circular mask."""
    x, y, w, h = face_rect
    h_img, w_img = img_bgr.shape[:2]

    # Add 30 % padding around detected face box for natural framing
    pad = int(max(w, h) * 0.35)
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(w_img, x + w + pad)
    y2 = min(h_img, y + h + pad)

    cropped_bgr = img_bgr[y1:y2, x1:x2]
    cropped_rgb = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2RGB)

    pil = Image.fromarray(cropped_rgb).resize(
        (OUTPUT_SIZE, OUTPUT_SIZE), Image.LANCZOS
    )
    pil = pil.convert("RGBA")

    # Circular mask
    mask = Image.new("L", (OUTPUT_SIZE, OUTPUT_SIZE), 0)
    import PIL.ImageDraw as ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, OUTPUT_SIZE, OUTPUT_SIZE), fill=255)

    pil.putalpha(mask)
    return pil


@router.post("/api/face")
async def process_face(file: UploadFile = File(...)):
    """
    Accept an image upload, detect the largest face, crop it with a circular
    mask, and return the result as a base64-encoded PNG data URL.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    raw = await file.read()
    np_arr = np.frombuffer(raw, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise HTTPException(status_code=400, detail="Could not decode image")

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    face_rect = _detect_face(gray)

    if face_rect is None:
        # No face found — fall back to a center crop of the whole image
        h, w = img_bgr.shape[:2]
        side = min(h, w)
        x1 = (w - side) // 2
        y1 = (h - side) // 2
        face_rect = (x1, y1, side, side)

    pil_face = _crop_and_mask(img_bgr, face_rect)

    buf = io.BytesIO()
    pil_face.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    data_url = f"data:image/png;base64,{b64}"

    face_id = uuid.uuid4().hex[:12]
    faces[face_id] = data_url
    logger.info(
        "processed face face_id=%s filename=%s content_type=%s size_bytes=%s detected=%s",
        face_id,
        file.filename,
        file.content_type,
        len(raw),
        face_rect is not None,
    )

    return JSONResponse({"face_id": face_id, "face_url": data_url})
