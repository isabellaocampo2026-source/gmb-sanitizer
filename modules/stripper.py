"""
STRIPPER — Elimina absolutamente TODA metadata de la imagen.
"""
import numpy as np
from PIL import Image

def strip_all_metadata(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    pixel_array = np.array(rgb)
    clean = Image.fromarray(pixel_array)
    return clean
