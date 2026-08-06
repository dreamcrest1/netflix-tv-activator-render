import json
import base64
from data_manager import (
    get_all_profiles, add_or_update_profile, delete_profile,
    get_profile_cookies, export_full_state_b64
)

def export_profiles_b64():
    return export_full_state_b64()

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
