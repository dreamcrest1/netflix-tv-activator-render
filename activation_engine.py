import os
import sys
import re
import asyncio
import subprocess

PW_BROWSERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pw-browsers")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PW_BROWSERS_DIR

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
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
            # 1. Anti-Bot Browser Launch
            launch_args = [
                "--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage", "--disable-gpu", "--no-first-run", "--no-zygote",
                "--single-process", "--disable-extensions", "--incognito"
            ]
            
            try:
                browser = await p.chromium.launch(headless=True, args=launch_args)
            except Exception as launch_err:
                if "Executable doesn't exist" in str(launch_err) or "playwright install" in str(launch_err):
                    ensure_chromium_installed()
                    browser = await p.chromium.launch(headless=True, args=launch_args)
                else:
                    raise launch_err

            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )

            # 2. Cookie Injection
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

            # 3. Navigation with Double-Check
            try:
                await page.goto("https://www.netflix.com/tv2", wait_until="networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                await page.goto("https://www.netflix.com/tv2", wait_until="domcontentloaded", timeout=20000)

            # Wait for React to render the forms
            await page.wait_for_timeout(2500)

            # 4. Check for Expired Cookies (Login Redirect)
            if "login" in page.url or await page.locator("input[name='userLoginId']").count() > 0:
                await browser.close()
                return {"success": False, "error_code": "COOKIES_EXPIRED", "message": "Cookies expired. Please update via admin panel."}

            # 5. DYNAMIC UI DETECTION (White UI vs Black UI)
            split_inputs = page.locator("input.pin-number-input, input[data-uia^='pin-number-']")
            single_input = page.locator("input[name='rendezvousCode'], input[autocomplete='one-time-code']").first
            
            ui_type = None
            
            # Wait dynamically for either UI to appear (up to 15 seconds)
            for _ in range(15):
                if await split_inputs.count() >= 8:
                    ui_type = "WHITE_UI_SPLIT"
                    break
                elif await single_input.count() > 0:
                    ui_type = "BLACK_UI_SINGLE"
                    break
                await page.wait_for_timeout(1000)

            if not ui_type:
                await browser.close()
                return {"success": False, "error_code": "INPUT_NOT_FOUND", "message": "Could not locate any input fields. Netflix UI may have failed to load."}

            # 6. ROUTED TYPING STRATEGY
            if ui_type == "WHITE_UI_SPLIT":
                # Handle White UI: Iterate through all 8 individual boxes
                for i in range(8):
                    box = split_inputs.nth(i)
                    await box.click()
                    # Use evaluate to clear to avoid React state bouncing
                    await box.evaluate("el => el.value = ''")
                    # Press sequentially to trigger natural keyboard events
                    await page.keyboard.press_sequentially(clean_code[i], delay=100)
                    await page.wait_for_timeout(150) # Tiny pause between boxes

            elif ui_type == "BLACK_UI_SINGLE":
                # Handle Black UI: Single merged box
                await single_input.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                # Press sequentially mimics a human typing on the keyboard
                await single_input.press_sequentially(clean_code, delay=150)

            await page.wait_for_timeout(1000)

            # 7. MULTI-LOCATOR FORM SUBMISSION
            submit_selectors = [
                "button[data-uia='continue-button']", 
                "button:has-text('Enter Code to Continue')", # White UI button text
                "button:has-text('Continue')",              # Black UI button text
                "button[type='submit']"
            ]
            
            clicked = False
            for selector in submit_selectors:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_enabled():
                    await btn.click(force=True)
                    clicked = True
                    break
            
            # Fallback if no button found
            if not clicked:
                await page.keyboard.press("Enter")

            # 8. THE VERIFICATION POLLING LOOP
            # Instead of assuming success/failure instantly, poll the DOM for 15 seconds
            for _ in range(15):
                await page.wait_for_timeout(1000)
                
                # Condition A: URL changed successfully
                if "/tv2" not in page.url:
                    await browser.close()
                    return {"success": True, "message": "netflix activated"}
                
                # Condition B: Explicit Error Message Appeared on Screen
                error_locators = page.locator("div[data-hcw-form-control-validation='true'], [data-uia*='error'], .ui-message-error, .ui-message-contents")
                if await error_locators.count() > 0:
                    for idx in range(await error_locators.count()):
                        el = error_locators.nth(idx)
                        if await el.is_visible():
                            err_text = (await el.inner_text()).strip()
                            if err_text and len(err_text) > 4:
                                await browser.close()
                                return {"success": False, "error_code": "ACTIVATION_FAILED", "message": f"TV rejected code: {err_text}"}

                # Condition C: Success Text Appeared
                success_text = page.locator("text='connected', text='Ready to watch', text='Success', text='Start Watching'")
                if await success_text.count() > 0 and await success_text.first.is_visible():
                    await browser.close()
                    return {"success": True, "message": "netflix activated"}

            # 9. SILENT FAILURE FALLBACK
            # If 15 seconds pass and the input field is still visible on the screen, it failed.
            if ui_type == "BLACK_UI_SINGLE" and await single_input.is_visible():
                 await browser.close()
                 return {"success": False, "error_code": "ACTIVATION_FAILED", "message": "Activation did not process. The code might be expired."}
            elif ui_type == "WHITE_UI_SPLIT" and await split_inputs.first.is_visible():
                 await browser.close()
                 return {"success": False, "error_code": "ACTIVATION_FAILED", "message": "Activation did not process. The code might be expired."}

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
            "message": f"TV Activation code must be exactly 8 characters.",
            "formatted_output": "Invalid TV activation code format."
        }

    cookies = get_profile_cookies(email)
    if not cookies or len(cookies) == 0:
        msg = "Cookies expired. Please tell admin to update."
        return {"success": False, "error_code": "COOKIES_EXPIRED", "message": msg, "formatted_output": msg}

    last_error = None
    
    # Retry mechanism: Attempt up to 2 times
    for attempt in range(1, 3):
        try:
            res = await run_activation_attempt(email=email, clean_code=clean_code, cookies=cookies)
            
            if res.get("error_code") == "COOKIES_EXPIRED":
                msg = "Cookies expired. Please tell admin to update."
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
            print(f"Attempt {attempt} failed: {e}. Retrying...")
            await asyncio.sleep(2)

    msg = f"Automation error: {last_error}"
    return {"success": False, "error_code": "EXECUTION_ERROR", "message": msg, "formatted_output": msg}
