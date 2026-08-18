import os
import sys
import re
import asyncio
import subprocess

PW_BROWSERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pw-browsers")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PW_BROWSERS_DIR

from playwright.async_api import async_playwright
from profile_manager import get_profile_cookies

def ensure_chromium_installed():
    try:
        print(f"Downloading Chromium browser binary into {PW_BROWSERS_DIR}...")
        os.makedirs(PW_BROWSERS_DIR, exist_ok=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"Error installing Chromium: {e}")

async def run_activation_attempt(email: str, clean_code: str, cookies: list):
    async with async_playwright() as p:
        browser = None
        try:
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-zygote",
                        "--single-process",
                        "--disable-extensions"
                    ]
                )
            except Exception as launch_err:
                if "Executable doesn't exist" in str(launch_err) or "playwright install" in str(launch_err):
                    print("Chromium browser executable missing. Auto-installing Chromium...")
                    ensure_chromium_installed()
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-blink-features=AutomationControlled",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--no-first-run",
                            "--no-zygote",
                            "--single-process",
                            "--disable-extensions"
                        ]
                    )
                else:
                    raise launch_err

            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )

            formatted_cookies = []
            for c in cookies:
                cookie_dict = {
                    "name": c.get("name"),
                    "value": c.get("value"),
                    "domain": c.get("domain", ".netflix.com"),
                    "path": c.get("path", "/")
                }
                if "sameSite" in c and c["sameSite"] in ["Strict", "Lax", "None"]:
                    cookie_dict["sameSite"] = c["sameSite"]
                formatted_cookies.append(cookie_dict)

            await context.add_cookies(formatted_cookies)
            page = await context.new_page()

            # 1. Navigate to tv2 page
            try:
                await page.goto("https://www.netflix.com/tv2", wait_until="domcontentloaded", timeout=25000)
            except Exception:
                await page.goto("https://www.netflix.com/tv2", wait_until="commit", timeout=25000)

            # Wait dynamically for the input elements to render (solves the 0 count issue)
            try:
                await page.wait_for_selector(
                    "input[data-uia^='pin-number-'], input[name='rendezvousCode'], input[autocomplete='one-time-code']", 
                    state="visible", 
                    timeout=15000
                )
            except Exception:
                pass # Proceed to let the existing checks handle the missing inputs gracefully

            await page.wait_for_timeout(2000)

            current_url = page.url
            # Pre-check: If redirected to login page or login input exists -> Cookies Expired
            if "login" in current_url or await page.locator("input[name='userLoginId']").count() > 0:
                await browser.close()
                return {
                    "success": False,
                    "error_code": "COOKIES_EXPIRED",
                    "message": "cookies expired please tell admin to update"
                }

            # Target input field according to updated Netflix UI
            code_input = page.locator("input[data-uia^='pin-number-']")
            input_count = await code_input.count()

            if input_count == 0:
                # Fallback to general input locators
                code_input = page.locator("input[name='rendezvousCode'], input[autocomplete='one-time-code'], input[data-hcw-form-control-element], input[type='text'], input[type='number']")
                input_count = await code_input.count()

            if input_count == 0:
                if "login" in page.url or await page.locator("input[name='userLoginId']").count() > 0:
                    await browser.close()
                    return {
                        "success": False,
                        "error_code": "COOKIES_EXPIRED",
                        "message": "cookies expired please tell admin to update"
                    }
                
                await browser.close()
                return {
                    "success": False,
                    "error_code": "INPUT_NOT_FOUND",
                    "message": "Could not locate code input fields on netflix.com/tv2."
                }

            # Fill code into updated input element
            if await page.locator("input[data-uia^='pin-number-']").count() >= 8:
                # Explicitly fill split boxes by their direct ID mappings
                for i in range(8):
                    inp = page.locator(f"input[data-uia='pin-number-{i}']")
                    await inp.focus()
                    await inp.fill("")
                    await inp.type(clean_code[i], delay=80)
            elif input_count >= 8:
                for i in range(min(8, input_count)):
                    inp = code_input.nth(i)
                    await inp.focus()
                    await inp.fill("")
                    await inp.type(clean_code[i], delay=80)
            else:
                main_input = code_input.first
                await main_input.focus()
                try:
                    await main_input.fill("")
                except Exception:
                    pass
                await main_input.type(clean_code, delay=80)

            await page.wait_for_timeout(800)

            # Updated submit button matching new Netflix UI (data-uia="continue-button")
            submit_btn = page.locator("button[data-uia='continue-button'], button[type='submit'], button[data-uia*='submit'], button[data-uia*='continue']")
            if await submit_btn.count() > 0 and await submit_btn.first.is_visible():
                await submit_btn.first.click()
            else:
                await page.keyboard.press("Enter")

            await page.wait_for_timeout(3500)

            page_content = (await page.content()).lower()
            error_keywords = ["incorrect", "invalid code", "code expired", "try again", "unable to connect", "something went wrong"]
            has_error = any(err in page_content for err in error_keywords)

            if has_error:
                error_elem = page.locator("[data-uia*='error'], .ui-message-error, .ui-message-contents, [data-hcw-form-control-validation]")
                err_msg = "Invalid or expired TV code. Please check your TV screen."
                if await error_elem.count() > 0:
                    try:
                        err_msg = await error_elem.first.inner_text()
                    except Exception:
                        pass
                
                await browser.close()
                return {
                    "success": False,
                    "error_code": "ACTIVATION_FAILED",
                    "message": err_msg
                }

            await browser.close()
            return {"success": True, "message": "netflix activated"}

        except Exception as e:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            raise e

