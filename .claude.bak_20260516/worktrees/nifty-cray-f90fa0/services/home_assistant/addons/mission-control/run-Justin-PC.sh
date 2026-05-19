#!/usr/bin/env sh
set -eu

echo "=== Mission Control Home Assistant Add-on ==="

mkdir -p /data

if [ -e /app/data ] && [ ! -L /app/data ]; then
  rm -rf /app/data
fi

if [ ! -e /app/data ]; then
  ln -s /data /app/data
fi

python3 - <<'PY'
import json
import os
import re
from pathlib import Path

data_dir = Path("/data")
options_path = data_dir / "options.json"
config_path = data_dir / "config.json"
asset_version = "ha-addon-20260418k"

options = {}
if options_path.exists():
    options = json.loads(options_path.read_text(encoding="utf-8"))

config = {}
if config_path.exists():
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        config = {}

mapping = {
    "ha_url": "HA_URL",
    "ha_token": "HA_TOKEN",
    "gemini_api_key": "GEMINI_API_KEY",
    "server_url": "SERVER_URL",
}

for key, env_name in mapping.items():
    value = options.get(key)
    if value not in (None, ""):
        config[key] = value

    persisted_value = config.get(key)
    if persisted_value not in (None, ""):
        os.environ[env_name] = persisted_value

config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

print("Persisted add-on options into /data/config.json")
for key in mapping:
    print(f"  {key}: {'set' if config.get(key) else 'unset'}")

template_path = Path("/app/templates/index.html")
if template_path.exists():
    template_text = template_path.read_text(encoding="utf-8")
    patched_template = template_text.replace(
        'href="/static/css/style.css"',
        f'href="static/css/style.css?v={asset_version}"',
    ).replace(
        '<script src="/static/js/app.js"></script>',
        f'<script src="static/js/app.js?v={asset_version}"></script>',
    ).replace(
        '<div class="btn-row">\n                <button class="btn btn-secondary" id="btn-skip">Skip Round</button>\n                <button class="btn btn-danger" id="btn-stop">Stop Game</button>\n            </div>',
        '<div class="btn-row">\n                <button class="btn btn-secondary" id="btn-needs-help">Try Again</button>\n                <button class="btn btn-approve" id="btn-admin-success">Success!</button>\n                <button class="btn btn-secondary" id="btn-skip">Skip Round</button>\n                <button class="btn btn-danger" id="btn-stop">Stop Game</button>\n            </div>',
    )
    if patched_template != template_text:
        template_path.write_text(patched_template, encoding="utf-8")
        print("Patched index.html for ingress-relative static assets")

