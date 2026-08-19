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

            # Wait for either code input or login field
            try:
                await page.wait_for_selector(
                    "input[name='rendezvousCode'], input[autocomplete='one-time-code'], input[name='userLoginId']", 
                    state="visible", 
                    timeout=15000
                )
            except Exception:
                pass

            await page.wait_for_timeout(1500)

            # Pre-check: Expired session / Login redirect
            current_url = page.url
            if "login" in current_url or await page.locator("input[name='userLoginId']").count() > 0:
                await browser.close()
                return {
                    "success": False,
                    "error_code": "COOKIES_EXPIRED",
                    "message": "cookies expired please tell admin to update"
                }

            # 2. Locate exact input field from DOM
            code_input = page.locator("input[name='rendezvousCode'], input[autocomplete='one-time-code'], input[data-hcw-form-control-element='true']").first

            if await code_input.count() == 0:
                await browser.close()
                return {
                    "success": False,
                    "error_code": "INPUT_NOT_FOUND",
                    "message": "Could not locate code input fields on netflix.com/tv2."
                }

            # 3. Fill code and trigger React synthetic events
            await code_input.click()
            await code_input.fill("")
            await code_input.fill(clean_code)
            
            # Ensure React state recognizes the value change
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

            await page.wait_for_timeout(800)

            # 4. Click Continue button
            continue_btn = page.locator("button:has-text('Continue'), button:has-text('continue'), button[type='submit']").first
            if await continue_btn.count() > 0 and await continue_btn.is_visible():
                await continue_btn.click()
            else:
                await page.keyboard.press("Enter")

            # 5. Wait and verify actual outcome
            await page.wait_for_timeout(4000)

            # Check for error validation messages on screen
            error_locators = page.locator("[data-hcw-form-control-validation], [data-uia*='error'], .ui-message-error, .ui-message-contents")
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

            # Check if input field is still present (meaning form submission failed or didn't proceed)
            if await code_input.is_visible():
                # Check again after a short delay in case of network latency
                await page.wait_for_timeout(2500)
                if await code_input.is_visible():
                    await browser.close()
                    return {
                        "success": False,
                        "error_code": "ACTIVATION_FAILED",
                        "message": "Activation did not complete. Please verify the code on your TV."
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
