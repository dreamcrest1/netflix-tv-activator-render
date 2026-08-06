import os
import json
import base64
import time
from datetime import datetime

DATA_DIR = "/var/data" if os.path.exists("/var/data") else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
APP_DATA_FILE = os.path.join(DATA_DIR, "app_data.json")

DEFAULT_SETTINGS = {
    "max_monthly_activations": 3,
    "max_total_activations": 0,
    "whatsapp_number": "+91 6357998730",
    "whatsapp_link": "https://wa.me/916357998730?text=Hi%2C%20I%20want%20to%20buy%20Netflix%204K%20UHD%20subscription",
    "custom_sheet_url": ""
}

def _ensure_storage():
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception:
            pass
            
    if not os.path.exists(APP_DATA_FILE):
        data = {
            "profiles": {},
            "settings": DEFAULT_SETTINGS,
            "logs": []
        }
        env_data = os.environ.get("PROFILES_JSON_DATA") or os.environ.get("APP_STATE_B64", "")
        if env_data:
            try:
                try:
                    decoded = base64.b64decode(env_data).decode("utf-8")
                    data = json.loads(decoded)
                except Exception:
                    data = json.loads(env_data)
            except Exception:
                pass
        try:
            with open(APP_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

def load_app_data():
    _ensure_storage()
    try:
        if os.path.exists(APP_DATA_FILE):
            with open(APP_DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    d = json.loads(content)
                    if "settings" not in d:
                        d["settings"] = DEFAULT_SETTINGS
                    if "logs" not in d:
                        d["logs"] = []
                    if "profiles" not in d:
                        d["profiles"] = {}
                    return d
    except Exception:
        pass

    env_data = os.environ.get("PROFILES_JSON_DATA") or os.environ.get("APP_STATE_B64", "")
    if env_data:
        try:
            try:
                decoded = base64.b64decode(env_data).decode("utf-8")
                d = json.loads(decoded)
            except Exception:
                d = json.loads(env_data)
            if "settings" not in d:
                d["settings"] = DEFAULT_SETTINGS
            if "logs" not in d:
                d["logs"] = []
            if "profiles" not in d:
                d["profiles"] = {}
            return d
        except Exception:
            pass

    return {"profiles": {}, "settings": DEFAULT_SETTINGS, "logs": []}

def save_app_data(data):
    _ensure_storage()
    try:
        with open(APP_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving app data: {e}")

def get_all_profiles():
    data = load_app_data()
    profiles = data.get("profiles", {})
    result = []
    for email, meta in profiles.items():
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

    data = load_app_data()
    if "profiles" not in data:
        data["profiles"] = {}

    if email not in data["profiles"]:
        data["profiles"][email] = {"cookies": [], "updated_at": None}

    if cookies_raw is not None:
        from profile_manager import parse_cookies
        parsed = parse_cookies(cookies_raw)
        data["profiles"][email]["cookies"] = parsed
        data["profiles"][email]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    save_app_data(data)
    return True

def delete_profile(email: str):
    email = email.strip().lower()
    data = load_app_data()
    if "profiles" in data and email in data["profiles"]:
        del data["profiles"][email]
        save_app_data(data)
        return True
    return False

def get_profile_cookies(email: str):
    email = email.strip().lower()
    data = load_app_data()
    profiles = data.get("profiles", {})
    if email in profiles:
        return profiles[email].get("cookies", [])
    return []

def get_settings():
    data = load_app_data()
    settings = DEFAULT_SETTINGS.copy()
    settings.update(data.get("settings", {}))
    return settings

def update_settings(new_settings: dict):
    data = load_app_data()
    if "settings" not in data:
        data["settings"] = DEFAULT_SETTINGS.copy()
    data["settings"].update(new_settings)
    save_app_data(data)
    return data["settings"]

def log_activation(mobile: str, email: str, code: str, success: bool, message: str):
    data = load_app_data()
    if "logs" not in data:
        data["logs"] = []

    entry = {
        "id": len(data["logs"]) + 1,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "month_key": time.strftime("%Y-%m"),
        "mobile": str(mobile).strip(),
        "email": str(email).strip().lower(),
        "code": str(code).strip(),
        "success": bool(success),
        "message": str(message)
    }
    data["logs"].insert(0, entry)
    data["logs"] = data["logs"][:1000]
    save_app_data(data)
    return entry

def check_activation_limit(mobile: str):
    settings = get_settings()
    max_monthly = int(settings.get("max_monthly_activations", 3))
    max_total = int(settings.get("max_total_activations", 0))

    if max_monthly == 0 and max_total == 0:
        return True, "Allowed"

    data = load_app_data()
    logs = data.get("logs", [])
    clean_mobile = str(mobile).strip()
    current_month = time.strftime("%Y-%m")

    monthly_count = sum(1 for l in logs if l.get("mobile") == clean_mobile and l.get("month_key") == current_month and l.get("success"))
    total_count = sum(1 for l in logs if l.get("mobile") == clean_mobile and l.get("success"))

    if max_monthly > 0 and monthly_count >= max_monthly:
        return False, f"Monthly activation limit reached ({monthly_count}/{max_monthly} used this month). Please contact support to renew."

    if max_total > 0 and total_count >= max_total:
        return False, f"Total activation limit reached ({total_count}/{max_total} used). Please contact support."

    return True, "Allowed"

def get_activation_stats():
    data = load_app_data()
    logs = data.get("logs", [])
    settings = get_settings()

    total_activations = len(logs)
    successful_activations = sum(1 for l in logs if l.get("success"))
    
    user_stats = {}
    current_month = time.strftime("%Y-%m")

    for l in logs:
        m = l.get("mobile", "Unknown")
        if m not in user_stats:
            user_stats[m] = {"mobile": m, "total": 0, "monthly": 0, "last_active": l.get("timestamp")}
        user_stats[m]["total"] += 1
        if l.get("month_key") == current_month:
            user_stats[m]["monthly"] += 1

    return {
        "total_logs": total_activations,
        "successful_logs": successful_activations,
        "unique_users_count": len(user_stats),
        "settings": settings,
        "user_stats": sorted(list(user_stats.values()), key=lambda x: x["total"], reverse=True),
        "recent_logs": logs[:100]
    }

def export_full_state_b64():
    data = load_app_data()
    json_str = json.dumps(data)
    return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