js_path = Path("/app/static/js/app.js")
if js_path.exists():
    js_text = js_path.read_text(encoding="utf-8")
    original_js = js_text

    helper = """// Mission Control - WebSocket Client & UI Logic

const MC_BASE_PATH = (() => {
    const path = window.location.pathname || '/';
    if (!path || path === '/') return '/';
    return path.endsWith('/') ? path : `${path}/`;
})();

function mcUrl(path = '') {
    if (!path) return MC_BASE_PATH;
    if (/^[a-z]+:/i.test(path) || path.startsWith('//')) return path;
    const clean = path.startsWith('/') ? path.slice(1) : path;
    return `${MC_BASE_PATH}${clean}`;
}

function mcResolveAssetUrl(url) {
    if (!url) return url;
    if (/^[a-z]+:/i.test(url) || url.startsWith('//') || url.startsWith('data:') || url.startsWith('blob:')) {
        return url;
    }
    if (url.startsWith('/')) return mcUrl(url);
    return url;
}

const MC_PARENT_CONFIRM_TIMEOUT_MS = 5000;

function mcClearTemporaryConfirm(button) {
    if (!button) return;
    if (button.dataset.mcConfirmTimer) {
        window.clearTimeout(Number(button.dataset.mcConfirmTimer));
    }
    button.dataset.mcConfirmArmed = 'false';
    delete button.dataset.mcConfirmTimer;
    if (button.dataset.mcIdleLabel) {
        button.textContent = button.dataset.mcIdleLabel;
    }
}

function mcRequireSecondTap(button, confirmLabel, idleLabel) {
    if (!button) return true;
    if (button.dataset.mcConfirmArmed === 'true') {
        mcClearTemporaryConfirm(button);
        return true;
    }
    button.dataset.mcIdleLabel = idleLabel || button.textContent.trim() || 'Success!';
    button.dataset.mcConfirmArmed = 'true';
    button.textContent = confirmLabel;
    const timer = window.setTimeout(() => mcClearTemporaryConfirm(button), MC_PARENT_CONFIRM_TIMEOUT_MS);
    button.dataset.mcConfirmTimer = String(timer);
    return false;
}

function mcShowToast(message, durationMs = 2200) {
    if (!message) return;
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.setAttribute('role', 'status');
    toast.style.position = 'fixed';
    toast.style.right = '20px';
    toast.style.bottom = '20px';
    toast.style.zIndex = '9999';
    toast.style.padding = '10px 14px';
    toast.style.borderRadius = '999px';
    toast.style.background = 'rgba(15, 23, 42, 0.92)';
    toast.style.color = '#fff';
    toast.style.fontSize = '14px';
    toast.style.fontWeight = '600';
    toast.style.boxShadow = '0 12px 30px rgba(0, 0, 0, 0.28)';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'opacity 150ms ease, transform 150ms ease';
    document.body.appendChild(toast);
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    });
    window.setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        window.setTimeout(() => toast.remove(), 180);
    }, durationMs);
}

function mcBindById(id, eventName, handler, options) {
    const element = document.getElementById(id);
    if (!element) {
        console.warn(`Mission Control: missing element #${id} for ${eventName}`);
        return false;
    }
    element.addEventListener(eventName, handler, options);
    return true;
}

async function mcReadErrorMessage(resp, fallback = 'Request failed') {
    const statusSuffix = resp && resp.status ? ` (HTTP ${resp.status})` : '';
    let body = '';
    try {
        body = await resp.text();
    } catch (err) {
        return `${fallback}${statusSuffix}`;
    }

    const contentType = resp.headers?.get?.('content-type') || '';
    if (body && contentType.includes('application/json')) {
        try {
            const data = JSON.parse(body);
            return data.error || data.message || `${fallback}${statusSuffix}`;
        } catch (err) {
            // Fall through to plain-text handling.
        }
    }

    if (!body) {
        return `${fallback}${statusSuffix}`;
    }
    if (/<!doctype|<html/i.test(body)) {
        return `${fallback}${statusSuffix}`;
    }

    const compact = body.replace(/\s+/g, ' ').trim();
    return compact ? compact.slice(0, 240) : `${fallback}${statusSuffix}`;
}

function mcInstallFallbackBindings() {
    if (window.__mcBindingsReady || !window.App) {
        return false;
    }

    const app = window.App;
    const bindClick = (id, handler, { stopPropagation = false } = {}) => {
        const element = document.getElementById(id);
        if (!element) {
            return;
        }
        element.onclick = (event) => {
            event.preventDefault();
            if (stopPropagation) {
                event.stopPropagation();
            }
            return handler(event);
        };
    };
    const bindInput = (id, eventName, handler) => {
        const element = document.getElementById(id);
        if (!element) {
            return;
        }
        element[`on${eventName}`] = (event) => handler(event);
    };

    document.querySelectorAll('.theme-card').forEach((card) => {
        card.onclick = () => app.selectTheme(card.dataset.theme);
    });
    document.querySelectorAll('.tab').forEach((tab) => {
        tab.onclick = () => app.switchTab(tab.dataset.tab);
    });

    bindClick('btn-launch', () => app.startGame());
    bindClick('btn-launch-local', () => app.startGameLocal());
    bindClick('btn-launch-atv', () => app.startGameATV());
    bindClick('btn-launch-dropdown', () => app.toggleDropdown('launch-dropdown-menu'), { stopPropagation: true });
    bindClick('btn-launch-local-dropdown', () => app.toggleDropdown('launch-local-dropdown-menu'), { stopPropagation: true });
    bindClick('btn-launch-atv-dropdown', () => app.toggleDropdown('launch-atv-dropdown-menu'), { stopPropagation: true });
    bindClick('btn-review-launch', () => { app.closeDropdowns(); return app.reviewAndLaunch('normal'); });
    bindClick('btn-review-launch-local', () => { app.closeDropdowns(); return app.reviewAndLaunch('local'); });
    bindClick('btn-review-launch-atv', () => { app.closeDropdowns(); return app.reviewAndLaunch('atv'); });
    bindClick('btn-confirm-launch', () => app.confirmReviewLaunch());
    bindClick('btn-cancel-review', () => app.cancelReview());
    bindClick('btn-save-config', () => app.saveConfig());
    bindClick('btn-toggle-debug-log', () => app.toggleDebugLogging());
    bindClick('btn-fetch-entities', () => app.fetchEntities());
    bindClick('btn-suggest', () => app.suggestChallenges());
    bindClick('btn-discover-speakers', () => app.discoverSpeakers());
    bindClick('btn-add-floor', () => app.addFloor());
    bindClick('btn-save-floors', () => app.saveFloors());
    bindClick('btn-needs-help', () => app.requestHelp());
    bindClick('btn-admin-success', () => app.adminSuccess());
    bindClick('btn-skip', () => app.skipRound());
    bindClick('btn-stop', () => app.stopGame());
    bindClick('btn-advance', () => app.advanceMission());
    bindClick('btn-play-again', () => app.showScreen('setup'));

    bindInput('input-speaker-volume', 'input', (event) => {
        const volumeDisplay = document.getElementById('volume-display');
        if (volumeDisplay) {
            volumeDisplay.textContent = event.target.value + '%';
        }
        const gameSlider = document.getElementById('game-volume-slider');
        const gameDisplay = document.getElementById('game-volume-display');
        if (gameSlider) {
            gameSlider.value = event.target.value;
        }
        if (gameDisplay) {
            gameDisplay.textContent = event.target.value + '%';
        }
    });
    bindInput('input-speaker-volume', 'change', (event) => {
        fetch(mcUrl('/api/config'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ speaker_volume: parseInt(event.target.value, 10) / 100 }),
        });
    });
    bindInput('game-volume-slider', 'input', (event) => {
        const gameDisplay = document.getElementById('game-volume-display');
        if (gameDisplay) {
            gameDisplay.textContent = event.target.value + '%';
        }
    });
    bindInput('game-volume-slider', 'change', (event) => {
        const volume = parseInt(event.target.value, 10) / 100;
        fetch(mcUrl('/api/config'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ speaker_volume: volume }),
        });
        const settingsSlider = document.getElementById('input-speaker-volume');
        const volumeDisplay = document.getElementById('volume-display');
        if (settingsSlider) {
            settingsSlider.value = event.target.value;
        }
        if (volumeDisplay) {
            volumeDisplay.textContent = event.target.value + '%';
        }
    });

    window.__mcBindingsReady = true;
    console.warn('Mission Control: installed fallback bindings');
    return true;
}
"""

    if "const MC_BASE_PATH = (() =>" not in js_text:
        js_text = js_text.replace(
            "// Mission Control - WebSocket Client & UI Logic\n\n",
            helper,
            1,
        )

    js_text = re.sub(
        r"fetch\((['`])(/[^'`]*?)\1,",
        lambda match: f"fetch(mcUrl({match.group(1)}{match.group(2)}{match.group(1)}),",
        js_text,
    )
    js_text = re.sub(
        r"fetch\((['`])(/[^'`]*?)\1\)",
        lambda match: f"fetch(mcUrl({match.group(1)}{match.group(2)}{match.group(1)}))",
        js_text,
    )
    js_text = re.sub(
        r"document\.getElementById\((['\"])([^'\"]+)\1\)\.addEventListener\(",
        lambda match: f"mcBindById({match.group(1)}{match.group(2)}{match.group(1)}, ",
        js_text,
    )
    js_text = js_text.replace(
        "        });\n    },\n\n    selectTheme(",
        "        });\n        window.__mcBindingsReady = true;\n    },\n\n    selectTheme(",
        1,
    )
    js_text = js_text.replace(
        "document.addEventListener('DOMContentLoaded', () => App.init());",
        "document.addEventListener('DOMContentLoaded', () => {\n    setTimeout(() => {\n        if (!window.__mcBindingsReady) {\n            mcInstallFallbackBindings();\n        }\n    }, 250);\n    try {\n        App.init();\n    } catch (err) {\n        console.error('Mission Control init failed:', err);\n        mcInstallFallbackBindings();\n    }\n});",
        1,
    )

    replacements = [
        ("this.ws = new WebSocket(`${protocol}//${location.host}/ws`);", "this.ws = new WebSocket(`${protocol}//${location.host}${mcUrl('/ws')}`);"),
        ("const audio = new Audio(url);", "const audio = new Audio(mcResolveAssetUrl(url));"),
        ("this.introAudio = new Audio(url);", "this.introAudio = new Audio(mcResolveAssetUrl(url));"),
        ("                        ${m.exists ? `<button class=\"btn-approve\" onclick=\"App.playIntroMusic('${m.audio_url}', this)\">Play</button>` : ''}", "                        ${m.exists ? `<button class=\"btn-approve\" onclick=\"App.playIntroMusic('${m.audio_url}', this)\">Play</button>` : `<button class=\"btn-rethink\" onclick=\"App.generateIntroMusic('${m.theme}')\">Generate</button>`}"),
        ("                const err = await resp.json();\n                throw new Error(err.error || 'Failed');", "                throw new Error(await mcReadErrorMessage(resp, 'Failed'));"),
        ("            const data = await resp.json();\n            if (!resp.ok) throw new Error(data.error || 'Failed');", "            if (!resp.ok) throw new Error(await mcReadErrorMessage(resp, 'Generation failed'));\n            const data = await resp.json();"),
        ("            el.style.backgroundImage = `url(${url})`;", "            const resolvedUrl = mcResolveAssetUrl(url);\n            el.style.backgroundImage = `url(${resolvedUrl})`;"),
        ("            img.src = url;", "            img.src = resolvedUrl;"),
        ("        preview.innerHTML = `<img src=\"${url}\" style=\"max-width:400px;border-radius:8px;border:1px solid rgba(255,255,255,0.1)\">`;", "        const resolvedUrl = mcResolveAssetUrl(url);\n        preview.innerHTML = `<img src=\"${resolvedUrl}\" style=\"max-width:400px;border-radius:8px;border:1px solid rgba(255,255,255,0.1)\">`;"),
    ]

    for old, new in replacements:
        js_text = js_text.replace(old, new)

    js_text = js_text.replace(
        """                    <div class=\"intro-music-actions\">\n                        ${m.exists ? `<button class=\"btn-approve\" onclick=\"App.playIntroMusic('${m.audio_url}', this)\">Play</button>` : ''}\n                    </div>""",
        """                    <div class=\"intro-music-actions\">\n                        ${m.exists ? `<button class=\"btn-approve\" onclick=\"App.playIntroMusic('${m.audio_url}', this)\">Play</button>` : `<button class=\"btn-rethink\" onclick=\"App.generateIntroMusic('${m.theme}')\">Generate</button>`}\n                        ${m.exists ? `<button class=\"btn-rethink\" onclick=\"App.generateIntroMusic('${m.theme}')\">Regenerate</button>` : ''}\n                        ${m.exists ? `<button class=\"btn-deny\" onclick=\"App.deleteIntroMusic('${m.theme}')\">Delete</button>` : ''}\n                    </div>""",
    )
    js_text = js_text.replace(
        """            if (!resp.ok) {\n                const err = await resp.json();\n                throw new Error(err.error || 'Failed');\n            }""",
        """            if (!resp.ok) {\n                throw new Error(await mcReadErrorMessage(resp, 'Failed'));\n            }""",
    )
    js_text = js_text.replace(
        """        document.getElementById('btn-skip').addEventListener('click', () => this.skipRound());\n        document.getElementById('btn-stop').addEventListener('click', () => this.stopGame());\n        document.getElementById('btn-advance').addEventListener('click', () => this.advanceMission());""",
        """        document.getElementById('btn-needs-help').addEventListener('click', () => this.requestHelp());\n        document.getElementById('btn-admin-success').addEventListener('click', () => this.adminSuccess());\n        document.getElementById('btn-skip').addEventListener('click', () => this.skipRound());\n        document.getElementById('btn-stop').addEventListener('click', () => this.stopGame());\n        document.getElementById('btn-advance').addEventListener('click', () => this.advanceMission());""",
    )
    js_text = js_text.replace(
        """    async skipRound() {\n        await fetch(mcUrl('/api/skip'), { method: 'POST' });\n    },\n\n    async stopGame() {\n        await fetch(mcUrl('/api/stop'), { method: 'POST' });\n    },""",
        """    async skipRound() {\n        await fetch(mcUrl('/api/skip'), { method: 'POST' });\n    },\n\n    async requestHelp() {\n        const btn = document.getElementById('btn-needs-help');\n        const idleLabel = btn ? (btn.dataset.mcIdleLabel || btn.textContent.trim() || 'Try Again') : 'Try Again';\n        if (btn) {\n            btn.disabled = true;\n            btn.textContent = 'Replaying...';\n        }\n        try {\n            const resp = await fetch(mcUrl('/api/needs-help'), { method: 'POST' });\n            if (!resp.ok) {\n                throw new Error(await mcReadErrorMessage(resp, 'Failed to replay mission'));\n            }\n            mcShowToast('Mission replaying...');\n        } catch (err) {\n            alert('Try Again failed: ' + err.message);\n        } finally {\n            if (btn) {\n                btn.disabled = false;\n                btn.textContent = idleLabel;\n            }\n        }\n    },\n\n    async adminSuccess() {\n        const btn = document.getElementById('btn-admin-success');\n        if (!mcRequireSecondTap(btn, 'Confirm Success', 'Success!')) {\n            return;\n        }\n        if (btn) {\n            btn.disabled = true;\n            btn.textContent = 'Marking Success...';\n        }\n        try {\n            const resp = await fetch(mcUrl('/api/admin-success'), { method: 'POST' });\n            if (!resp.ok) {\n                throw new Error(await mcReadErrorMessage(resp, 'Failed to mark mission successful'));\n            }\n        } catch (err) {\n            alert('Admin success failed: ' + err.message);\n        } finally {\n            if (btn) {\n                btn.disabled = false;\n                mcClearTemporaryConfirm(btn);\n            }\n        }\n    },\n\n    async stopGame() {\n        await fetch(mcUrl('/api/stop'), { method: 'POST' });\n    },""",
    )

    if js_text != original_js:
        js_path.write_text(js_text, encoding="utf-8")
        print("Patched app.js for ingress-relative API, WS, and asset URLs")

