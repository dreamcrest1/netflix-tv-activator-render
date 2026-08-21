import os
import sys
import re
import time
import asyncio
import subprocess

PW_BROWSERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pw-browsers")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PW_BROWSERS_DIR

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from profile_manager import get_profile_cookies
from data_manager import log_activation_detail

def ensure_chromium_installed():
    try:
        print(f"Downloading Chromium binary into {PW_BROWSERS_DIR}...")
        os.makedirs(PW_BROWSERS_DIR, exist_ok=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"Error installing Chromium: {e}")

async def run_activation_attempt(email: str, clean_code: str, cookies: list, mobile: str = ""):
    steps = []
    start_time = time.time()
    
    def log_step(msg: str):
        elapsed = round(time.time() - start_time, 2)
        steps.append(f"[{elapsed}s] {msg}")

    log_step(f"Starting activation for {email} with code {clean_code}")

    async with async_playwright() as p:
        browser = None
        try:
            # 1. Launch Browser
            launch_args = [
                "--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage", "--disable-gpu", "--no-first-run", "--no-zygote",
                "--single-process", "--disable-extensions"
            ]
            
            try:
                browser = await p.chromium.launch(headless=True, args=launch_args)
            except Exception as launch_err:
                if "Executable doesn't exist" in str(launch_err) or "playwright install" in str(launch_err):
                    log_step("Chromium binary missing. Triggering auto-install...")
                    ensure_chromium_installed()
                    browser = await p.chromium.launch(headless=True, args=launch_args)
                else:
                    raise launch_err

            log_step("Browser launched successfully.")

            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )

            # 2. Inject Cookies
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
            log_step(f"Injected {len(formatted_cookies)} profile cookies.")

            page = await context.new_page()

            # 3. Fast Navigation
            log_step("Navigating to https://www.netflix.com/tv2...")
            try:
                await page.goto("https://www.netflix.com/tv2", wait_until="domcontentloaded", timeout=18000)
            except PlaywrightTimeoutError:
                log_step("Page load exceeded 18s, forcing commit check...")
                await page.goto("https://www.netflix.com/tv2", wait_until="commit", timeout=10000)

            await page.wait_for_timeout(1500)
            current_url = page.url
            log_step(f"Landed on URL: {current_url}")

            # 4. Check for Session Expiry / Login Page
            if "login" in current_url or await page.locator("input[name='userLoginId']").count() > 0:
                log_step("Redirected to login page. Session cookies expired.")
                await browser.close()
                err_msg = "Cookies expired. Please update via admin panel."
                log_activation_detail(mobile, email, clean_code, False, err_msg, steps)
                return {"success": False, "error_code": "COOKIES_EXPIRED", "message": err_msg}

            # 5. Fast Adaptive UI Detection
            split_inputs = page.locator("input.pin-number-input, input[data-uia^='pin-number-']")
            single_input = page.locator("input[name='rendezvousCode'], input[autocomplete='one-time-code']").first
            
            ui_type = None
            for _ in range(6):  # 6 second max detection
                if await split_inputs.count() >= 8:
                    ui_type = "WHITE_UI_SPLIT"
                    break
                elif await single_input.count() > 0:
                    ui_type = "BLACK_UI_SINGLE"
                    break
                await page.wait_for_timeout(1000)

            log_step(f"Detected UI Variant: {ui_type or 'NONE'}")

            if not ui_type:
                await browser.close()
                err_msg = "Could not locate code input field on netflix.com/tv2."
                log_activation_detail(mobile, email, clean_code, False, err_msg, steps)
                return {"success": False, "error_code": "INPUT_NOT_FOUND", "message": err_msg}

            # 6. Type Code
            if ui_type == "WHITE_UI_SPLIT":
                log_step("Typing code into 8 split boxes...")
                for i in range(8):
                    box = split_inputs.nth(i)
                    await box.click()
                    await box.evaluate("el => el.value = ''")
                    await box.type(clean_code[i], delay=50)
            else:
                log_step("Entering code into single input field and dispatching React events...")
                await single_input.click()
                await single_input.fill("")
                await single_input.type(clean_code, delay=50)
                await page.evaluate(f"""
                    () => {{
                        const el = document.querySelector("input[name='rendezvousCode'], input[autocomplete='one-time-code']");
                        if (el) {{
                            el.value = '{clean_code}';
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }}
                """)

            await page.wait_for_timeout(600)

            # 7. Form Submission
            submit_selectors = [
                "button[data-uia='continue-button']", 
                "button:has-text('Enter Code to Continue')", 
                "button:has-text('Continue')", 
                "button[type='submit']"
            ]
            
            clicked = False
            for selector in submit_selectors:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    log_step(f"Clicking submit button with selector: {selector}")
                    await btn.click(force=True)
                    clicked = True
                    break
            
            if not clicked:
                log_step("Submit button not found; sending Enter key.")
                await page.keyboard.press("Enter")

            # 8. Result Polling Loop (8 seconds max)
            log_step("Awaiting activation verification...")
            for _ in range(8):
                await page.wait_for_timeout(1000)
                
                # Condition A: Redirected away from tv2
                if "/tv2" not in page.url:
                    log_step(f"Success! URL redirected to: {page.url}")
                    await browser.close()
                    log_activation_detail(mobile, email, clean_code, True, "Activation successful (URL Redirected)", steps)
                    return {"success": True, "message": "netflix activated"}

                # Condition B: Explicit Error Message
                error_locators = page.locator("div[data-hcw-form-control-validation='true'], [data-uia*='error'], .ui-message-error, .ui-message-contents")
                if await error_locators.count() > 0:
                    for idx in range(await error_locators.count()):
                        el = error_locators.nth(idx)
                        if await el.is_visible():
                            err_text = (await el.inner_text()).strip()
                            if err_text and len(err_text) > 3:
                                log_step(f"Netflix error banner displayed: '{err_text}'")
                                await browser.close()
                                log_activation_detail(mobile, email, clean_code, False, err_text, steps)
                                return {"success": False, "error_code": "ACTIVATION_FAILED", "message": err_text}

                # Condition C: Success confirmation on page
                success_text = page.locator("text='connected', text='Ready to watch', text='Success', text='Start Watching'")
                if await success_text.count() > 0 and await success_text.first.is_visible():
                    log_step("Success banner detected on page.")
                    await browser.close()
                    log_activation_detail(mobile, email, clean_code, True, "Activation successful (Success banner detected)", steps)
                    return {"success": True, "message": "netflix activated"}

            # 9. Silent Failure Fallback Check
            if (ui_type == "BLACK_UI_SINGLE" and await single_input.is_visible()) or (ui_type == "WHITE_UI_SPLIT" and await split_inputs.first.is_visible()):
                log_step("Code input field remained visible after submission. Code rejected or expired.")
                await browser.close()
                err_msg = "Invalid or expired TV code. Please check your TV screen."
                log_activation_detail(mobile, email, clean_code, False, err_msg, steps)
                return {"success": False, "error_code": "ACTIVATION_FAILED", "message": err_msg}

            log_step("Inputs cleared and no error detected. Assuming success.")
            await browser.close()
            log_activation_detail(mobile, email, clean_code, True, "Activation completed", steps)
            return {"success": True, "message": "netflix activated"}

        except Exception as e:
            log_step(f"Exception encountered: {str(e)}")
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            log_activation_detail(mobile, email, clean_code, False, f"Automation exception: {str(e)}", steps)
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
        msg = "Cookies expired. Please tell admin to update."
        log_activation_detail(mobile, email, clean_code, False, msg, ["No cookies stored for this profile."])
        return {"success": False, "error_code": "COOKIES_EXPIRED", "message": msg, "formatted_output": msg}

    last_error = None
    try:
        res = await run_activation_attempt(email=email, clean_code=clean_code, cookies=cookies, mobile=mobile)
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
    except Exception as e:
        last_error = str(e)

    msg = f"Automation error: {last_error}"
    return {"success": False, "error_code": "EXECUTION_ERROR", "message": msg, "formatted_output": msg}
