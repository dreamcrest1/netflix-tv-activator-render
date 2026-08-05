import re
import asyncio
from playwright.async_api import async_playwright
from profile_manager import get_profile_cookies

async def activate_tv(email: str, raw_code: str):
    clean_code = re.sub(r'[^a-zA-Z0-9]', '', raw_code).upper()
    if len(clean_code) != 8:
        return {
            "success": False,
            "error_code": "INVALID_CODE_FORMAT",
            "message": f"TV Activation code must be exactly 8 characters. Received: {raw_code}"
        }

    cookies = get_profile_cookies(email)
    if not cookies or len(cookies) == 0:
        return {
            "success": False,
            "error_code": "NO_COOKIES_FOUND",
            "message": f"No active Netflix cookies found for profile '{email}'. Please upload cookies in Admin Panel."
        }

    async with async_playwright() as p:
        browser = None
        try:
            # Optimized Chromium parameters for Render micro-container limits
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
                    "--single-process"
                ]
            )

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

            await page.goto("https://www.netflix.com/tv2", wait_until="domcontentloaded", timeout=35000)
            await page.wait_for_timeout(2000)

            current_url = page.url
            if "login" in current_url or await page.locator("input[name='userLoginId']").count() > 0:
                await browser.close()
                return {
                    "success": False,
                    "error_code": "NOT_LOGGED_IN",
                    "message": f"Account '{email}' session cookies expired. Admin needs to re-upload cookies in Admin Panel."
                }

            inputs = page.locator("input[type='text'], input[type='number'], input[type='tel'], input[data-uia*='code'], input[data-uia*='pin']")
            input_count = await inputs.count()

            if input_count == 0:
                inputs = page.locator("input")
                input_count = await inputs.count()

            if input_count == 0:
                await browser.close()
                return {
                    "success": False,
                    "error_code": "INPUT_NOT_FOUND",
                    "message": "Could not locate code input fields on netflix.com/tv2."
                }

            if input_count >= 8:
                for i in range(min(8, input_count)):
                    inp = inputs.nth(i)
                    await inp.focus()
                    await inp.fill("")
                    await inp.type(clean_code[i], delay=100)
            else:
                main_input = inputs.first
                await main_input.focus()
                try:
                    await main_input.fill("")
                except Exception:
                    pass
                for char in clean_code:
                    await page.keyboard.type(char, delay=120)

            await page.wait_for_timeout(1000)

            submit_btn = page.locator("button[type='submit'], button[data-uia*='submit'], button[data-uia*='continue'], button[data-uia*='activate']")
            if await submit_btn.count() > 0 and await submit_btn.first.is_visible():
                await submit_btn.first.click()
            else:
                await page.keyboard.press("Enter")

            await page.wait_for_timeout(4000)

            page_content = (await page.content()).lower()
            error_keywords = ["invalid code", "code expired", "incorrect code", "try again", "unable to connect"]
            has_error = any(err in page_content for err in error_keywords)

            if has_error:
                error_elem = page.locator("[data-uia*='error'], .ui-message-error, .ui-message-contents")
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

            formatted_output = (
                "📺 *1. If TV asks for a code (household / travelling code issue)\n"
                "*GO TO https://netflix-code-fetcher-5q.vercel.app/\n"
                "SELECT YOUR EMAIL\n"
                f"Email : {email}\n"
                "CLICK FETCH AND UPDATE CODE"
            )

            return {
                "success": True,
                "email": email,
                "code": clean_code,
                "message": "netflix activated",
                "formatted_output": formatted_output
            }

        except Exception as e:
            if browser:
                await browser.close()
            return {
                "success": False,
                "error_code": "EXECUTION_ERROR",
                "message": f"Automation exception: {str(e)}"
            }