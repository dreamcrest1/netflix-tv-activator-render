import os
import json
import base64
import time
import requests
from datetime import datetime

DATA_DIR = "/var/data" if os.path.exists("/var/data") else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
APP_DATA_FILE = os.path.join(DATA_DIR, "app_data.json")

UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip()
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()

DEFAULT_SETTINGS = {
    "max_monthly_activations": 3,
    "max_total_activations": 0,
    "whatsapp_number": "+91 6357998730",
    "whatsapp_link": "https://wa.me/916357998730?text=Hi%2C%20I%20want%20to%20buy%20Netflix%204K%20UHD%20subscription",
    "custom_sheet_url": ""
}

def load_from_upstash():
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    try:
        clean_url = UPSTASH_URL.rstrip('/')
        url = f"{clean_url}/get/app_data"
        headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            val = res.json().get("result")
            if val:
                if isinstance(val, str):
                    return json.loads(val)
                elif isinstance(val, dict):
                    return val
    except Exception as e:
        print(f"Error reading from Upstash: {e}")
    return None

def save_to_upstash(data):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return False
    try:
        clean_url = UPSTASH_URL.rstrip('/')
        url = f"{clean_url}/set/app_data"
        headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        json_str = json.dumps(data)
        res = requests.post(url, headers=headers, data=json_str, timeout=6)
        return res.status_code == 200
    except Exception as e:
        print(f"Error saving to Upstash: {e}")
        return False

