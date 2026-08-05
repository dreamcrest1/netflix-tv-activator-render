import os
import json
from fastapi import FastAPI, Form, HTTPException, Request, Depends, Body
from fastapi.responses import HTMLResponse, JSONResponse

from sheet_manager import fetch_and_validate_user, DEFAULT_SHEET_URL
from profile_manager import (
    get_all_profiles, add_or_update_profile, delete_profile,
    get_profile_cookies, parse_cookies
)
from activation_engine import activate_tv

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Logical8794")

app = FastAPI(title="Netflix TV Code Activator PRO Web")

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Netflix TV Code Activator PRO</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        nred: '#E50914',
                        nredhover: '#B20710',
                        darkcard: '#141414',
                        darkborder: '#252525',
                        accentgreen: '#00C853',
                        accentgreenhover: '#009624',
                    }
                }
            }
        }
    </script>
    <style>
        body { font-family: 'Segoe UI', Roboto, sans-serif; background-color: #0A0A0A; }
        .glass-card { background: #141414; border: 1px solid #252525; }
        .console-box { background-color: #080808; font-family: 'Consolas', 'Courier New', monospace; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0A0A0A; }
        ::-webkit-scrollbar-thumb { background: #252525; border-radius: 4px; }
    </style>
</head>
<body class="text-white min-h-screen flex flex-col justify-between p-3 md:p-6">

    <header class="max-w-4xl mx-auto w-full flex justify-between items-center glass-card rounded-2xl p-4 mb-6 shadow-xl">
        <div class="flex items-center gap-3">
            <div class="bg-nred text-white font-extrabold text-2xl w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-red-900/50">
                N
            </div>
            <div>
                <h1 class="text-lg md:text-xl font-bold tracking-tight text-white flex items-center gap-2">
                    NETFLIX TV CODE ACTIVATOR 
                    <span class="bg-red-950 text-nred text-xs px-2 py-0.5 rounded-md border border-red-900/50 font-mono">v2.0 PRO</span>
                </h1>
                <p class="text-xs text-zinc-400">Automatic TV Session Activation & Sheet Subscription Verification</p>
            </div>
        </div>
        <button onclick="openAdminModal()" class="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white px-3 py-2 rounded-xl text-xs md:text-sm font-semibold transition border border-zinc-700 flex items-center gap-2">
            <i class="fa-solid fa-lock text-nred"></i>
            <span>Admin Panel</span>
        </button>
    </header>

    <main class="max-w-4xl mx-auto w-full space-y-5">
        <div id="globalStatus" class="hidden rounded-xl p-4 text-sm font-semibold flex items-center gap-3 border transition-all"></div>

        <div class="glass-card rounded-2xl p-5 md:p-6 space-y-4 shadow-xl">
            <div class="flex justify-between items-center border-b border-zinc-800/80 pb-3">
                <h2 class="text-sm md:text-base font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-mobile-screen text-nred"></i>
                    STEP 1: VERIFY MOBILE SUBSCRIPTION
                </h2>
                <span id="step1Badge" class="text-xs px-2.5 py-1 rounded-full bg-zinc-800 text-zinc-400 font-mono">Pending Auth</span>
            </div>

            <form id="mobileForm" onsubmit="handleVerifyMobile(event)" class="space-y-4">
                <div>
                    <label class="block text-xs font-semibold text-zinc-400 uppercase mb-2">10-Digit Mobile Number</label>
                    <div class="relative">
                        <i class="fa-solid fa-phone absolute left-4 top-3.5 text-zinc-500"></i>
                        <input type="tel" id="mobileInput" placeholder="Enter 10-digit mobile number" maxlength="10" required
                               class="w-full bg-zinc-950 border border-zinc-800 rounded-xl py-3 pl-11 pr-4 text-white text-lg font-mono tracking-wider focus:outline-none focus:border-nred transition">
                    </div>
                </div>

                <button type="submit" id="btnVerifyMobile" class="w-full bg-nred hover:bg-nredhover text-white font-bold py-3.5 rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-red-900/30">
                    <i class="fa-solid fa-shield-halved"></i>
                    <span>Verify Plan & Fetch Profile</span>
                </button>
            </form>

            <div id="userInfoCard" class="hidden bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 space-y-2">
                <div class="flex justify-between items-center text-xs">
                    <span class="text-zinc-400">Assigned Netflix Profile:</span>
                    <span id="infoEmail" class="text-emerald-400 font-mono font-bold text-sm">--</span>
                </div>
                <div class="flex justify-between items-center text-xs">
                    <span class="text-zinc-400">Subscription Status / Expiry:</span>
                    <span id="infoExpiry" class="text-zinc-200 font-mono">--</span>
                </div>
            </div>
        </div>

        <div id="activationSection" class="glass-card rounded-2xl p-5 md:p-6 space-y-4 shadow-xl opacity-50 pointer-events-none transition-all">
            <div class="flex justify-between items-center border-b border-zinc-800/80 pb-3">
                <h2 class="text-sm md:text-base font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-tv text-emerald-400"></i>
                    STEP 2: ENTER 8-DIGIT TV CODE
                </h2>
                <span class="text-xs text-zinc-400 font-mono">netflix.com/tv2</span>
            </div>

            <form id="activateForm" onsubmit="handleActivate(event)" class="space-y-4">
                <div>
                    <label class="block text-xs font-semibold text-zinc-400 uppercase mb-2">8-Digit TV Activation Code</label>
                    <input type="text" id="tvCodeInput" placeholder="1 2 3 4 5 6 7 8" maxlength="8" required
                           class="w-full bg-zinc-950 border border-zinc-800 rounded-xl py-3.5 px-4 text-center text-2xl font-mono tracking-widest text-white uppercase focus:outline-none focus:border-accentgreen transition">
                </div>

                <button type="submit" id="btnActivate" class="w-full bg-accentgreen hover:bg-accentgreenhover text-white font-bold py-4 rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-green-900/30 text-base">
                    <i class="fa-solid fa-bolt"></i>
                    <span>⚡ ACTIVATE NETFLIX TV NOW</span>
                </button>
            </form>
        </div>

        <div class="glass-card rounded-2xl p-5 md:p-6 space-y-3 shadow-xl">
            <div class="flex justify-between items-center">
                <h3 class="text-xs font-bold uppercase text-zinc-400 flex items-center gap-2">
                    <i class="fa-solid fa-terminal text-zinc-500"></i>
                    Live Activity Log
                </h3>
                <button onclick="clearConsole()" class="text-xs text-zinc-500 hover:text-zinc-300">Clear</button>
            </div>
            <div id="consoleLog" class="console-box text-emerald-400 text-xs p-3.5 rounded-xl h-28 overflow-y-auto space-y-1">
                <div>[SYSTEM] System ready. Enter 10-digit mobile number to verify subscription.</div>
            </div>
        </div>

        <div id="outputContainer" class="hidden glass-card rounded-2xl p-5 md:p-6 space-y-3 shadow-xl border-emerald-900/50">
            <div class="flex justify-between items-center">
                <h3 class="text-xs font-bold uppercase text-emerald-400 flex items-center gap-2">
                    <i class="fa-solid fa-circle-check"></i>
                    Formatted Activation Output
                </h3>
            </div>
            <textarea id="outputText" readonly rows="5" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3.5 text-xs text-zinc-200 font-mono focus:outline-none resize-none"></textarea>
            <button onclick="copyOutput()" id="btnCopy" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl transition flex items-center justify-center gap-2 text-sm">
                <i class="fa-solid fa-copy"></i>
                <span>📋 Copy Output to Clipboard</span>
            </button>
        </div>
    </main>

    <div id="adminModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
        <div class="glass-card rounded-2xl max-w-2xl w-full p-6 space-y-5 border-zinc-700 max-h-[90vh] overflow-y-auto">
            <div class="flex justify-between items-center border-b border-zinc-800 pb-3">
                <h3 class="text-lg font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-user-shield text-nred"></i>
                    Admin Management Panel
                </h3>
                <button onclick="closeAdminModal()" class="text-zinc-400 hover:text-white text-xl">&times;</button>
            </div>

            <div id="adminLoginForm" class="space-y-4">
                <p class="text-xs text-zinc-400">Enter admin access password to unlock profile & cookie management.</p>
                <div>
                    <input type="password" id="adminPassword" placeholder="Admin Password"
                           class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-white focus:outline-none focus:border-nred text-sm">
                </div>
                <button onclick="loginAdmin()" class="w-full bg-nred hover:bg-nredhover text-white font-bold py-3 rounded-xl text-sm">
                    Unlock Admin Dashboard
                </button>
            </div>

            <div id="adminDashboard" class="hidden space-y-5">
                <div class="bg-zinc-950 border border-zinc-800 p-4 rounded-xl space-y-3">
                    <h4 class="text-xs font-bold text-zinc-300 uppercase">Add / Update Profile Email</h4>
                    <div class="flex gap-2">
                        <input type="email" id="newProfileEmail" placeholder="user@netflix.com"
                               class="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none">
                        <button onclick="addNewProfile()" class="bg-nred text-white font-bold px-4 py-2 rounded-xl text-xs hover:bg-nredhover">
                            Add Profile
                        </button>
                    </div>
                </div>

                <div class="space-y-2">
                    <div class="flex justify-between items-center">
                        <h4 class="text-xs font-bold text-zinc-300 uppercase">Saved Profiles & Cookies</h4>
                        <button onclick="loadAdminProfiles()" class="text-xs text-nred hover:underline">Refresh List</button>
                    </div>
                    <div id="profilesList" class="space-y-2 max-h-60 overflow-y-auto pr-1"></div>
                </div>

                <div id="cookieEditorBox" class="hidden bg-zinc-950 border border-zinc-800 p-4 rounded-xl space-y-3">
                    <div class="flex justify-between items-center">
                        <h4 class="text-xs font-bold text-zinc-300 uppercase">Edit Cookies for: <span id="targetEmailDisplay" class="text-nred"></span></h4>
                        <button onclick="closeCookieEditor()" class="text-xs text-zinc-500 hover:text-white">Cancel</button>
                    </div>
                    <textarea id="cookiesJsonInput" rows="6" placeholder='Paste JSON cookies array or raw cookie string...'
                              class="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-3 text-xs font-mono text-zinc-200 focus:outline-none"></textarea>
                    <button onclick="saveCookiesForProfile()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2.5 rounded-xl text-xs">
                        Save Cookies
                    </button>
                </div>

                <div class="bg-zinc-950 border border-zinc-800 p-4 rounded-xl space-y-2">
                    <h4 class="text-xs font-bold text-zinc-300 uppercase">Google Sheet Sync Test</h4>
                    <button onclick="testSheetConnection()" class="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-bold py-2 rounded-xl text-xs">
                        Fetch & Verify Google Sheet Connection
                    </button>
                    <div id="sheetTestResult" class="text-xs font-mono text-zinc-400 hidden"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let verifiedMobile = null;
        let assignedEmail = null;
        let adminTokenPassword = "";
        let currentTargetProfile = "";

        function logConsole(msg, level="INFO") {
            const time = new Date().toLocaleTimeString();
            const logBox = document.getElementById('consoleLog');
            const line = document.createElement('div');
            line.innerHTML = `<span class="text-zinc-500">[${time}]</span> <span class="${level === 'ERROR' ? 'text-red-400' : level === 'SUCCESS' ? 'text-emerald-400' : 'text-zinc-300'}">[${level}] ${msg}</span>`;
            logBox.appendChild(line);
            logBox.scrollTop = logBox.scrollHeight;
        }

        function clearConsole() {
            document.getElementById('consoleLog').innerHTML = '';
        }

        function showGlobalStatus(type, msg) {
            const banner = document.getElementById('globalStatus');
            banner.classList.remove('hidden', 'bg-red-950', 'border-red-800', 'text-red-300', 'bg-emerald-950', 'border-emerald-800', 'text-emerald-300');
            if (type === 'error') {
                banner.classList.add('bg-red-950', 'border-red-800', 'text-red-300');
                banner.innerHTML = `<i class="fa-solid fa-circle-exclamation text-red-400 text-lg"></i> <span>${msg}</span>`;
            } else {
                banner.classList.add('bg-emerald-950', 'border-emerald-800', 'text-emerald-300');
                banner.innerHTML = `<i class="fa-solid fa-circle-check text-emerald-400 text-lg"></i> <span>${msg}</span>`;
            }
        }

        async function handleVerifyMobile(e) {
            e.preventDefault();
            const mobile = document.getElementById('mobileInput').value.trim();
            const btn = document.getElementById('btnVerifyMobile');

            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Checking Google Sheet...`;
            logConsole(`Verifying subscription for mobile: ${mobile}...`);

            try {
                const res = await fetch('/api/check-user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mobile })
                });
                const data = await res.json();

                if (data.valid) {
                    verifiedMobile = data.mobile;
                    assignedEmail = data.assigned_email;

                    document.getElementById('userInfoCard').classList.remove('hidden');
                    document.getElementById('infoEmail').innerText = assignedEmail;
                    document.getElementById('infoExpiry').innerText = data.expiry_date || 'Active';

                    document.getElementById('step1Badge').innerText = 'Verified ✓';
                    document.getElementById('step1Badge').className = 'text-xs px-2.5 py-1 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono';

                    const step2 = document.getElementById('activationSection');
                    step2.classList.remove('opacity-50', 'pointer-events-none');

                    showGlobalStatus('success', `Mobile verified! Assigned Profile: ${assignedEmail}`);
                    logConsole(`Subscription verified for ${assignedEmail}. Expiry: ${data.expiry_date}`, 'SUCCESS');
                } else {
                    showGlobalStatus('error', data.message);
                    logConsole(`Verification failed: ${data.message}`, 'ERROR');
                }
            } catch (err) {
                showGlobalStatus('error', 'Error connecting to verification server.');
                logConsole(`Server error: ${err.message}`, 'ERROR');
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<i class="fa-solid fa-shield-halved"></i> <span>Verify Plan & Fetch Profile</span>`;
            }
        }

        async function handleActivate(e) {
            e.preventDefault();
            const code = document.getElementById('tvCodeInput').value.trim();
            const btn = document.getElementById('btnActivate');

            if (!verifiedMobile || !assignedEmail) {
                showGlobalStatus('error', 'Please verify your mobile number first.');
                return;
            }

            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Connecting Playwright to Netflix...`;
            logConsole(`Initiating TV activation for ${assignedEmail} with code ${code}...`);

            try {
                const res = await fetch('/api/activate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mobile: verifiedMobile, code })
                });
                const data = await res.json();

                if (data.success) {
                    showGlobalStatus('success', '🎉 Netflix TV Code Activated Successfully!');
                    logConsole(`Activation successful for ${assignedEmail}!`, 'SUCCESS');

                    document.getElementById('outputContainer').classList.remove('hidden');
                    document.getElementById('outputText').value = data.formatted_output;
                } else {
                    showGlobalStatus('error', data.message || 'Activation failed.');
                    logConsole(`Activation failed: ${data.message}`, 'ERROR');
                }
            } catch (err) {
                showGlobalStatus('error', 'Server error running browser activation.');
                logConsole(`Execution exception: ${err.message}`, 'ERROR');
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<i class="fa-solid fa-bolt"></i> <span>⚡ ACTIVATE NETFLIX TV NOW</span>`;
            }
        }

        function copyOutput() {
            const txt = document.getElementById('outputText');
            txt.select();
            document.execCommand('copy');
            const btn = document.getElementById('btnCopy');
            btn.innerHTML = `<i class="fa-solid fa-check"></i> <span>Copied to Clipboard! ✓</span>`;
            btn.className = 'w-full bg-emerald-600 text-white font-bold py-3 rounded-xl transition flex items-center justify-center gap-2 text-sm';
            setTimeout(() => {
                btn.innerHTML = `<i class="fa-solid fa-copy"></i> <span>📋 Copy Output to Clipboard</span>`;
                btn.className = 'w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl transition flex items-center justify-center gap-2 text-sm';
            }, 2000);
        }

        function openAdminModal() {
            document.getElementById('adminModal').classList.remove('hidden');
        }

        function closeAdminModal() {
            document.getElementById('adminModal').classList.add('hidden');
        }

        async function loginAdmin() {
            const pwd = document.getElementById('adminPassword').value;
            const res = await fetch('/api/admin/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: pwd })
            });
            const data = await res.json();

            if (data.success) {
                adminTokenPassword = pwd;
                document.getElementById('adminLoginForm').classList.add('hidden');
                document.getElementById('adminDashboard').classList.remove('hidden');
                loadAdminProfiles();
            } else {
                alert('Invalid Admin Password!');
            }
        }

        async function loadAdminProfiles() {
            const res = await fetch(`/api/admin/profiles?password=${encodeURIComponent(adminTokenPassword)}`);
            const data = await res.json();
            const list = document.getElementById('profilesList');
            list.innerHTML = '';

            if (data.profiles && data.profiles.length > 0) {
                data.profiles.forEach(p => {
                    const div = document.createElement('div');
                    div.className = 'flex justify-between items-center bg-zinc-900 p-3 rounded-xl border border-zinc-800 text-xs';
                    div.innerHTML = `
                        <div>
                            <span class="font-bold text-white font-mono">${p.email}</span>
                            <div class="text-zinc-500 text-[10px]">${p.has_cookies ? '✓ ' + p.cookie_count + ' cookies stored' : '⚠ No cookies uploaded'}</div>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="openCookieEditor('${p.email}')" class="bg-blue-600 hover:bg-blue-700 text-white px-2.5 py-1 rounded-lg">Cookies</button>
                            <button onclick="deleteProfile('${p.email}')" class="bg-red-950 text-red-400 hover:bg-red-900 px-2 py-1 rounded-lg">&times;</button>
                        </div>
                    `;
                    list.appendChild(div);
                });
            } else {
                list.innerHTML = `<div class="text-xs text-zinc-500 italic p-2">No profiles saved yet.</div>`;
            }
        }

        async function addNewProfile() {
            const email = document.getElementById('newProfileEmail').value.trim();
            if (!email) return;

            await fetch('/api/admin/profiles/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: adminTokenPassword, email })
            });
            document.getElementById('newProfileEmail').value = '';
            loadAdminProfiles();
        }

        async function deleteProfile(email) {
            if (!confirm(`Delete profile ${email}?`)) return;
            await fetch('/api/admin/profiles/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: adminTokenPassword, email })
            });
            loadAdminProfiles();
        }

        function openCookieEditor(email) {
            currentTargetProfile = email;
            document.getElementById('targetEmailDisplay').innerText = email;
            document.getElementById('cookieEditorBox').classList.remove('hidden');
        }

        function closeCookieEditor() {
            document.getElementById('cookieEditorBox').classList.add('hidden');
        }

        async function saveCookiesForProfile() {
            const cookiesRaw = document.getElementById('cookiesJsonInput').value;
            const res = await fetch('/api/admin/profiles/cookies', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    password: adminTokenPassword,
                    email: currentTargetProfile,
                    cookies: cookiesRaw
                })
            });
            const data = await res.json();
            if (data.success) {
                alert(`Cookies saved for ${currentTargetProfile}!`);
                closeCookieEditor();
                document.getElementById('cookiesJsonInput').value = '';
                loadAdminProfiles();
            } else {
                alert(`Error saving cookies: ${data.message}`);
            }
        }

        async function testSheetConnection() {
            const resBox = document.getElementById('sheetTestResult');
            resBox.classList.remove('hidden');
            resBox.innerText = "Connecting to Google Sheet...";
            
            const res = await fetch('/api/admin/sheet-test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: adminTokenPassword })
            });
            const data = await res.json();
            resBox.innerText = JSON.stringify(data, null, 2);
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    return HTML_CONTENT

