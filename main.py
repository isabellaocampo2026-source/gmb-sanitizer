"""
GMB Photo Sanitizer — API principal.
"""
import os, random, zipfile, traceback, logging, unicodedata, re
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gmb-sanitizer")
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.requests import Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image
from data.colombia import CITIES, DEVICE_PROFILES
from modules.geocoder import add_jitter, geocode_address, geocode_city
from modules.injector import build_exif, inject_exif
from modules.stripper import strip_all_metadata
from modules.uniquifier import uniquify_image

def _slugify(text: str) -> str:
    """Convert text to URL/filename-friendly slug."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = text.strip('-')
    return text or 'foto'

app = FastAPI(title="GMB Photo Sanitizer", version="1.0.0")

from starlette.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-GMB-Processed", "X-GMB-Total", "X-GMB-Errors", "Content-Disposition"],
)

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request: Request):
    cities = sorted(CITIES.keys())
    devices = [{"id": i, "label": f"{d['make']} {d['model_name']}"} for i, d in enumerate(DEVICE_PROFILES)]
    return templates.TemplateResponse("index.html", {"request": request, "cities": cities, "devices": devices})

@app.get("/api/cities")
async def api_cities():
    return JSONResponse({name: {"department": d["department"], "lat": d["lat"], "lon": d["lon"], "altitude": d["altitude"]} for name, d in sorted(CITIES.items())})

@app.post("/api/geocode")
async def api_geocode(address: str = Form(""), city: str = Form("")):
    if address:
        result = geocode_address(address, city)
    elif city:
        result = geocode_city(city)
    else:
        raise HTTPException(400, "Envía dirección o ciudad.")
    if not result:
        raise HTTPException(404, "No se encontró la ubicación.")
    return JSONResponse(result)

@app.post("/api/sanitize")
async def api_sanitize(
    files: list[UploadFile] = File(...),
    city: str = Form(""),
    address: str = Form(""),
    manual_lat: Optional[str] = Form(""),
    manual_lon: Optional[str] = Form(""),
    manual_alt: Optional[str] = Form(""),
    postal_code: str = Form(""),
    device_id: str = Form("random"),
    intensity: str = Form("medium"),
    jitter_radius: str = Form("30"),
    date_from: str = Form(""),
    date_to: str = Form(""),
    random_device_per_photo: str = Form("true"),
    keyword: str = Form(""),
):
    try:
        m_lat = float(manual_lat) if manual_lat else None
        m_lon = float(manual_lon) if manual_lon else None
        m_alt = float(manual_alt) if manual_alt else None
    except ValueError:
        m_lat = m_lon = m_alt = None

    if m_lat is not None and m_lon is not None:
        location = {"lat": m_lat, "lon": m_lon, "altitude": m_alt or 100, "postal_code": postal_code or "110111"}
    elif address:
        location = geocode_address(address, city)
        if not location:
            raise HTTPException(400, "No se pudo geocodificar la dirección.")
    elif city:
        location = geocode_city(city)
        if not location:
            raise HTTPException(400, f"Ciudad '{city}' no encontrada.")
    else:
        raise HTTPException(400, "Envía al menos una ciudad o coordenadas.")

    try:
        dt_from = datetime.strptime(date_from, "%Y-%m-%d") if date_from else datetime.now() - timedelta(days=30)
    except ValueError:
        dt_from = datetime.now() - timedelta(days=30)
    try:
        dt_to = datetime.strptime(date_to, "%Y-%m-%d") if date_to else datetime.now()
    except ValueError:
        dt_to = datetime.now()
    if dt_to < dt_from:
        dt_from, dt_to = dt_to, dt_from

    try:
        fixed_device_id = int(device_id)
        fixed_device = DEVICE_PROFILES[fixed_device_id] if 0 <= fixed_device_id < len(DEVICE_PROFILES) else None
    except (ValueError, IndexError):
        fixed_device = None
    use_random = random_device_per_photo == "true"

    try:
        jitter_r = float(jitter_radius)
    except ValueError:
        jitter_r = 30.0

    zip_buffer = BytesIO()
    processed = 0
    errors_list = []

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, file in enumerate(files):
            try:
                logger.info(f"[{idx+1}/{len(files)}] Processing: {file.filename} (content_type={file.content_type})")
                contents = await file.read()
                logger.info(f"  Read {len(contents)} bytes")
                if len(contents) == 0:
                    raise ValueError("Archivo vacío (0 bytes)")

                img = Image.open(BytesIO(contents))
                logger.info(f"  Opened: mode={img.mode}, size={img.size}")
                if img.mode != "RGB":
                    img = img.convert("RGB")

                clean = strip_all_metadata(img)
                logger.info(f"  Stripped metadata")

                unique, quality_range = uniquify_image(clean, intensity)
                quality = random.randint(*quality_range)
                logger.info(f"  Uniquified: size={unique.size}, quality={quality}")

                buf = BytesIO()
                unique.save(buf, "JPEG", quality=quality, optimize=True)
                jpeg_bytes = buf.getvalue()
                logger.info(f"  Saved JPEG: {len(jpeg_bytes)} bytes")

                total_sec = max(1, int((dt_to - dt_from).total_seconds()))
                ts = dt_from + timedelta(seconds=random.randint(0, total_sec))
                ts = ts.replace(hour=random.randint(7, 19), minute=random.randint(0, 59), second=random.randint(0, 59))
                j_lat, j_lon = add_jitter(location["lat"], location["lon"], jitter_r)
                device = None if use_random or not fixed_device else fixed_device

                exif = build_exif(lat=j_lat, lon=j_lon, altitude=location.get("altitude", 100), timestamp=ts, device_profile=device, image_width=unique.size[0], image_height=unique.size[1], keyword=keyword.strip(), city_name=city)
                logger.info(f"  Built EXIF")

                final = inject_exif(jpeg_bytes, exif)
                logger.info(f"  Injected EXIF: {len(final)} bytes")

                # SEO-friendly filename: keyword-city-N.jpg
                if keyword.strip():
                    slug = _slugify(keyword.strip())
                    city_slug = _slugify(city) if city else ""
                    if city_slug:
                        fname = f"{slug}-{city_slug}-{idx + 1}.jpg"
                    else:
                        fname = f"{slug}-{idx + 1}.jpg"
                else:
                    original = os.path.splitext(file.filename or f"photo_{idx}")[0]
                    fname = f"{original}_gmb.jpg"

                zf.writestr(fname, final)
                processed += 1
                logger.info(f"  SUCCESS -> {fname}")
            except Exception as e:
                err_msg = f"{file.filename}: {str(e)}"
                logger.error(f"FAILED processing {file.filename}:\n{traceback.format_exc()}")
                errors_list.append(err_msg)

        report = f"Procesadas: {processed}/{len(files)}\n"
        if errors_list:
            report += "\nErrores:\n" + "\n".join(errors_list)
        zf.writestr("_reporte.txt", report)

    zip_buffer.seek(0)
    ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_header = f"{processed}/{len(files)} OK"
    if errors_list:
        report_header += f" | Errors: {'; '.join(errors_list[:3])}"
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="gmb_sanitized_{ts_label}.zip"',
        "X-GMB-Processed": str(processed),
        "X-GMB-Total": str(len(files)),
        "X-GMB-Errors": "; ".join(errors_list[:3]) if errors_list else "",
    })

@app.post("/api/verify")
async def api_verify(file: UploadFile = File(...)):
    import piexif
    contents = await file.read()
    try:
        exif_dict = piexif.load(contents)
    except Exception:
        return JSONResponse({"error": "No se pudo leer EXIF"})
    result = {}
    for ifd_name in ("0th", "Exif", "GPS", "1st"):
        ifd = exif_dict.get(ifd_name, {})
        if isinstance(ifd, dict):
            readable = {}
            for tag, val in ifd.items():
                try:
                    tag_name = piexif.TAGS.get(ifd_name, {}).get(tag, {}).get("name", str(tag))
                except Exception:
                    tag_name = str(tag)
                if isinstance(val, bytes):
                    try:
                        val = val.decode("utf-8", errors="replace")
                    except Exception:
                        val = str(val)
                elif isinstance(val, tuple):
                    val = str(val)
                readable[tag_name] = val
            if readable:
                result[ifd_name] = readable
    return JSONResponse(result)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
