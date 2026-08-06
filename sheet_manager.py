import csv
import io
import re
from datetime import datetime
from data_manager import is_number_blocked

DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS--Y2zpv344p1buBTni7_acc-Hu2_f0J1z_D3cf7bW4hy1bY3TNSyxj8BRC0sYMRZVMy3HoG7giQbO/pub?output=csv"

def get_csv_url(sheet_url: str) -> str:
    if not sheet_url:
        sheet_url = DEFAULT_SHEET_URL
    sheet_url = sheet_url.strip()
    if "/pubhtml" in sheet_url:
        sheet_url = sheet_url.replace("/pubhtml", "/pub?output=csv")
    elif "/pub" in sheet_url and "output=csv" not in sheet_url:
        sheet_url = sheet_url.split("?")[0] + "?output=csv"
    return sheet_url

def parse_date_flexible(date_str):
    if not date_str:
        return None
    date_str = str(date_str).strip()
    
    formats = (
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y/%m/%d",
        "%d %b %Y", "%d %B %Y", "%d-%b-%y", "%d-%b-%Y", "%d-%B-%y", "%d-%B-%Y",
        "%d/%b/%y", "%d/%b/%Y", "%b %d, %Y", "%B %d, %Y", "%d/%m/%y", "%m/%d/%y"
    )
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
            
    try:
        import pandas as pd
        dt = pd.to_datetime(date_str, dayfirst=True)
        if not pd.isna(dt):
            return dt.to_pydatetime()
    except Exception:
        pass

    return None

def format_expiry_display(dt, raw_fallback=""):
    if not dt:
        return raw_fallback or "Active"
    
    day = dt.day
    month_map = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sept", 10: "Oct", 11: "Nov", 12: "Dec"
    }
    month_str = month_map.get(dt.month, dt.strftime("%b"))
    year = dt.year
    
    return f"{day} {month_str} {year}"

def extract_email_from_row(row_dict):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    # 1. Search all row cell values for an email regex match
    for col, val in row_dict.items():
        val_str = str(val).strip()
        match = re.search(email_pattern, val_str)
        if match:
            return match.group(0).lower()

    # 2. Inspect column headers
    cols = {str(k).strip().lower(): k for k in row_dict.keys() if k}
    for key in ["email", "profile", "profiles", "account", "netflix", "acc", "mail", "user"]:
        for c_lower, c_orig in cols.items():
            if key in c_lower:
                val = str(row_dict.get(c_orig, '')).strip()
                if val and val.lower() not in ["nan", "none", "null"]:
                    return val.lower()
                    
    return "Default Profile"

def fetch_and_validate_user(mobile_number: str, custom_sheet_url: str = None):
    import requests
    clean_mobile = re.sub(r'\D', '', str(mobile_number).strip())
    if len(clean_mobile) < 10:
        return {
            "valid": False,
            "error_code": "INVALID_MOBILE",
            "message": "Please enter a valid 10-digit mobile number."
        }
    
    if len(clean_mobile) > 10:
        clean_mobile = clean_mobile[-10:]

    if is_number_blocked(clean_mobile):
        return {
            "valid": False,
            "error_code": "USER_BLOCKED",
            "message": f"Mobile number '{clean_mobile}' has been suspended/blocked. Please contact support via WhatsApp."
        }

    csv_url = get_csv_url(custom_sheet_url)
    
    try:
        res = requests.get(csv_url, timeout=12)
        if res.status_code != 200:
            return {
                "valid": False,
                "error_code": "SHEET_FETCH_ERROR",
                "message": f"Unable to reach Google Sheet (HTTP {res.status_code})."
            }
        
        f = io.StringIO(res.text)
        reader = list(csv.DictReader(f))
        if not reader:
            return {
                "valid": False,
                "error_code": "EMPTY_SHEET",
                "message": "Google Sheet contains no data."
            }
        
        fieldnames = reader[0].keys()
        cols = {str(k).strip().lower(): k for k in fieldnames if k}
        
        mobile_col = None
        for key in ["mobile", "phone", "number", "contact", "mobile number", "phone number"]:
            if key in cols:
                mobile_col = cols[key]
                break
        if not mobile_col and fieldnames:
            mobile_col = list(fieldnames)[0]
            
        expiry_col = None
        for key in ["expiry", "expiry date", "expire", "expiration", "expire date", "validity", "valid until"]:
            if key in cols:
                expiry_col = cols[key]
                break

        matched_row = None
        for row in reader:
            val = re.sub(r'\D', '', str(row.get(mobile_col, '')))
            if len(val) >= 10 and val[-10:] == clean_mobile:
                matched_row = row
                break

        if matched_row is None:
            return {
                "valid": False,
                "error_code": "MOBILE_NOT_FOUND",
                "message": f"Mobile number '{clean_mobile}' is not registered in our records."
            }

        expiry_str = str(matched_row.get(expiry_col, '')).strip() if expiry_col else ""
        if not expiry_str or expiry_str.lower() in ["nan", "none", "null"]:
            for k, v in matched_row.items():
                if parse_date_flexible(v):
                    expiry_str = str(v).strip()
                    break

        expiry_dt = parse_date_flexible(expiry_str)
        formatted_display_expiry = format_expiry_display(expiry_dt, raw_fallback=expiry_str)

        if expiry_dt:
            expiry_end_of_day = expiry_dt.replace(hour=23, minute=59, second=59)
            current_dt = datetime.now()
            
            if current_dt > expiry_end_of_day:
                return {
                    "valid": False,
                    "error_code": "PLAN_EXPIRED",
                    "message": f"Expired plan please renew (Expired on {formatted_display_expiry}).",
                    "expiry_date": formatted_display_expiry
                }

        assigned_email = extract_email_from_row(matched_row)

        return {
            "valid": True,
            "mobile": clean_mobile,
            "assigned_email": assigned_email,
            "expiry_date": formatted_display_expiry,
            "message": "User verified successfully."
        }

    except Exception as e:
        return {
            "valid": False,
            "error_code": "SERVER_ERROR",
            "message": f"Error validating sheet data: {str(e)}"
        }