@app.post("/api/check-user")
async def api_check_user(data: dict = Body(...)):
    mobile = data.get("mobile", "")
    sheet_url = data.get("sheet_url", DEFAULT_SHEET_URL)
    res = fetch_and_validate_user(mobile_number=mobile, custom_sheet_url=sheet_url)
    return res

@app.post("/api/activate")
async def api_activate(data: dict = Body(...)):
    mobile = data.get("mobile", "")
    code = data.get("code", "")
    sheet_url = data.get("sheet_url", DEFAULT_SHEET_URL)

    validation = fetch_and_validate_user(mobile_number=mobile, custom_sheet_url=sheet_url)
    if not validation.get("valid"):
        return validation

    assigned_email = validation.get("assigned_email")
    res = await activate_tv(email=assigned_email, raw_code=code)
    return res

@app.post("/api/admin/login")
async def admin_login(data: dict = Body(...)):
    pwd = data.get("password", "")
    if pwd == ADMIN_PASSWORD:
        return {"success": True}
    return JSONResponse({"success": False, "message": "Invalid Password"}, status_code=401)

@app.get("/api/admin/profiles")
async def admin_list_profiles(password: str):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    profiles = get_all_profiles()
    return {"profiles": profiles}

@app.post("/api/admin/profiles/add")
async def admin_add_profile(data: dict = Body(...)):
    if data.get("password") != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    add_or_update_profile(email=data.get("email", ""))
    return {"success": True}

@app.post("/api/admin/profiles/delete")
async def admin_delete_profile(data: dict = Body(...)):
    if data.get("password") != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    delete_profile(email=data.get("email", ""))
    return {"success": True}

@app.post("/api/admin/profiles/cookies")
async def admin_update_cookies(data: dict = Body(...)):
    if data.get("password") != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    email = data.get("email", "")
    cookies_raw = data.get("cookies")
    add_or_update_profile(email=email, cookies_raw=cookies_raw)
    return {"success": True}

@app.post("/api/admin/sheet-test")
async def admin_sheet_test(data: dict = Body(...)):
    if data.get("password") != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    import requests, pandas as pd, io
    sheet_url = DEFAULT_SHEET_URL
    try:
        r = requests.get(sheet_url, timeout=10)
        df = pd.read_csv(io.StringIO(r.text))
        return {
            "status": "connected",
            "columns": df.columns.tolist(),
            "row_count": len(df),
            "sample_first_row": df.iloc[0].to_dict() if not df.empty else {}
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)