engine_path = Path("/app/engine.py")
if engine_path.exists():
    engine_text = engine_path.read_text(encoding="utf-8")
    original_engine = engine_text

    old_monitor = '''    async def monitor_round(self, challenge: Challenge) -> dict:
        """Monitor WebSocket for challenge completion."""
        targets_remaining = {t.entity_id: t.target_state for t in challenge.targets}
        targets_completed = set()

        needs_change_event: set[str] = set()
        pre_setup_entities = {s.entity_id for s in challenge.pre_setup}
        for target in challenge.targets:
            if target.entity_id not in pre_setup_entities:
                current = self.state_cache.get(target.entity_id)
                if current == target.target_state:
                    needs_change_event.add(target.entity_id)
                    logger.info(f"{target.entity_id} already in target state '{target.target_state}', requiring change event")

        left_target_state: set[str] = set()
        start_time = time.time()
        hint_sent = False
        elapsed = 0
'''

    new_monitor = '''    async def monitor_round(self, challenge: Challenge) -> dict:
        """Monitor WebSocket for challenge completion."""
        off_state_aliases = {"off", "unavailable", "unknown"}

        def _matches_target_state(entity_id: str, current_state: str, target_state: str) -> bool:
            current_state = current_state or ""
            if current_state == target_state:
                return True

            domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
            if target_state == "off" and domain in {"light", "switch", "fan"}:
                return current_state in off_state_aliases

            return False

        targets_remaining = {t.entity_id: t.target_state for t in challenge.targets}
        targets_completed = set()
        initial_target_states = dict(getattr(self, "_round_initial_states", {}) or {})

        # Reconcile any queued HA events that arrived after round setup but before monitoring started.
        await self.drain_ws_events(max_iterations=100, timeout=0.05)

        needs_change_event: set[str] = set()
        pre_setup_entities = {s.entity_id for s in challenge.pre_setup}
        for target in challenge.targets:
            current = self.state_cache.get(target.entity_id)
            if not _matches_target_state(target.entity_id, current, target.target_state):
                continue

            if _matches_target_state(target.entity_id, initial_target_states.get(target.entity_id), target.target_state) and target.entity_id not in pre_setup_entities:
                needs_change_event.add(target.entity_id)
                logger.info(f"{target.entity_id} already in target state '{target.target_state}', requiring change event")
                continue

            targets_completed.add(target.entity_id)
            targets_remaining.pop(target.entity_id, None)

        left_target_state: set[str] = set()
        start_time = time.time()
        hint_sent = False
        elapsed = 0

        if targets_completed:
            logger.info(f"Round start reconciled completed targets: {sorted(targets_completed)}")
            await self.broadcast({
                "type": "target_update",
                "targets": [
                    {"entity_id": t.entity_id, "completed": t.entity_id in targets_completed}
                    for t in challenge.targets
                ],
            })
            if not targets_remaining:
                return {"status": "completed", "time": 0}
'''

    old_event_logic = '''                        if entity_id in needs_change_event:
                            if new_state != target_state:
                                left_target_state.add(entity_id)
                            elif new_state == target_state and entity_id in left_target_state:
                                targets_completed.add(entity_id)
                                del targets_remaining[entity_id]
                        elif new_state == target_state:
                            targets_completed.add(entity_id)
                            del targets_remaining[entity_id]
'''

    new_event_logic = '''                        if entity_id in needs_change_event:
                            if not _matches_target_state(entity_id, new_state, target_state):
                                left_target_state.add(entity_id)
                            elif _matches_target_state(entity_id, new_state, target_state) and entity_id in left_target_state:
                                targets_completed.add(entity_id)
                                del targets_remaining[entity_id]
                        elif _matches_target_state(entity_id, new_state, target_state):
                            targets_completed.add(entity_id)
                            del targets_remaining[entity_id]
'''

    old_round_setup = '''                # Pre-setup
                if challenge.pre_setup:
                    await self.pre_setup_challenge(challenge)

                # Pick announcement from precached options (first is standard, rest are funny)
'''

    new_round_setup = '''                # Pre-setup
                if challenge.pre_setup:
                    await self.pre_setup_challenge(challenge)

                # Snapshot target states before the announcement so early completions can be reconciled.
                self._round_initial_states = {
                    t.entity_id: self.state_cache.get(t.entity_id)
                    for t in challenge.targets
                }

                # Pick announcement from precached options (first is standard, rest are funny)
'''

    if old_monitor in engine_text:
        engine_text = engine_text.replace(old_monitor, new_monitor, 1)
    if old_event_logic in engine_text:
        engine_text = engine_text.replace(old_event_logic, new_event_logic, 1)
    if old_round_setup in engine_text:
        engine_text = engine_text.replace(old_round_setup, new_round_setup, 1)
    engine_text = engine_text.replace(
        '        self.skip_requested = False\n        self.stop_requested = False\n',
        '        self.skip_requested = False\n        self.stop_requested = False\n        self.admin_success_requested = False\n        self.needs_help_requested = False\n',
        1,
    )
    engine_text = engine_text.replace(
        '            if self.skip_requested:\n                self.skip_requested = False\n                return {"status": "skipped", "time": round(elapsed)}\n\n            if self.stop_requested:\n                return {"status": "stopped", "time": round(elapsed)}\n',
        '            if self.needs_help_requested:\n                self.needs_help_requested = False\n                theme = self._current_theme\n                help_start = time.time()\n\n                options = getattr(self, "_announcement_options", {}).get(challenge.name, [])\n                if len(options) > 1 and random.random() < 0.33:\n                    announcement = random.choice(options[1:])\n                elif options:\n                    announcement = options[0]\n                else:\n                    announcement = theme.wrap_announcement(challenge.announcement)\n\n                await self.play_cached_audio(\n                    self.hub_speaker,\n                    announcement,\n                    theme.announcer_voice,\n                )\n\n                start_time += time.time() - help_start\n                await self.broadcast({"type": "mission_replayed", "round": self.current_round})\n                continue\n\n            if self.admin_success_requested:\n                self.admin_success_requested = False\n                return {"status": "completed", "time": round(elapsed)}\n\n            if self.skip_requested:\n                self.skip_requested = False\n                return {"status": "skipped", "time": round(elapsed)}\n\n            if self.stop_requested:\n                return {"status": "stopped", "time": round(elapsed)}\n',
        1,
    )
    engine_text = engine_text.replace(
        '        self.stop_requested = False\n        self.skip_requested = False\n        self.results = []\n',
        '        self.stop_requested = False\n        self.skip_requested = False\n        self.admin_success_requested = False\n        self.needs_help_requested = False\n        self.results = []\n',
        1,
    )
    engine_text = engine_text.replace(
        '    def request_stop(self):\n        self.stop_requested = True\n',
        '    def request_stop(self):\n        self.stop_requested = True\n\n    def request_needs_help(self):\n        self.needs_help_requested = True\n\n    def request_admin_success(self):\n        self.admin_success_requested = True\n',
        1,
    )

    if engine_text != original_engine:
        engine_path.write_text(engine_text, encoding="utf-8")
        print("Patched engine.py to reconcile early target completions")

