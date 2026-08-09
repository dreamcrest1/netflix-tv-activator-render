import os
import json
from fastapi import FastAPI, Form, HTTPException, Request, Depends, Body
from fastapi.responses import HTMLResponse, JSONResponse

from sheet_manager import fetch_and_validate_user, DEFAULT_SHEET_URL
from profile_manager import (
    get_all_profiles, add_or_update_profile, delete_profile,
    get_profile_cookies, parse_cookies, export_profiles_b64
)
from data_manager import (
    get_settings, update_settings, log_activation,
    check_activation_limit, get_activation_stats, export_full_state_b64,
    record_pageview, toggle_block_number, get_blocked_numbers
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
<body class="text-white min-h-screen flex flex-col justify-between p-3 md:p-6 relative pb-20">

    <header class="max-w-4xl mx-auto w-full flex justify-between items-center glass-card rounded-2xl p-4 mb-5 shadow-2xl">
        <div class="flex items-center gap-3">
            <div class="bg-nred text-white font-extrabold text-2xl w-10 h-10 rounded-xl flex items-center justify-center shadow-lg shadow-red-900/50">
                N
            </div>
            <div>
                <h1 class="text-lg md:text-xl font-bold tracking-tight text-white flex items-center gap-2">
                    NETFLIX TV CODE ACTIVATOR 
                    <span class="bg-red-950 text-nred text-xs px-2 py-0.5 rounded-md border border-red-900/50 font-mono">v2.0 PRO</span>
                </h1>
                <p class="text-xs text-zinc-400">Automatic TV Activation & Subscription Verification</p>
            </div>
        </div>
        <a href="/admin" class="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white px-3 py-2 rounded-xl text-xs md:text-sm font-semibold transition border border-zinc-700 flex items-center gap-2">
            <i class="fa-solid fa-gauge-high text-nred"></i>
            <span>Admin Portal</span>
        </a>
    </header>

    <main class="max-w-4xl mx-auto w-full space-y-5">

        <div class="bg-gradient-to-r from-red-700 via-red-600 to-red-800 rounded-2xl p-4 md:p-5 shadow-2xl flex flex-col md:flex-row justify-between items-center gap-4 border border-red-500/40">
            <div class="flex items-center gap-3">
                <div class="bg-black px-3 py-1.5 rounded-lg flex items-center justify-center shadow-md">
                    <span class="text-nred font-extrabold text-lg tracking-wider">NETFLIX</span>
                </div>
                <div>
                    <div class="text-[10px] md:text-xs font-bold uppercase tracking-widest text-red-100">PREMIUM STREAMING ACCESS</div>
                    <div class="text-sm md:text-base font-extrabold text-white">Buy Netflix 4K UHD for all devices</div>
                </div>
            </div>
            <a href="https://wa.me/916357998730?text=Hi%2C%20I%20want%20to%20buy%20Netflix%204K%20UHD%20subscription" target="_blank"
               class="bg-white text-red-600 hover:bg-zinc-100 font-bold px-5 py-2.5 rounded-full text-xs md:text-sm transition flex items-center gap-2 shadow-lg hover:scale-105 transform">
                <i class="fa-brands fa-whatsapp text-green-500 text-base"></i>
                <span>Chat now <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i></span>
            </a>
        </div>

        <div class="glass-card bg-gradient-to-r from-zinc-900 via-zinc-900 to-zinc-950 border border-zinc-800 rounded-2xl p-4 md:p-5 shadow-2xl flex flex-col md:flex-row justify-between items-center gap-4">
            <div class="flex items-center gap-3">
                <div class="bg-zinc-800 border border-zinc-700 text-amber-400 w-10 h-10 rounded-xl flex items-center justify-center text-lg shadow-inner">
                    <i class="fa-solid fa-house-laptop"></i>
                </div>
                <div>
                    <div class="text-xs font-bold text-amber-400 flex items-center gap-1.5 uppercase tracking-wider">
                        <span>Need Travel / Household Code?</span>
                    </div>
                    <div class="text-xs md:text-sm text-zinc-300 font-medium">Get your travel or household code directly from the code fetcher portal.</div>
                </div>
            </div>
            <a href="https://netflix-code-fetcher-5q.vercel.app/" target="_blank"
               class="bg-amber-500 hover:bg-amber-600 text-black font-bold px-5 py-2.5 rounded-xl text-xs md:text-sm transition flex items-center gap-2 shadow-lg hover:scale-105 transform">
                <i class="fa-solid fa-key"></i>
                <span>Open Code Fetcher <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i></span>
            </a>
        </div>

        <div id="globalStatus" class="hidden rounded-xl p-4 text-sm font-semibold flex items-center gap-3 border transition-all"></div>

        <div class="glass-card rounded-2xl p-5 md:p-6 space-y-4 shadow-2xl">
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

        <div id="activationSection" class="glass-card rounded-2xl p-5 md:p-6 space-y-4 shadow-2xl opacity-50 pointer-events-none transition-all">
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

        <div class="glass-card rounded-2xl p-5 md:p-6 space-y-3 shadow-2xl">
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

        <div id="outputContainer" class="hidden glass-card rounded-2xl p-5 md:p-6 space-y-3 shadow-2xl border-emerald-900/50">
            <div class="flex justify-between items-center">
                <h3 class="text-xs font-bold uppercase text-emerald-400 flex items-center gap-2">
                    <i class="fa-solid fa-circle-check"></i>
                    Formatted Activation Output
                </h3>
            </div>
            <textarea id="outputText" readonly rows="8" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3.5 text-xs text-zinc-200 font-mono focus:outline-none resize-none"></textarea>
            <button onclick="copyOutput()" id="btnCopy" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl transition flex items-center justify-center gap-2 text-sm">
                <i class="fa-solid fa-copy"></i>
                <span>📋 Copy Output to Clipboard</span>
            </button>
        </div>
    </main>

    <a href="https://wa.me/916357998730?text=Hi%2C%20I%20need%20help%20with%20Netflix%20TV%20Activation" target="_blank"
       class="fixed bottom-5 right-5 bg-emerald-500 hover:bg-emerald-600 text-white font-bold px-4 py-3 rounded-full shadow-2xl flex items-center gap-2.5 z-40 transition transform hover:scale-105 border border-emerald-300/30">
        <i class="fa-brands fa-whatsapp text-2xl"></i>
        <span class="text-xs md:text-sm font-semibold">WhatsApp Support</span>
    </a>

    <script>
        let verifiedMobile = null;
        let assignedEmail = null;

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

        async function fetchWithTimeout(resource, options = {}) {
            const { timeout = 50000 } = options;
            const controller = new AbortController();
            const id = setTimeout(() => controller.abort(), timeout);
            try {
                const response = await fetch(resource, { ...options, signal: controller.signal });
                clearTimeout(id);
                return response;
            } catch (err) {
                clearTimeout(id);
                throw err;
            }
        }

        async function handleVerifyMobile(e) {
            e.preventDefault();
            const mobile = document.getElementById('mobileInput').value.trim();
            const btn = document.getElementById('btnVerifyMobile');

            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Checking Subscription & Limits...`;
            logConsole(`Verifying subscription for mobile: ${mobile}...`);

            try {
                const res = await fetchWithTimeout('/api/check-user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mobile }),
                    timeout: 20000
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
                const errMsg = err.name === 'AbortError' ? 'Verification request timed out.' : 'Error connecting to verification server.';
                showGlobalStatus('error', errMsg);
                logConsole(`Server error: ${errMsg}`, 'ERROR');
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
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Validating cookies & connecting to Netflix...`;
            logConsole(`Validating cookies & initiating TV activation for ${assignedEmail} with code ${code}...`);

            try {
                const res = await fetchWithTimeout('/api/activate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mobile: verifiedMobile, code }),
                    timeout: 50000
                });
                const data = await res.json();

                if (data.formatted_output) {
                    document.getElementById('outputContainer').classList.remove('hidden');
                    document.getElementById('outputText').value = data.formatted_output;
                }

                if (data.success) {
                    showGlobalStatus('success', '🎉 Netflix TV Code Activated Successfully!');
                    logConsole(`Activation successful for ${assignedEmail}!`, 'SUCCESS');
                } else {
                    const errText = data.message || 'Activation failed.';
                    showGlobalStatus('error', errText);
                    logConsole(`Activation failed: ${errText}`, 'ERROR');
                }
            } catch (err) {
                const errMsg = err.name === 'AbortError' ? 'Browser activation timed out. Please retry.' : 'Server error running browser activation.';
                showGlobalStatus('error', errMsg);
                logConsole(`Execution exception: ${errMsg}`, 'ERROR');
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
    </script>
</body>
</html>
"""

ADMIN_HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Netflix Activator PRO - Admin Control Center</title>
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
                    }
                }
            }
        }
    </script>
    <style>
        body { font-family: 'Segoe UI', Roboto, sans-serif; background-color: #0A0A0A; }
        .glass-card { background: #141414; border: 1px solid #252525; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0A0A0A; }
        ::-webkit-scrollbar-thumb { background: #252525; border-radius: 4px; }
    </style>
</head>
<body class="text-white min-h-screen p-4 md:p-8">

    <div class="max-w-6xl mx-auto space-y-6">

        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 glass-card p-5 rounded-2xl shadow-2xl">
            <div class="flex items-center gap-3">
                <div class="bg-nred text-white w-10 h-10 rounded-xl flex items-center justify-center font-black text-xl shadow-lg shadow-red-900/50">
                    N
                </div>
                <div>
                    <h1 class="text-xl font-extrabold flex items-center gap-2">
                        ADMIN CONTROL CENTER
                        <span class="text-xs bg-red-950 text-nred border border-red-900 px-2 py-0.5 rounded font-mono">PRO</span>
                    </h1>
                    <p class="text-xs text-zinc-400">Full System Metrics, User Blacklist, Cookies & Activation Logs</p>
                </div>
            </div>
            <a href="/" class="bg-zinc-800 hover:bg-zinc-700 text-zinc-200 px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2">
                <i class="fa-solid fa-arrow-left"></i> Back to Main Site
            </a>
        </div>

        <div id="adminLoginForm" class="glass-card max-w-md mx-auto p-6 rounded-2xl space-y-4 shadow-2xl my-12">
            <h2 class="text-base font-bold text-center text-white flex items-center justify-center gap-2">
                <i class="fa-solid fa-lock text-nred"></i> Unlock Admin Portal
            </h2>
            <input type="password" id="adminPassword" placeholder="Enter Admin Password"
                   class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-white focus:outline-none focus:border-nred text-sm">
            <button onclick="loginAdmin()" class="w-full bg-nred hover:bg-nredhover text-white font-bold py-3 rounded-xl text-sm transition">
                Unlock Admin Dashboard
            </button>
        </div>

        <div id="adminDashboard" class="hidden space-y-6">

            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div class="glass-card p-4 rounded-xl">
                    <div class="text-[11px] font-bold text-zinc-400 uppercase">Website Pageviews</div>
                    <div id="statPageviews" class="text-2xl font-bold font-mono text-blue-400 mt-1">0</div>
                </div>
                <div class="glass-card p-4 rounded-xl">
                    <div class="text-[11px] font-bold text-zinc-400 uppercase">Unique Visitors</div>
                    <div id="statVisitors" class="text-2xl font-bold font-mono text-purple-400 mt-1">0</div>
                </div>
                <div class="glass-card p-4 rounded-xl">
                    <div class="text-[11px] font-bold text-zinc-400 uppercase">Successful Activations</div>
                    <div id="statSuccess" class="text-2xl font-bold font-mono text-emerald-400 mt-1">0</div>
                </div>
                <div class="glass-card p-4 rounded-xl">
                    <div class="text-[11px] font-bold text-zinc-400 uppercase">Blocked Numbers</div>
                    <div id="statBlocked" class="text-2xl font-bold font-mono text-red-500 mt-1">0</div>
                </div>
            </div>

            <div class="glass-card p-5 rounded-2xl space-y-3">
                <h3 class="text-xs font-bold text-amber-400 uppercase flex items-center gap-2">
                    <i class="fa-solid fa-gauge-high"></i> User Activation Limits Control
                </h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs text-zinc-400 mb-1">Max Monthly Activations per User (0 = Unlimited)</label>
                        <input type="number" id="limitMonthly" min="0" value="3"
                               class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-xs text-white focus:outline-none">
                    </div>
                    <div>
                        <label class="block text-xs text-zinc-400 mb-1">Max Lifetime Activations per User (0 = Unlimited)</label>
                        <input type="number" id="limitTotal" min="0" value="0"
                               class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 text-xs text-white focus:outline-none">
                    </div>
                </div>
                <button onclick="saveLimitsConfig()" class="bg-amber-500 hover:bg-amber-600 text-black font-bold px-4 py-2 rounded-xl text-xs transition">
                    Save Limits Configuration
                </button>
            </div>

            <div class="glass-card p-5 rounded-2xl space-y-3">
                <h3 class="text-xs font-bold text-red-500 uppercase flex items-center gap-2">
                    <i class="fa-solid fa-user-slash"></i> User Blacklist / Number Blocking Tool
                </h3>
                <div class="flex gap-2">
                    <input type="tel" id="blockMobileInput" placeholder="Enter 10-digit mobile number to block" maxlength="10"
                           class="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none font-mono">
                    <button onclick="blockMobileAction()" class="bg-red-600 hover:bg-red-700 text-white font-bold px-4 py-2 rounded-xl text-xs transition">
                        Block Number
                    </button>
                </div>
            </div>

            <div class="glass-card p-5 rounded-2xl space-y-4">
                <div class="flex justify-between items-center">
                    <h3 class="text-xs font-bold text-zinc-300 uppercase">Netflix Profiles & Session Cookies</h3>
                    <button onclick="loadAdminProfiles()" class="text-xs text-nred hover:underline">Refresh Profiles</button>
                </div>
                <div class="flex gap-2">
                    <input type="email" id="newProfileEmail" placeholder="user@netflix.com"
                           class="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none font-mono">
                    <button onclick="addNewProfile()" class="bg-nred hover:bg-nredhover text-white font-bold px-4 py-2 rounded-xl text-xs transition">
                        Add Profile
                    </button>
                </div>
                <div id="profilesList" class="space-y-2 max-h-48 overflow-y-auto pr-1"></div>
            </div>

            <div id="cookieEditorBox" class="hidden glass-card p-5 rounded-2xl space-y-3 border-blue-900/50">
                <div class="flex justify-between items-center">
                    <h4 class="text-xs font-bold text-zinc-300 uppercase">Edit Cookies for: <span id="targetEmailDisplay" class="text-nred"></span></h4>
                    <button onclick="closeCookieEditor()" class="text-xs text-zinc-500 hover:text-white">Cancel</button>
                </div>
                <textarea id="cookiesJsonInput" rows="6" placeholder='Paste JSON cookies array or raw cookie string...'
                          class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-xs font-mono text-zinc-200 focus:outline-none"></textarea>
                <button onclick="saveCookiesForProfile()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2.5 rounded-xl text-xs transition">
                    Save Cookies
                </button>
            </div>

            <div class="glass-card p-5 rounded-2xl space-y-3">
                <h3 class="text-xs font-bold text-zinc-300 uppercase flex items-center gap-2">
                    <i class="fa-solid fa-users"></i> Per-User Statistics & Management
                </h3>
                <div class="max-h-60 overflow-y-auto">
                    <table class="w-full text-left text-xs text-zinc-300 border-collapse">
                        <thead>
                            <tr class="border-b border-zinc-800 text-zinc-500">
                                <th class="py-2">Mobile Number</th>
                                <th class="py-2">Monthly Activations</th>
                                <th class="py-2">Total Activations</th>
                                <th class="py-2">Status</th>
                                <th class="py-2">Last Active</th>
                                <th class="py-2">Action</th>
                            </tr>
                        </thead>
                        <tbody id="userStatsTbody">
                            <tr><td colspan="6" class="py-2 text-zinc-500 italic">No user data yet.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="glass-card p-5 rounded-2xl space-y-3">
                <div class="flex justify-between items-center">
                    <h3 class="text-xs font-bold text-zinc-300 uppercase flex items-center gap-2">
                        <i class="fa-solid fa-list-check"></i> Audit Activation Trail Logs
                    </h3>
                    <input type="text" id="logSearchInput" onkeyup="filterAuditLogs()" placeholder="Search mobile or email..."
                           class="bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1 text-[11px] text-white focus:outline-none w-48 font-mono">
                </div>
                <div class="max-h-64 overflow-y-auto">
                    <table class="w-full text-left text-xs text-zinc-300 border-collapse">
                        <thead>
                            <tr class="border-b border-zinc-800 text-zinc-500">
                                <th class="py-2">Timestamp</th>
                                <th class="py-2">Mobile</th>
                                <th class="py-2">Profile Email</th>
                                <th class="py-2">TV Code</th>
                                <th class="py-2">Status</th>
                            </tr>
                        </thead>
                        <tbody id="auditLogsTbody">
                            <tr><td colspan="5" class="py-2 text-zinc-500 italic">No logs recorded yet.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="glass-card p-5 rounded-2xl space-y-2 border-blue-900/40">
                <h3 class="text-xs font-bold text-zinc-300 uppercase">Server Restart Persistence Backup</h3>
                <p class="text-[11px] text-zinc-400">Copy this backup string and add it as an Environment Variable named <code class="text-amber-400 bg-zinc-950 px-1 py-0.5 rounded font-mono">PROFILES_JSON_DATA</code> in Render settings. That way, all settings, logs, blocked numbers, and cookies will NEVER reset when Render restarts!</p>
                <button onclick="copyEnvBackup()" id="btnEnvBackup" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2.5 rounded-xl text-xs transition">
                    📋 Copy Persistent ENV Backup String
                </button>
            </div>

        </div>

    </div>

    <script>
        let adminTokenPassword = "";
        let currentTargetProfile = "";
        let rawLogsData = [];

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
                loadAdminStats();
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
                    div.className = 'flex justify-between items-center bg-zinc-950 p-3 rounded-xl border border-zinc-800 text-xs';
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

        async function loadAdminStats() {
            const res = await fetch(`/api/admin/stats?password=${encodeURIComponent(adminTokenPassword)}`);
            const data = await res.json();

            if (data) {
                document.getElementById('statPageviews').innerText = data.pageviews || 0;
                document.getElementById('statVisitors').innerText = data.unique_visitors || 0;
                document.getElementById('statSuccess').innerText = data.successful_logs || 0;
                document.getElementById('statBlocked').innerText = data.blocked_count || 0;

                if (data.settings) {
                    document.getElementById('limitMonthly').value = data.settings.max_monthly_activations ?? 3;
                    document.getElementById('limitTotal').value = data.settings.max_total_activations ?? 0;
                }

                const userTbody = document.getElementById('userStatsTbody');
                userTbody.innerHTML = '';
                if (data.user_stats && data.user_stats.length > 0) {
                    data.user_stats.forEach(u => {
                        const tr = document.createElement('tr');
                        tr.className = 'border-b border-zinc-800/50';
                        tr.innerHTML = `
                            <td class="py-2 font-mono font-bold text-white">${u.mobile}</td>
                            <td class="py-2 font-mono text-amber-400">${u.monthly}</td>
                            <td class="py-2 font-mono text-emerald-400">${u.total}</td>
                            <td class="py-2 font-mono">
                                <span class="px-2 py-0.5 rounded text-[10px] ${u.is_blocked ? 'bg-red-950 text-red-400 border border-red-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800'}">
                                    ${u.is_blocked ? 'BLOCKED' : 'ACTIVE'}
                                </span>
                            </td>
                            <td class="py-2 font-mono text-zinc-400">${u.last_active}</td>
                            <td class="py-2">
                                <button onclick="toggleBlockUser('${u.mobile}', ${!u.is_blocked})" class="px-2 py-1 text-[10px] rounded font-bold ${u.is_blocked ? 'bg-emerald-700 hover:bg-emerald-600 text-white' : 'bg-red-900 hover:bg-red-800 text-white'}">
                                    ${u.is_blocked ? 'Unblock' : 'Block'}
                                </button>
                            </td>
                        `;
                        userTbody.appendChild(tr);
                    });
                } else {
                    userTbody.innerHTML = `<tr><td colspan="6" class="py-2 text-zinc-500 italic">No user data yet.</td></tr>`;
                }

                rawLogsData = data.recent_logs || [];
                renderAuditLogs(rawLogsData);
            }
        }

        function renderAuditLogs(logs) {
            const auditTbody = document.getElementById('auditLogsTbody');
            auditTbody.innerHTML = '';
            if (logs && logs.length > 0) {
                logs.forEach(l => {
                    const tr = document.createElement('tr');
                    tr.className = 'border-b border-zinc-800/50 text-[11px]';
                    tr.innerHTML = `
                        <td class="py-2 font-mono text-zinc-400">${l.timestamp}</td>
                        <td class="py-2 font-mono font-bold text-white">${l.mobile}</td>
                        <td class="py-2 font-mono text-zinc-300">${l.email}</td>
                        <td class="py-2 font-mono text-amber-300">${l.code}</td>
                        <td class="py-2 font-mono">
                            <span class="px-2 py-0.5 rounded-full text-[10px] ${l.success ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-red-950 text-red-400 border border-red-800'}">
                                ${l.success ? 'SUCCESS' : 'FAILED'}
                            </span>
                        </td>
                    `;
                    auditTbody.appendChild(tr);
                });
            } else {
                auditTbody.innerHTML = `<tr><td colspan="5" class="py-2 text-zinc-500 italic">No logs recorded yet.</td></tr>`;
            }
        }

        function filterAuditLogs() {
            const query = document.getElementById('logSearchInput').value.toLowerCase().trim();
            if (!query) {
                renderAuditLogs(rawLogsData);
                return;
            }
            const filtered = rawLogsData.filter(l => l.mobile.toLowerCase().includes(query) || l.email.toLowerCase().includes(query));
            renderAuditLogs(filtered);
        }

        async function toggleBlockUser(mobile, block) {
            await fetch('/api/admin/block-number', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: adminTokenPassword, mobile, block })
            });
            loadAdminStats();
        }

        async function blockMobileAction() {
            const mob = document.getElementById('blockMobileInput').value.trim();
            if (!mob) return;
            await toggleBlockUser(mob, true);
            document.getElementById('blockMobileInput').value = '';
        }

        async function saveLimitsConfig() {
            const monthly = parseInt(document.getElementById('limitMonthly').value) || 0;
            const total = parseInt(document.getElementById('limitTotal').value) || 0;

            const res = await fetch('/api/admin/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    password: adminTokenPassword,
                    settings: {
                        max_monthly_activations: monthly,
                        max_total_activations: total
                    }
                })
            });
            const data = await res.json();
            if (data.success) {
                alert('Limits configuration saved successfully!');
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

        async function copyEnvBackup() {
            const res = await fetch('/api/admin/export-env', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: adminTokenPassword })
            });
            const data = await res.json();
            if (data.b64_str) {
                navigator.clipboard.writeText(data.b64_str);
                const btn = document.getElementById('btnEnvBackup');
                btn.innerText = "✓ Backup String Copied to Clipboard!";
                btn.className = "w-full bg-emerald-600 text-white font-bold py-2.5 rounded-xl text-xs";
                setTimeout(() => {
                    btn.innerText = "📋 Copy Persistent ENV Backup String";
                    btn.className = "w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2.5 rounded-xl text-xs";
                }, 3000);
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    record_pageview(client_ip)
    return HTML_CONTENT

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin_page(request: Request):
    return ADMIN_HTML_CONTENT

@app.post("/api/check-user")
async def api_check_user(data: dict = Body(...)):
    mobile = data.get("mobile", "")
    sheet_url = data.get("sheet_url", DEFAULT_SHEET_URL)
    
    allowed, limit_msg = check_activation_limit(mobile)
    if not allowed:
        return {"valid": False, "error_code": "LIMIT_OR_BLOCKED", "message": limit_msg}

    res = fetch_and_validate_user(mobile_number=mobile, custom_sheet_url=sheet_url)
    return res

@app.post("/api/activate")
async def api_activate(data: dict = Body(...)):
    mobile = data.get("mobile", "")
    code = data.get("code", "")
    sheet_url = data.get("sheet_url", DEFAULT_SHEET_URL)

    allowed, limit_msg = check_activation_limit(mobile)
    if not allowed:
        log_activation(mobile=mobile, email="Unknown", code=code, success=False, message=limit_msg)
        return {"success": False, "error_code": "LIMIT_OR_BLOCKED", "message": limit_msg}

    validation = fetch_and_validate_user(mobile_number=mobile, custom_sheet_url=sheet_url)
    if not validation.get("valid"):
        log_activation(mobile=mobile, email="Unknown", code=code, success=False, message=validation.get("message"))
        return validation

    assigned_email = validation.get("assigned_email")
    expiry_date = validation.get("expiry_date", "")

    res = await activate_tv(email=assigned_email, raw_code=code, mobile=mobile, expiry_date=expiry_date)
    
    log_activation(
        mobile=mobile,
        email=assigned_email,
        code=code,
        success=res.get("success", False),
        message=res.get("message", "")
    )
    
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

@app.get("/api/admin/stats")
async def admin_get_stats(password: str):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return get_activation_stats()

@app.post("/api/admin/block-number")
async def admin_block_number(data: dict = Body(...)):
    if data.get("password") != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    mobile = data.get("mobile", "")
    block = data.get("block", True)
    blocked_list = toggle_block_number(mobile, block)
    return {"success": True, "blocked_numbers": blocked_list}

@app.post("/api/admin/settings")
async def admin_update_settings(data: dict = Body(...)):
    if data.get("password") != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    new_s = update_settings(data.get("settings", {}))
    return {"success": True, "settings": new_s}

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

@app.post("/api/admin/export-env")
async def admin_export_env(data: dict = Body(...)):
    if data.get("password") != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    b64_str = export_full_state_b64()
    return {"b64_str": b64_str}

@app.post("/api/admin/sheet-test")
async def admin_sheet_test(data: dict = Body(...)):
    if data.get("password") != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    import requests, csv, io
    sheet_url = DEFAULT_SHEET_URL
    try:
        r = requests.get(sheet_url, timeout=10)
        reader = list(csv.DictReader(io.StringIO(r.text)))
        return {
            "status": "connected",
            "columns": list(reader[0].keys()) if reader else [],
            "row_count": len(reader),
            "sample_first_row": reader[0] if reader else {}
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