async def activate_tv(email: str, raw_code: str, mobile: str = "", expiry_date: str = ""):
    clean_code = re.sub(r'[^a-zA-Z0-9]', '', raw_code).upper()
    if len(clean_code) != 8:
        return {
            "success": False,
            "error_code": "INVALID_CODE_FORMAT",
            "message": f"TV Activation code must be exactly 8 characters. Received: {raw_code}",
            "formatted_output": "Invalid TV activation code format."
        }

    cookies = get_profile_cookies(email)
    if not cookies or len(cookies) == 0:
        msg = "cookies expired please tell admin to update"
        return {
            "success": False,
            "error_code": "COOKIES_EXPIRED",
            "message": msg,
            "formatted_output": msg
        }

    last_error = None
    for attempt in range(1, 3):
        try:
            res = await run_activation_attempt(email=email, clean_code=clean_code, cookies=cookies)
            if res.get("error_code") == "COOKIES_EXPIRED":
                msg = "cookies expired please tell admin to update"
                res["message"] = msg
                res["formatted_output"] = msg
                return res

            if res.get("success") or res.get("error_code") in ["INVALID_CODE_FORMAT", "ACTIVATION_FAILED"]:
                if res.get("success"):
                    user_mobile_str = str(mobile).strip() if mobile else "N/A"
                    expiry_str = str(expiry_date).strip() if expiry_date else "Active"
                    
                    formatted_output = (
                        f"User: {user_mobile_str} Expiry Date: {expiry_str}\n\n\n"
                        "📺 *1. If TV asks for a code (household / travelling code issue)\n\n"
                        "*GO TO https://netflix-code-fetcher-5q.vercel.app/\n"
                        "SELECT YOUR EMAIL\n"
                        f"Email : {email}\n"
                        "CLICK FETCH AND UPDATE CODE"
                    )
                    res["formatted_output"] = formatted_output
                    res["email"] = email
                    res["code"] = clean_code
                else:
                    res["formatted_output"] = res.get("message", "Activation failed.")
                return res
            last_error = res.get("message", "Unknown error")
        except Exception as e:
            last_error = str(e)
            print(f"Attempt {attempt} failed with error: {e}. Retrying...")
            await asyncio.sleep(1)

    msg = f"Automation error: {last_error}"
    return {
        "success": False,
        "error_code": "EXECUTION_ERROR",
        "message": msg,
        "formatted_output": msg
    }
