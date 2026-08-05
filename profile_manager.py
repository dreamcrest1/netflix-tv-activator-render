import os
import json

# Check Render persistent disk path (/var/data) if available, else local ./data directory
DATA_DIR = "/var/data" if os.path.exists("/var/data") else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")

def _ensure_storage():
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception:
            pass
    if not os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)
        except Exception:
            pass

def load_profiles():
    _ensure_storage()
    try:
        if os.path.exists(PROFILES_FILE):
            with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_profiles(data):
    _ensure_storage()
    try:
        with open(PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving profiles: {e}")

def get_all_profiles():
    data = load_profiles()
    result = []
    for email, meta in data.items():
        has_cookies = bool(meta.get("cookies") and len(meta.get("cookies", [])) > 0)
        result.append({
            "email": email,
            "has_cookies": has_cookies,
            "cookie_count": len(meta.get("cookies", [])) if meta.get("cookies") else 0,
            "updated_at": meta.get("updated_at", "N/A")
        })
    return sorted(result, key=lambda x: x["email"])

def add_or_update_profile(email: str, cookies_raw=None):
    email = email.strip().lower()
    if not email:
        raise ValueError("Email address cannot be empty.")

    data = load_profiles()
    if email not in data:
        data[email] = {"cookies": [], "updated_at": None}

    if cookies_raw is not None:
        parsed_cookies = parse_cookies(cookies_raw)
        data[email]["cookies"] = parsed_cookies
        import time
        data[email]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    save_profiles(data)
    return True

def delete_profile(email: str):
    email = email.strip().lower()
    data = load_profiles()
    if email in data:
        del data[email]
        save_profiles(data)
        return True
    return False

def get_profile_cookies(email: str):
    email = email.strip().lower()
    data = load_profiles()
    if email in data:
        return data[email].get("cookies", [])
    return []

def parse_cookies(raw_input):
    if isinstance(raw_input, list):
        return raw_input
    if isinstance(raw_input, dict):
        return [raw_input]
    
    if isinstance(raw_input, str):
        raw_input = raw_input.strip()
        try:
            val = json.loads(raw_input)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                return [val]
        except Exception:
            pass

        cookies_list = []
        for line in raw_input.split(";"):
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                cookies_list.append({
                    "name": k.strip(),
                    "value": v.strip(),
                    "domain": ".netflix.com",
                    "path": "/"
                })
        return cookies_list

    return []