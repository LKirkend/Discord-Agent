"""
File: status_ui.py
Description:
    Renders the HTML status dashboard page for the Discord Liaison Bot.
Author: Logan Kirkendall <Logan@LKAud.io>
"""

import os
import time
from fastapi.responses import HTMLResponse
import state

def discover_agent_sessions(*args, **kwargs):
    """
    Description:
        Wrapper delegating to bot.discover_agent_sessions.
    Usage:
        sessions = discover_agent_sessions()
    Usage Example:
        sessions = discover_agent_sessions()
    """
    import bot
    return bot.discover_agent_sessions(*args, **kwargs)

async def get_status_ui():
    """
    Description:
        FastAPI endpoint to render the main HTML Status Page.
    Usage:
        res = await get_status_ui()
    Usage Example:
        res = await get_status_ui()
    """
    uptime_seconds = int(time.time() - state.START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    
    try:
        sessions = discover_agent_sessions()
        active_sessions = len(sessions)
    except Exception:
        active_sessions = "Error"
        
    bot_name = "AGY2 Liaison Bot"
    import bot
    DISCORD_BOT_TOKEN = bot.DISCORD_BOT_TOKEN
    DISCORD_USER_ID = bot.DISCORD_USER_ID
    DISCORD_USER_NAME = os.getenv("DISCORD_USER_NAME", "Tig1")
    DISCORD_BOT_PERMISSIONS = getattr(state, "DISCORD_BOT_PERMISSIONS", "8471182706732241")
    
    bot_permissions = 0
    if state.bot and state.bot.is_ready():
        for guild in state.bot.guilds:
            if guild.me:
                bot_permissions = max(bot_permissions, guild.me.guild_permissions.value)
                
    if not DISCORD_BOT_TOKEN:
        status_label = "Config Warning"
        status_color = "#f59e0b"
        status_rgb = "245, 158, 11"
    elif state.bot and state.bot.is_ready():
        status_label = "Active"
        status_color = "#10b981"
        status_rgb = "16, 185, 129"
    else:
        if uptime_seconds < 30:
            status_label = "Connecting"
            status_color = "#f59e0b"
            status_rgb = "245, 158, 11"
        else:
            status_label = "Disconnected"
            status_color = "#ef4444"
            status_rgb = "239, 68, 68"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Antigravity Liaison Bot Status</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-color: #0b0f19;
                --card-bg: rgba(17, 24, 39, 0.7);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-main: #f3f4f6;
                --text-muted: #9ca3af;
                --primary: #6366f1; /* Indigo */
                --success: #10b981; /* Emerald */
                --warning: #f59e0b; /* Amber */
                --danger: #ef4444; /* Rose */
                --pulse-rgb: {status_rgb};
            }}
            body {{
                font-family: 'Inter', sans-serif;
                background-color: var(--bg-color);
                color: var(--text-main);
                margin: 0;
                padding: 24px;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 90vh;
            }}
            .container {{
                width: 100%;
                max-width: 480px;
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 20px;
                backdrop-filter: blur(16px);
                padding: 32px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                animation: fadeIn 0.8s ease-out;
            }}
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            .header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 24px;
                border-bottom: 1px solid var(--card-border);
                padding-bottom: 16px;
            }}
            .title {{
                font-size: 20px;
                font-weight: 600;
                color: var(--text-main);
                margin: 0;
            }}
            .status-badge-container {{
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .status-badge {{
                display: flex;
                align-items: center;
                gap: 8px;
                background: rgba({status_rgb}, 0.05);
                border: 1px solid rgba({status_rgb}, 0.1);
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 500;
                color: {status_color};
            }}
            .dot {{
                width: 8px;
                height: 8px;
                background-color: {status_color};
                border-radius: 50%;
                display: inline-block;
                box-shadow: 0 0 8px {status_color};
                animation: pulse 2s infinite;
            }}
            @keyframes pulse {{
                0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(var(--pulse-rgb), 0.7); }}
                70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(var(--pulse-rgb), 0); }}
                100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(var(--pulse-rgb), 0); }}
            }}
            .metric-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 16px;
                margin-bottom: 24px;
            }}
            .metric-card {{
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid var(--card-border);
                border-radius: 12px;
                padding: 16px;
                transition: all 0.3s ease;
            }}
            .metric-card:hover {{
                background: rgba(255, 255, 255, 0.05);
                border-color: var(--primary);
                transform: translateY(-2px);
            }}
            .metric-label {{
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--text-muted);
                margin-bottom: 4px;
            }}
            .metric-value {{
                font-size: 16px;
                font-weight: 600;
                color: var(--text-main);
            }}
            .info-list {{
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}
            .info-item {{
                display: flex;
                justify-content: space-between;
                font-size: 13px;
                padding: 10px 14px;
                background: rgba(255, 255, 255, 0.01);
                border: 1px solid var(--card-border);
                border-radius: 10px;
            }}
            .info-key {{
                color: var(--text-muted);
            }}
            .info-val {{
                font-weight: 500;
                color: var(--text-main);
            }}
            .pause-btn {{
                width: 100%;
                background: var(--primary);
                border: none;
                border-radius: 12px;
                color: white;
                padding: 12px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-top: 24px;
                box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
            }}
            .pause-btn:hover {{
                background: #4f46e5;
                transform: translateY(-1px);
            }}
            .pause-btn.paused {{
                background: var(--warning);
                box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
            }}
            .pause-btn.paused:hover {{
                background: #d97706;
            }}
            .footer {{
                margin-top: 24px;
                text-align: center;
                font-size: 11px;
                color: var(--text-muted);
            }}
            /* Toggle Switch */
            .switch {{
                position: relative;
                display: inline-block;
                width: 40px;
                height: 20px;
            }}
            .switch input {{
                opacity: 0;
                width: 0;
                height: 0;
            }}
            .slider {{
                position: absolute;
                cursor: pointer;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: rgba(255,255,255,0.1);
                transition: .3s;
                border-radius: 20px;
                border: 1px solid var(--card-border);
            }}
            .slider:before {{
                position: absolute;
                content: "";
                height: 12px;
                width: 12px;
                left: 3px;
                bottom: 3px;
                background-color: var(--text-main);
                transition: .3s;
                border-radius: 50%;
            }}
            input:checked + .slider {{
                background-color: var(--success);
            }}
            input:checked + .slider:before {{
                transform: translateX(20px);
            }}
            .provider-select-btn {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid var(--card-border);
                color: var(--text-muted);
                padding: 6px 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 12px;
                font-weight: 500;
                transition: all 0.2s;
            }}
            .provider-select-btn.active {{
                background: var(--primary);
                color: white;
                border-color: var(--primary);
                box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
            }}
            /* Modal Overlay */
            .modal-overlay {{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(4px);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s ease;
            }}
            .modal-overlay.show {{
                opacity: 1;
                pointer-events: auto;
            }}
            .modal-content {{
                background: #111827;
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 24px;
                width: 320px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
                text-align: left;
                transform: scale(0.95);
                transition: transform 0.2s ease;
            }}
            .modal-overlay.show .modal-content {{
                transform: scale(1);
            }}
            /* Toast notification */
            .toast {{
                position: fixed;
                bottom: 24px;
                right: 24px;
                background: var(--success);
                color: white;
                padding: 12px 20px;
                border-radius: 10px;
                box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
                font-size: 13px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
                z-index: 1001;
                opacity: 0;
                transform: translateY(20px);
                transition: all 0.3s ease;
                pointer-events: none;
            }}
            .toast.show {{
                opacity: 1;
                transform: translateY(0);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 class="title">🤖 Discord Liaison</h1>
                <div class="status-badge-container">
                    <div class="status-badge" id="status-badge">
                        <span class="dot" id="status-dot"></span>
                        <span id="status-text">{status_label}</span>
                    </div>
                    <div class="status-badge" id="paused-badge" style="display: {'flex' if state.IS_PAUSED else 'none'}; background: rgba(245, 158, 11, 0.05); border: 1px solid rgba(245, 158, 11, 0.1); color: #f59e0b; gap: 8px;">
                        <span class="dot" style="background-color: #f59e0b; box-shadow: 0 0 8px #f59e0b;"></span>
                        <span>Paused</span>
                    </div>
                </div>
            </div>
            
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-label">Port</div>
                    <div class="metric-value">{state.PORT}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Process ID</div>
                    <div class="metric-value">{os.getpid()}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Liaison Bot</div>
                    <div class="metric-value">{bot_name}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Uptime</div>
                    <div class="metric-value" id="uptime-val">{uptime_str}</div>
                </div>
                
                <!-- Model Switcher Card -->
                <div class="metric-card" style="grid-column: span 2;">
                    <div class="metric-label" style="margin-bottom: 12px; font-weight: 600;">LLM Provider Setup</div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span class="info-key" style="font-size: 13px;">Provider</span>
                        <div style="display: flex; gap: 8px;">
                            <button id="btn-gemini" class="provider-select-btn">Gemini</button>
                            <button id="btn-ollama" class="provider-select-btn">Ollama (Local)</button>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="info-key" style="font-size: 13px;">Auto-switch to local upon quota depletion</span>
                        <label class="switch">
                            <input type="checkbox" id="chk-auto-switch">
                            <span class="slider"></span>
                        </label>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 12px;">
                        <span class="info-key" style="font-size: 13px;">Force server-only chat (bypass DMs)</span>
                        <label class="switch">
                            <input type="checkbox" id="chk-force-server">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
            </div>
            
            <div class="info-list">
                <div class="info-item">
                    <span class="info-key">Registered User</span>
                    <span class="info-val" id="user-val">{DISCORD_USER_NAME} (ID: {DISCORD_USER_ID or "N/A"})</span>
                </div>
                <div class="info-item">
                    <span class="info-key">Active Sessions</span>
                    <span class="info-val" id="sessions-val">{active_sessions}</span>
                </div>
                <div class="info-item">
                    <span class="info-key">Active Permissions</span>
                    <span class="info-val" id="permissions-val">{bot_permissions}</span>
                </div>
                <div class="info-item" style="align-items: center; justify-content: space-between; display: flex;">
                    <span class="info-key">Invite Permissions</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <input type="text" id="txt-permissions" value="{DISCORD_BOT_PERMISSIONS}" style="background: rgba(255,255,255,0.05); border: 1px solid var(--card-border); border-radius: 6px; color: var(--text-main); font-size: 13px; padding: 4px 8px; width: 140px; text-align: right; outline: none; font-family: monospace;" />
                        <button id="btn-save-permissions" style="background: var(--primary); border: none; border-radius: 6px; color: white; padding: 4px 10px; font-size: 12px; font-weight: 600; cursor: pointer; transition: background 0.2s;">Save</button>
                    </div>
                </div>
                <div class="info-item">
                    <span class="info-key">System Integrations</span>
                    <span class="info-val">FastAPI + Discord.py</span>
                </div>
            </div>
            
            <button id="toggle-pause-btn" class="pause-btn {'paused' if state.IS_PAUSED else ''}">
                {"Resume Liaison" if state.IS_PAUSED else "Pause Liaison"}
            </button>
            
            <div class="footer">
                Antigravity Platform Extension | Real-Time Updates
            </div>
        </div>

        <!-- Confirmation Modal -->
        <div id="confirm-modal" class="modal-overlay">
            <div class="modal-content">
                <h3 style="margin-top: 0; margin-bottom: 12px; font-size: 16px; font-weight: 600; color: var(--text-main);">Save Changes?</h3>
                <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 20px; line-height: 1.5;">Are you sure you want to update the bot permissions integer to <span id="new-perms-display" style="font-weight: 600; color: var(--primary);"></span>?</p>
                <div style="display: flex; justify-content: flex-end; gap: 10px;">
                    <button id="btn-confirm-cancel" style="background: rgba(255,255,255,0.05); border: 1px solid var(--card-border); border-radius: 8px; color: var(--text-main); padding: 8px 16px; font-size: 13px; cursor: pointer; font-weight: 500;">Cancel</button>
                    <button id="btn-confirm-save" style="background: var(--primary); border: none; border-radius: 8px; color: white; padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer;">Confirm</button>
                </div>
            </div>
        </div>

        <!-- Success Toast -->
        <div id="success-toast" class="toast">
            <span>💾</span>
            <span>Settings saved successfully!</span>
        </div>

        <script>
            let currentProvider = "";
            let currentAutoSwitch = false;
            let currentForceServerChat = false;
            let currentPermissions = "{DISCORD_BOT_PERMISSIONS}";
            const txtPerms = document.getElementById('txt-permissions');

            async function updateStatus() {{
                try {{
                    const response = await fetch('/api/status');
                    if (!response.ok) return;
                    const data = await response.json();
                    
                    document.getElementById('uptime-val').textContent = data.uptime;
                    document.getElementById('sessions-val').textContent = data.active_sessions;
                    document.getElementById('user-val').textContent = data.discord_user;
                    document.getElementById('permissions-val').textContent = data.bot_permissions;
                    
                    if (document.activeElement !== txtPerms) {{
                        txtPerms.value = data.discord_bot_permissions;
                        currentPermissions = data.discord_bot_permissions;
                    }}
                    
                    const badge = document.getElementById('status-badge');
                    const badgeText = document.getElementById('status-text');
                    const dot = document.getElementById('status-dot');
                    
                    badgeText.textContent = data.status_label;
                    badgeText.style.color = data.status_color;
                    badge.style.background = `rgba(${{data.status_rgb}}, 0.05)`;
                    badge.style.borderColor = `rgba(${{data.status_rgb}}, 0.1)`;
                    badge.style.color = data.status_color;
                    
                    dot.style.backgroundColor = data.status_color;
                    dot.style.boxShadow = `0 0 8px ${{data.status_color}}`;
                    
                    updatePauseUI(data.paused);
                    updateSettingsUI(data.model_provider, data.auto_switch_local, data.force_server_chat === 1);
                    
                    document.documentElement.style.setProperty('--pulse-rgb', data.status_rgb);
                }} catch (e) {{
                    console.error("Failed to fetch status:", e);
                }}
            }}
            
            function updatePauseUI(isPaused) {{
                const pausedBadge = document.getElementById('paused-badge');
                const toggleBtn = document.getElementById('toggle-pause-btn');
                if (isPaused) {{
                    pausedBadge.style.display = 'flex';
                    toggleBtn.textContent = 'Resume Liaison';
                    toggleBtn.classList.add('paused');
                }} else {{
                    pausedBadge.style.display = 'none';
                    toggleBtn.textContent = 'Pause Liaison';
                    toggleBtn.classList.remove('paused');
                }}
            }}

            function updateSettingsUI(provider, autoSwitch, forceServer) {{
                currentProvider = provider;
                currentAutoSwitch = autoSwitch;
                currentForceServerChat = forceServer;
                
                const btnGemini = document.getElementById('btn-gemini');
                const btnOllama = document.getElementById('btn-ollama');
                const chkAutoSwitch = document.getElementById('chk-auto-switch');
                const chkForceServer = document.getElementById('chk-force-server');
                
                if (provider === "gemini") {{
                    btnGemini.classList.add('active');
                    btnOllama.classList.remove('active');
                }} else {{
                    btnGemini.classList.remove('active');
                    btnOllama.classList.add('active');
                }}
                
                chkAutoSwitch.checked = autoSwitch;
                chkForceServer.checked = forceServer;
            }}

            async function saveSettings(provider, autoSwitch, forceServer) {{
                try {{
                    const res = await fetch('/api/settings', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ 
                            model_provider: provider, 
                            auto_switch_local: autoSwitch,
                            discord_bot_permissions: currentPermissions,
                            force_server_chat: forceServer ? 1 : 0,
                            force_only_server: forceServer ? 1 : 0
                        }})
                    }});
                    if (res.ok) {{
                        const data = await res.json();
                        updateSettingsUI(data.model_provider, data.auto_switch_local, data.force_server_chat === 1);
                    }}
                }} catch (e) {{
                    console.error("Failed to save settings:", e);
                }}
            }}
            
            document.getElementById('btn-gemini').addEventListener('click', () => saveSettings('gemini', currentAutoSwitch, currentForceServerChat));
            document.getElementById('btn-ollama').addEventListener('click', () => saveSettings('ollama', currentAutoSwitch, currentForceServerChat));
            document.getElementById('chk-auto-switch').addEventListener('change', (e) => saveSettings(currentProvider, e.target.checked, currentForceServerChat));
            document.getElementById('chk-force-server').addEventListener('change', (e) => saveSettings(currentProvider, currentAutoSwitch, e.target.checked));

            const savePermsBtn = document.getElementById('btn-save-permissions');
            const confirmModal = document.getElementById('confirm-modal');
            const newPermsDisplay = document.getElementById('new-perms-display');
            const confirmCancelBtn = document.getElementById('btn-confirm-cancel');
            const confirmSaveBtn = document.getElementById('btn-confirm-save');
            const successToast = document.getElementById('success-toast');

            let pendingPermissions = "";

            savePermsBtn.addEventListener('click', () => {{
                pendingPermissions = txtPerms.value.trim();
                if (!pendingPermissions) return;
                newPermsDisplay.textContent = pendingPermissions;
                confirmModal.classList.add('show');
            }});

            confirmCancelBtn.addEventListener('click', () => {{
                confirmModal.classList.remove('show');
            }});

            confirmSaveBtn.addEventListener('click', async () => {{
                confirmModal.classList.remove('show');
                try {{
                    const res = await fetch('/api/settings', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ 
                            model_provider: currentProvider, 
                            auto_switch_local: currentAutoSwitch,
                            discord_bot_permissions: pendingPermissions,
                            force_server_chat: currentForceServerChat ? 1 : 0,
                            force_only_server: currentForceServerChat ? 1 : 0
                        }})
                    }});
                    if (res.ok) {{
                        const data = await res.json();
                        currentPermissions = data.discord_bot_permissions;
                        txtPerms.value = currentPermissions;
                        
                        // Show success toast
                        successToast.classList.add('show');
                        setTimeout(() => {{
                            successToast.classList.remove('show');
                        }}, 3000);
                    }}
                }} catch (e) {{
                    console.error("Failed to save permissions settings:", e);
                }}
            }});
            
            const toggleBtn = document.getElementById('toggle-pause-btn');
            toggleBtn.addEventListener('click', async () => {{
                try {{
                    const res = await fetch('/api/toggle-pause', {{ method: 'POST' }});
                    if (res.ok) {{
                        const data = await res.json();
                        updatePauseUI(data.paused);
                    }}
                }} catch (e) {{
                    console.error("Failed to toggle pause:", e);
                }}
            }});
            
            setInterval(updateStatus, 2000);
            updateStatus();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
