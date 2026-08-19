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

            # 1. Navigate to activation page
            try:
                await page.goto("https://www.netflix.com/tv2", wait_until="domcontentloaded", timeout=25000)
            except Exception:
                await page.goto("https://www.netflix.com/tv2", wait_until="commit", timeout=25000)

            # Wait for either the inputs or login redirect
            try:
                await page.wait_for_selector(
                    "input[data-uia^='pin-number-'], input[name='rendezvousCode'], input[autocomplete='one-time-code'], input[name='userLoginId']", 
                    state="visible", 
                    timeout=15000
                )
            except Exception:
                pass

            await page.wait_for_timeout(1500)

            current_url = page.url
            # Pre-check: Expired session / Login redirect
            if "login" in current_url or await page.locator("input[name='userLoginId']").count() > 0:
                await browser.close()
                return {
                    "success": False,
                    "error_code": "COOKIES_EXPIRED",
                    "message": "cookies expired please tell admin to update"
                }

            # 2. Identify input boxes
            pin_inputs = page.locator("input[data-uia^='pin-number-']")
            pin_count = await pin_inputs.count()

            if pin_count >= 8:
                # Modern Split-Box PIN UI: Focus 1st box and type naturally with keyboard
                first_box = page.locator("input[data-uia='pin-number-0']")
                await first_box.click()
                await page.wait_for_timeout(200)
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                for char in clean_code:
                    await page.keyboard.press(char)
                    await page.wait_for_timeout(100)
            else:
                fallback_input = page.locator("input[name='rendezvousCode'], input[autocomplete='one-time-code'], input[data-hcw-form-control-element], input[type='text'], input[type='number']").first
                if await fallback_input.count() == 0:
                    await browser.close()
                    return {
                        "success": False,
                        "error_code": "INPUT_NOT_FOUND",
                        "message": "Could not locate code input fields on netflix.com/tv2."
                    }
                await fallback_input.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await fallback_input.type(clean_code, delay=100)

            await page.wait_for_timeout(1000)

            # 3. Submit code (if not auto-submitted by Netflix)
            submit_btn = page.locator("button[data-uia='continue-button'], button[type='submit'], button[data-uia*='submit'], button[data-uia*='continue']")
            if await submit_btn.count() > 0 and await submit_btn.first.is_visible():
                try:
                    await submit_btn.first.click(timeout=3000)
                except Exception:
                    await page.keyboard.press("Enter")
            else:
                await page.keyboard.press("Enter")

            # Allow time for Netflix server to respond
            await page.wait_for_timeout(4000)

            # 4. Check for ACTUAL visible error elements
            error_locators = page.locator("[data-uia*='error'], .ui-message-error, .ui-message-contents, [data-hcw-form-control-validation]")
            error_count = await error_locators.count()

            if error_count > 0:
                for idx in range(error_count):
                    el = error_locators.nth(idx)
                    if await el.is_visible():
                        err_text = (await el.inner_text()).strip()
                        if err_text:
                            await browser.close()
                            return {
                                "success": False,
                                "error_code": "ACTIVATION_FAILED",
                                "message": err_text
                            }

            # 5. Check if activation succeeded (URL change or presence of success message/absence of inputs)
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