server_path = Path("/app/server.py")
if server_path.exists():
    server_text = server_path.read_text(encoding="utf-8")
    original_server = server_text

    original_round_routes = '@app.post("/api/skip")\nasync def skip_round():\n    if not engine.running:\n        return JSONResponse({"error": "No game running"}, status_code=409)\n    engine.request_skip()\n    return {"status": "skipping"}\n\n\n@app.post("/api/stop")'
    admin_success_routes = '@app.post("/api/skip")\nasync def skip_round():\n    if not engine.running:\n        return JSONResponse({"error": "No game running"}, status_code=409)\n    engine.request_skip()\n    return {"status": "skipping"}\n\n\n@app.post("/api/admin-success")\nasync def admin_success():\n    """Parent/admin override: mark the active mission as completed."""\n    if not engine.running:\n        return JSONResponse({"error": "No game running"}, status_code=409)\n    engine.request_admin_success()\n    return {"status": "completing"}\n\n\n@app.post("/api/stop")'
    needs_help_routes = '@app.post("/api/skip")\nasync def skip_round():\n    if not engine.running:\n        return JSONResponse({"error": "No game running"}, status_code=409)\n    engine.request_skip()\n    return {"status": "skipping"}\n\n\n@app.post("/api/needs-help")\nasync def needs_help():\n    """Replay the current mission audio and pause the timer during playback."""\n    if not engine.running:\n        return JSONResponse({"error": "No game running"}, status_code=409)\n    engine.request_needs_help()\n    return {"status": "replaying"}\n\n\n@app.post("/api/admin-success")\nasync def admin_success():\n    """Parent/admin override: mark the active mission as completed."""\n    if not engine.running:\n        return JSONResponse({"error": "No game running"}, status_code=409)\n    engine.request_admin_success()\n    return {"status": "completing"}\n\n\n@app.post("/api/stop")'

    if needs_help_routes not in server_text:
        if admin_success_routes in server_text:
            server_text = server_text.replace(admin_success_routes, needs_help_routes, 1)
        elif original_round_routes in server_text:
            server_text = server_text.replace(original_round_routes, needs_help_routes, 1)

    if server_text != original_server:
        server_path.write_text(server_text, encoding="utf-8")
        print("Patched server.py with parent controls and needs-help endpoint")
PY

exec uvicorn server:app --host 0.0.0.0 --port 8765
