"""
GEOCODER — Convierte direcciones/ciudades colombianas a coordenadas GPS.
"""
import random
import requests
from data.colombia import CITIES

def geocode_city(city_name):
    if city_name in CITIES:
        c = CITIES[city_name]
        return {"lat": c["lat"], "lon": c["lon"], "altitude": c["altitude"], "department": c["department"], "postal_code": random.choice(c["postal_codes"]), "source": "local_db"}
    for name, c in CITIES.items():
        if name.lower() == city_name.strip().lower():
            return {"lat": c["lat"], "lon": c["lon"], "altitude": c["altitude"], "department": c["department"], "postal_code": random.choice(c["postal_codes"]), "source": "local_db"}
    for name, c in CITIES.items():
        if city_name.strip().lower() in name.lower():
            return {"lat": c["lat"], "lon": c["lon"], "altitude": c["altitude"], "department": c["department"], "postal_code": random.choice(c["postal_codes"]), "source": "local_db"}
    return None

def geocode_address(address, city=""):
    try:
        query = address
        if city:
            query += f", {city}"
        query += ", Colombia"
        resp = requests.get("https://nominatim.openstreetmap.org/search", params={"q": query, "format": "json", "limit": 1, "countrycodes": "co"}, headers={"User-Agent": "GMBSanitizer/1.0"}, timeout=10)
        if resp.status_code == 200 and resp.json():
            r = resp.json()[0]
            lat, lon = float(r["lat"]), float(r["lon"])
            city_data = geocode_city(city) if city else None
            return {"lat": lat, "lon": lon, "altitude": city_data["altitude"] if city_data else 100, "department": city_data["department"] if city_data else "", "postal_code": city_data["postal_code"] if city_data else "110111", "source": "nominatim"}
    except Exception:
        pass
    if city:
        return geocode_city(city)
    return None

def add_jitter(lat, lon, radius_m=30.0):
    offset = radius_m / 111_000
    return (lat + random.uniform(-offset, offset), lon + random.uniform(-offset, offset))
