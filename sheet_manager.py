import requests
import pandas as pd
import io
import re

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

def fetch_and_validate_user(mobile_number: str, custom_sheet_url: str = None):
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
        
        df = pd.read_csv(io.StringIO(res.text))
        if df.empty:
            return {
                "valid": False,
                "error_code": "EMPTY_SHEET",
                "message": "Google Sheet contains no data."
            }
        
        cols = {str(c).strip().lower(): c for c in df.columns}
        
        mobile_col = None
        for key in ["mobile", "phone", "number", "contact", "mobile number", "phone number"]:
            if key in cols:
                mobile_col = cols[key]
                break
        if not mobile_col:
            mobile_col = df.columns[0]
            
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
        for _, row in df.iterrows():
            val = re.sub(r'\D', '', str(row[mobile_col]))
            if len(val) >= 10 and val[-10:] == clean_mobile:
                matched_row = row
                break

        if matched_row is None:
            return {
                "valid": False,
                "error_code": "MOBILE_NOT_FOUND",
                "message": f"Mobile number '{clean_mobile}' is not registered in our records."
            }

        expiry_str = str(matched_row[expiry_col]) if expiry_col else None
        if not expiry_str or expiry_str.lower() in ["nan", "none", "null"]:
            return {
                "valid": False,
                "error_code": "NO_EXPIRY_DATE",
                "message": "Expiry date missing for this subscription."
            }

        try:
            expiry_date = pd.to_datetime(expiry_str, dayfirst=True)
            current_date = pd.Timestamp.now().floor('d')
            
            if current_date > expiry_date:
                return {
                    "valid": False,
                    "error_code": "PLAN_EXPIRED",
                    "message": f"Expired plan please renew (Expired on {expiry_date.strftime('%Y-%m-%d')}).",
                    "expiry_date": expiry_date.strftime("%Y-%m-%d")
                }
        except Exception:
            pass

        assigned_email = str(matched_row[email_col]).strip() if email_col else "Default Profile"

        return {
            "valid": True,
            "mobile": clean_mobile,
            "assigned_email": assigned_email,
            "expiry_date": expiry_date.strftime("%Y-%m-%d") if 'expiry_date' in locals() else str(expiry_str),
            "message": "User verified successfully."
        }

    except Exception as e:
        return {
            "valid": False,
            "error_code": "SERVER_ERROR",
            "message": f"Error validating sheet data: {str(e)}"
        }