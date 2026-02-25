"""
STRIPPER — Elimina absolutamente TODA metadata de la imagen.
"""
import numpy as np
from PIL import Image

def strip_all_metadata(image: Image.Image) -> Image.Image:
    # Converting to RGB creates a new image object without any metadata (EXIF/IPTC/XMP)
    # This is much faster and uses less memory than converting to a numpy array.
    clean = Image.new("RGB", image.size)
    clean.paste(image)
    return clean