def get_env_backup_data():
    env_data = os.environ.get("PROFILES_JSON_DATA") or os.environ.get("APP_STATE_B64", "")
    if env_data:
        try:
            try:
                decoded = base64.b64decode(env_data).decode("utf-8")
                return json.loads(decoded)
            except Exception:
                return json.loads(env_data)
        except Exception:
            pass
    return None

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
            "blocked_numbers": [],
            "logs": [],
            "debug_logs": [],
            "metrics": {
                "pageviews": 0,
                "unique_ips": []
            }
        }
        upstash_data = load_from_upstash()
        if upstash_data:
            data = upstash_data
        else:
            env_data = get_env_backup_data()
            if env_data:
                data = env_data
                save_to_upstash(data)

        try:
            with open(APP_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

def load_app_data():
    _ensure_storage()
    upstash_data = load_from_upstash()
    
    env_backup = get_env_backup_data()
    data = upstash_data or {}
    
    if not data and os.path.exists(APP_DATA_FILE):
        try:
            with open(APP_DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
        except Exception:
            pass

    if not data and env_backup:
        data = env_backup

    if "settings" not in data:
        data["settings"] = DEFAULT_SETTINGS
    if "blocked_numbers" not in data:
        data["blocked_numbers"] = []
    if "logs" not in data:
        data["logs"] = []
    if "debug_logs" not in data:
        data["debug_logs"] = []
    if "profiles" not in data:
        data["profiles"] = {}
    if "metrics" not in data:
        data["metrics"] = {"pageviews": 0, "unique_ips": []}

    return data

def save_app_data(data):
    _ensure_storage()
    try:
        with open(APP_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving app data to file: {e}")

    save_to_upstash(data)

def record_pageview(client_ip: str = "127.0.0.1"):
    data = load_app_data()
    metrics = data.get("metrics", {"pageviews": 0, "unique_ips": []})
    metrics["pageviews"] = metrics.get("pageviews", 0) + 1
    
    unique_ips = set(metrics.get("unique_ips", []))
    if client_ip and client_ip not in unique_ips and len(unique_ips) < 5000:
        unique_ips.add(client_ip)
        metrics["unique_ips"] = list(unique_ips)

    data["metrics"] = metrics
    save_app_data(data)
    return metrics

def is_number_blocked(mobile: str):
    clean = str(mobile).strip()
    if len(clean) > 10:
        clean = clean[-10:]
    data = load_app_data()
    blocked = data.get("blocked_numbers", [])
    return clean in blocked

def toggle_block_number(mobile: str, block: bool = True):
    clean = str(mobile).strip()
    if len(clean) > 10:
        clean = clean[-10:]
    data = load_app_data()
    blocked = set(data.get("blocked_numbers", []))
    if block:
        blocked.add(clean)
    else:
        blocked.discard(clean)
    data["blocked_numbers"] = list(blocked)
    save_app_data(data)
    return list(blocked)

def get_blocked_numbers():
    data = load_app_data()
    return data.get("blocked_numbers", [])

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

def log_activation(mobile: str, email: str, code: str, success: bool, message: str, action: str = "ACTIVATE"):
    data = load_app_data()
    if "logs" not in data:
        data["logs"] = []

    clean_mobile = str(mobile).strip()
    if len(clean_mobile) > 10:
        clean_mobile = clean_mobile[-10:]

    entry = {
        "id": len(data["logs"]) + 1,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "month_key": time.strftime("%Y-%m"),
        "mobile": clean_mobile,
        "email": str(email).strip().lower(),
        "code": str(code).strip(),
        "action": action,
        "success": bool(success),
        "message": str(message)
    }
    data["logs"].insert(0, entry)
    data["logs"] = data["logs"][:2000]
    save_app_data(data)
    return entry

def log_activation_detail(mobile: str, email: str, code: str, success: bool, message: str, steps: list):
    data = load_app_data()
    if "debug_logs" not in data:
        data["debug_logs"] = []

    clean_mobile = str(mobile).strip()
    if len(clean_mobile) > 10:
        clean_mobile = clean_mobile[-10:]

    detail_entry = {
        "id": len(data["debug_logs"]) + 1,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mobile": clean_mobile or "N/A",
        "email": str(email).strip().lower() or "N/A",
        "code": str(code).strip() or "N/A",
        "success": bool(success),
        "message": str(message),
        "steps": steps or []
    }
    data["debug_logs"].insert(0, detail_entry)
    data["debug_logs"] = data["debug_logs"][:500]  # Store last 500 in-depth executions
    save_app_data(data)
    return detail_entry

def get_debug_logs():
    data = load_app_data()
    return data.get("debug_logs", [])

def clear_debug_logs():
    data = load_app_data()
    data["debug_logs"] = []
    save_app_data(data)
    return True

def check_activation_limit(mobile: str):
    if is_number_blocked(mobile):
        return False, "This mobile number has been suspended. Please contact support via WhatsApp."

    settings = get_settings()
    max_monthly = int(settings.get("max_monthly_activations", 3))
    max_total = int(settings.get("max_total_activations", 0))

    if max_monthly == 0 and max_total == 0:
        return True, "Allowed"

    data = load_app_data()
    logs = data.get("logs", [])
    clean_mobile = str(mobile).strip()
    if len(clean_mobile) > 10:
        clean_mobile = clean_mobile[-10:]

    current_month = time.strftime("%Y-%m")

    monthly_count = sum(1 for l in logs if l.get("mobile") == clean_mobile and l.get("month_key") == current_month and l.get("success") and l.get("action") == "ACTIVATE")
    total_count = sum(1 for l in logs if l.get("mobile") == clean_mobile and l.get("success") and l.get("action") == "ACTIVATE")

    if max_monthly > 0 and monthly_count >= max_monthly:
        return False, f"Monthly activation limit reached ({monthly_count}/{max_monthly} used this month). Please contact support to upgrade."

    if max_total > 0 and total_count >= max_total:
        return False, f"Total activation limit reached ({total_count}/{max_total} used). Please contact support."

    return True, "Allowed"

def get_activation_stats():
    data = load_app_data()
    logs = data.get("logs", [])
    debug_logs = data.get("debug_logs", [])
    settings = get_settings()
    blocked = data.get("blocked_numbers", [])
    metrics = data.get("metrics", {"pageviews": 0, "unique_ips": []})

    total_activations = sum(1 for l in logs if l.get("action") == "ACTIVATE")
    successful_activations = sum(1 for l in logs if l.get("success") and l.get("action") == "ACTIVATE")
    failed_activations = sum(1 for l in logs if not l.get("success") and l.get("action") == "ACTIVATE")
    
    user_stats = {}
    current_month = time.strftime("%Y-%m")

    for l in logs:
        m = l.get("mobile", "Unknown")
        if not m or m == "Unknown":
            continue
        if m not in user_stats:
            user_stats[m] = {
                "mobile": m,
                "total": 0,
                "monthly": 0,
                "last_active": l.get("timestamp"),
                "is_blocked": m in blocked
            }
        if l.get("action") == "ACTIVATE" and l.get("success"):
            user_stats[m]["total"] += 1
            if l.get("month_key") == current_month:
                user_stats[m]["monthly"] += 1

    for b in blocked:
        if b not in user_stats:
            user_stats[b] = {
                "mobile": b,
                "total": 0,
                "monthly": 0,
                "last_active": "N/A",
                "is_blocked": True
            }

    return {
        "pageviews": metrics.get("pageviews", 0),
        "unique_visitors": len(metrics.get("unique_ips", [])),
        "total_logs": total_activations,
        "successful_logs": successful_activations,
        "failed_logs": failed_activations,
        "unique_users_count": len(user_stats),
        "blocked_count": len(blocked),
        "settings": settings,
        "user_stats": sorted(list(user_stats.values()), key=lambda x: x["total"], reverse=True),
        "recent_logs": logs[:200],
        "debug_logs": debug_logs[:200]
    }

def export_full_state_b64():
    data = load_app_data()
    json_str = json.dumps(data)
    return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
