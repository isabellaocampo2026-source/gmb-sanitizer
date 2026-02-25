"""
UNIQUIFIER — Transforma la imagen a nivel de píxel para hacerla irrastreable.
"""
import random
import numpy as np
from PIL import Image, ImageEnhance

_SETTINGS = {
    "low": {"noise_sigma": 1.5, "color_shift": 1, "brightness": (0.99, 1.01), "contrast": (0.99, 1.01), "sharpness": (0.97, 1.03), "crop_px": 3, "rotation": 0.3, "jpeg_quality": (92, 96)},
    "medium": {"noise_sigma": 2.5, "color_shift": 2, "brightness": (0.97, 1.03), "contrast": (0.97, 1.03), "sharpness": (0.95, 1.05), "crop_px": 6, "rotation": 0.5, "jpeg_quality": (88, 94)},
    "high": {"noise_sigma": 4.0, "color_shift": 4, "brightness": (0.95, 1.05), "contrast": (0.95, 1.05), "sharpness": (0.90, 1.10), "crop_px": 12, "rotation": 1.0, "jpeg_quality": (84, 91)},
}

def uniquify_image(image, intensity="medium"):
    s = _SETTINGS.get(intensity, _SETTINGS["medium"])
    img = image.copy()
    angle = random.uniform(-s["rotation"], s["rotation"])
    img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255))
    w, h = img.size
    cl, ct, cr, cb = random.randint(0, s["crop_px"]), random.randint(0, s["crop_px"]), random.randint(0, s["crop_px"]), random.randint(0, s["crop_px"])
    if w - cl - cr > 200 and h - ct - cb > 200:
        img = img.crop((cl, ct, w - cr, h - cb))
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, s["noise_sigma"], arr.shape).astype(np.float32)
    arr += noise
    for c in range(min(3, arr.shape[2])):
        arr[:, :, c] += random.uniform(-s["color_shift"], s["color_shift"])
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    img = ImageEnhance.Brightness(img).enhance(random.uniform(*s["brightness"]))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(*s["contrast"]))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(*s["sharpness"]))
    return img, s["jpeg_quality"]
