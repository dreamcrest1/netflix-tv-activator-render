import csv
import io
import re
from datetime import datetime

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
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return None

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
                
        email_col = None
        for key in ["email", "profile", "netflix email", "account", "netflix profile", "acc"]:
            if key in cols:
                email_col = cols[key]
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

        expiry_str = str(matched_row.get(expiry_col, '')).strip()
        if not expiry_str or expiry_str.lower() in ["nan", "none", "null"]:
            return {
                "valid": False,
                "error_code": "NO_EXPIRY_DATE",
                "message": "Expiry date missing for this subscription."
            }

        expiry_dt = parse_date_flexible(expiry_str)
        if expiry_dt:
            current_dt = datetime.now()
            if current_dt > expiry_dt:
                return {
                    "valid": False,
                    "error_code": "PLAN_EXPIRED",
                    "message": f"Expired plan please renew (Expired on {expiry_dt.strftime('%Y-%m-%d')}).",
                    "expiry_date": expiry_dt.strftime("%Y-%m-%d")
                }

        assigned_email = str(matched_row.get(email_col, '')).strip() if email_col else "Default Profile"

        return {
            "valid": True,
            "mobile": clean_mobile,
            "assigned_email": assigned_email,
            "expiry_date": expiry_dt.strftime("%Y-%m-%d") if expiry_dt else expiry_str,
            "message": "User verified successfully."
        }

    except Exception as e:
        return {
            "valid": False,
            "error_code": "SERVER_ERROR",
            "message": f"Error validating sheet data: {str(e)}"
        }
