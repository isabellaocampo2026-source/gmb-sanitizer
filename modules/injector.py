"""
INJECTOR — Construye e inyecta EXIF realista en JPEGs.
"""
import random
import tempfile
import os
from datetime import datetime, timedelta
from io import BytesIO
import piexif
from PIL import Image
from data.colombia import DEVICE_PROFILES

def _decimal_to_dms(decimal_degrees: float):
    d = abs(decimal_degrees)
    degrees = int(d)
    m_float = (d - degrees) * 60
    minutes = int(m_float)
    s_float = (m_float - minutes) * 60
    return ((degrees, 1), (minutes, 1), (int(s_float * 10000), 10000))

def build_exif(lat, lon, altitude, timestamp=None, device_profile=None, image_width=None, image_height=None, keyword="", city_name=""):
    if device_profile is None:
        device_profile = random.choice(DEVICE_PROFILES)
    if timestamp is None:
        now = datetime.now()
        offset = random.randint(0, 30 * 24 * 3600)
        timestamp = now - timedelta(seconds=offset)
        timestamp = timestamp.replace(hour=random.randint(7, 19), minute=random.randint(0, 59), second=random.randint(0, 59))

    dt_str = timestamp.strftime("%Y:%m:%d %H:%M:%S")
    subsec = str(random.randint(100, 999))
    lat_ref = b"N" if lat >= 0 else b"S"
    lon_ref = b"E" if lon >= 0 else b"W"
    lat_dms = _decimal_to_dms(lat)
    lon_dms = _decimal_to_dms(lon)
    alt_ref = 0 if altitude >= 0 else 1
    alt_val = (int(abs(altitude) * 100), 100)

    iso_lo, iso_hi = device_profile["iso_range"]
    iso_options = [v for v in [50,64,80,100,125,160,200,250,320,400,500,640,800] if iso_lo <= v <= iso_hi]
    iso = random.choice(iso_options) if iso_options else 200
    exp_options = [v for v in [60,100,120,125,160,200,250,320,500,1000,2000,4000] if v <= device_profile["exposure_range"][1]]
    exp_denom = random.choice(exp_options) if exp_options else 125
    px = image_width or device_profile["pixel_x"]
    py = image_height or device_profile["pixel_y"]

    # Build SEO description from keyword + city
    seo_desc = ""
    if keyword and city_name:
        seo_desc = f"{keyword} en {city_name}"
    elif keyword:
        seo_desc = keyword
    elif city_name:
        seo_desc = city_name

    zeroth_ifd = {
        piexif.ImageIFD.Make: device_profile["make"].encode(),
        piexif.ImageIFD.Model: device_profile["model"].encode(),
        piexif.ImageIFD.Software: device_profile["software"].encode(),
        piexif.ImageIFD.DateTime: dt_str.encode(),
        piexif.ImageIFD.Orientation: 1,
        piexif.ImageIFD.XResolution: (72, 1),
        piexif.ImageIFD.YResolution: (72, 1),
        piexif.ImageIFD.ResolutionUnit: 2,
        piexif.ImageIFD.YCbCrPositioning: 1,
    }

    # Inject SEO keyword into EXIF description fields
    if seo_desc:
        zeroth_ifd[piexif.ImageIFD.ImageDescription] = seo_desc.encode("utf-8")
        zeroth_ifd[piexif.ImageIFD.XPTitle] = seo_desc.encode("utf-16le")
        zeroth_ifd[piexif.ImageIFD.XPKeywords] = keyword.encode("utf-16le") if keyword else seo_desc.encode("utf-16le")
        zeroth_ifd[piexif.ImageIFD.XPSubject] = seo_desc.encode("utf-16le")

    exif_dict = {
        "0th": zeroth_ifd,
        "Exif": {
            piexif.ExifIFD.ExposureTime: (1, exp_denom),
            piexif.ExifIFD.FNumber: device_profile["f_number"],
            piexif.ExifIFD.ExposureProgram: 2,
            piexif.ExifIFD.ISOSpeedRatings: iso,
            piexif.ExifIFD.ExifVersion: b"0232",
            piexif.ExifIFD.DateTimeOriginal: dt_str.encode(),
            piexif.ExifIFD.DateTimeDigitized: dt_str.encode(),
            piexif.ExifIFD.SubSecTimeOriginal: subsec.encode(),
            piexif.ExifIFD.SubSecTimeDigitized: subsec.encode(),
            piexif.ExifIFD.ComponentsConfiguration: b"\x01\x02\x03\x00",
            piexif.ExifIFD.FocalLength: device_profile["focal_length"],
            piexif.ExifIFD.ColorSpace: 1,
            piexif.ExifIFD.PixelXDimension: px,
            piexif.ExifIFD.PixelYDimension: py,
            piexif.ExifIFD.FlashpixVersion: b"0100",
            piexif.ExifIFD.SceneCaptureType: 0,
            piexif.ExifIFD.Flash: 0,
            piexif.ExifIFD.WhiteBalance: 0,
            piexif.ExifIFD.MeteringMode: 2,
            piexif.ExifIFD.ExposureMode: 0,
            piexif.ExifIFD.SceneType: b"\x01",
            piexif.ExifIFD.SensingMethod: 2,
        },
        "GPS": {
            piexif.GPSIFD.GPSVersionID: (2, 3, 0, 0),
            piexif.GPSIFD.GPSLatitudeRef: lat_ref,
            piexif.GPSIFD.GPSLatitude: lat_dms,
            piexif.GPSIFD.GPSLongitudeRef: lon_ref,
            piexif.GPSIFD.GPSLongitude: lon_dms,
            piexif.GPSIFD.GPSAltitudeRef: alt_ref,
            piexif.GPSIFD.GPSAltitude: alt_val,
            piexif.GPSIFD.GPSTimeStamp: ((timestamp.hour, 1), (timestamp.minute, 1), (timestamp.second, 1)),
            piexif.GPSIFD.GPSDateStamp: timestamp.strftime("%Y:%m:%d").encode(),
            piexif.GPSIFD.GPSProcessingMethod: b"ASCII\x00\x00\x00GPS",
        },
        "1st": {},
    }
    return exif_dict

def inject_exif(jpeg_bytes, exif_dict):
    exif_bytes = piexif.dump(exif_dict)
    tmp_in = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    try:
        tmp_in.write(jpeg_bytes)
        tmp_in.close()
        piexif.insert(exif_bytes, tmp_in.name, tmp_in.name)
        with open(tmp_in.name, 'rb') as f:
            result = f.read()
        return result
    finally:
        try:
            os.unlink(tmp_in.name)
        except OSError:
            pass
