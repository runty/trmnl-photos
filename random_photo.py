import os
import random
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from io import BytesIO

import numpy as np
from PIL import Image, ImageEnhance
from rembg import new_session, remove

PHOTOS_DIR = "/photos"

session = new_session("u2netp")

PALETTES = {
    "7color": [
        (0, 0, 0),
        (255, 255, 255),
        (0, 128, 0),
        (0, 0, 255),
        (255, 0, 0),
        (255, 255, 0),
        (255, 128, 0),
    ],
    "spectra6": [
        (0, 0, 0),
        (255, 255, 255),
        (0, 128, 0),
        (0, 0, 255),
        (255, 0, 0),
        (255, 255, 0),
    ],
    "bw4": [
        (0, 0, 0),
        (85, 85, 85),
        (170, 170, 170),
        (255, 255, 255),
    ],
    "bw": [
        (0, 0, 0),
        (255, 255, 255),
    ],
}


def get_saliency_center(img):
    mask = remove(img, session=session, only_mask=True)
    mask_arr = np.array(mask)

    rows = np.any(mask_arr > 128, axis=1)
    cols = np.any(mask_arr > 128, axis=0)
    if not rows.any() or not cols.any():
        return img.size[0] // 2, img.size[1] // 2

    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    return (cmin + cmax) // 2, (rmin + rmax) // 2


def smart_crop(img, target_w, target_h):
    target_ratio = target_w / target_h
    img_w, img_h = img.size

    cx, cy = get_saliency_center(img)

    if img_w / img_h > target_ratio:
        crop_h = img_h
        crop_w = int(crop_h * target_ratio)
    else:
        crop_w = img_w
        crop_h = int(crop_w / target_ratio)

    x1 = max(0, min(cx - crop_w // 2, img_w - crop_w))
    y1 = max(0, min(cy - crop_h // 2, img_h - crop_h))

    return img.crop((x1, y1, x1 + crop_w, y1 + crop_h)).resize(
        (target_w, target_h), Image.Resampling.LANCZOS
    )


def apply_palette(img, palette_name):
    if palette_name not in PALETTES:
        return img

    colors = PALETTES[palette_name]
    palette_data = []
    for r, g, b in colors:
        palette_data.extend([r, g, b])
    palette_data.extend(palette_data[:3] * (256 - len(colors)))

    palette_img = Image.new("P", (1, 1))
    palette_img.putpalette(palette_data)

    return img.convert("RGB").quantize(
        colors=len(colors),
        palette=palette_img,
        dither=Image.Dither.FLOYDSTEINBERG,
    ).convert("RGB")


def enhance_for_eink(img):
    img = ImageEnhance.Contrast(img).enhance(1.3)
    img = ImageEnhance.Color(img).enhance(1.4)
    img = ImageEnhance.Sharpness(img).enhance(1.2)
    return img


class RandomPhotoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/random":
            self.send_error(404)
            return

        files = [
            f
            for f in os.listdir(PHOTOS_DIR)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
        ]
        if not files:
            self.send_error(404, "No photos found")
            return

        chosen = random.choice(files)
        filepath = os.path.join(PHOTOS_DIR, chosen)
        params = parse_qs(parsed.query)

        w = params.get("w", [None])[0]
        h = params.get("h", [None])[0]
        palette = params.get("palette", [None])[0]

        if w and h:
            img = Image.open(filepath).convert("RGB")
            print(f"Smart cropping {chosen} to {w}x{h}...")
            img = smart_crop(img, int(w), int(h))
            img = enhance_for_eink(img)

            if palette:
                print(f"Applying {palette} palette...")
                img = apply_palette(img, palette)

            buf = BytesIO()
            img.save(buf, format="PNG")
            data = buf.getvalue()
            mime = "image/png"
            print(f"Done: {chosen} ({len(data)} bytes)")
        else:
            with open(filepath, "rb") as f:
                data = f.read()
            mime = mimetypes.guess_type(chosen)[0] or "application/octet-stream"

        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Photo-Name", chosen)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


print("Loading U2-Net model...")
get_saliency_center(Image.new("RGB", (64, 64), (128, 128, 128)))
print("Model loaded. Starting server on :8099")
HTTPServer(("0.0.0.0", 8099), RandomPhotoHandler).serve_forever()
