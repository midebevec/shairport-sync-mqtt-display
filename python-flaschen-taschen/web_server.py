from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template_string, request
from yaml import safe_load, safe_dump


def build_image_data_url(image_bytes: bytes, mime_type: str | None = None) -> str:
    """Return a browser-safe data URL for a cover image bytes payload."""
    if not image_bytes:
        return ""
    if mime_type is None:
        mime_type = "image/png"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


NAV_TEMPLATE = """
<nav style=\"position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:40;display:inline-flex;gap:8px;align-items:center;padding:8px 10px;background:rgba(10,12,18,0.86);border:1px solid rgba(255,255,255,0.08);border-radius:999px;box-shadow:0 10px 26px rgba(0,0,0,0.28);backdrop-filter:blur(14px);max-width:calc(100vw - 24px);justify-content:center;\">
  <a href=\"/\" class=\"nav-link{% if active == 'now-playing' %} active{% endif %}\" aria-label=\"Now Playing\" style=\"display:flex;align-items:center;justify-content:center;width:42px;height:42px;color:{% if active == 'now-playing' %}#ffffff{% else %}#9ca3af{% endif %};text-decoration:none;border-radius:999px;border:1px solid rgba(255,255,255,0.12);background:{% if active == 'now-playing' %}rgba(255,255,255,0.14){% else %}rgba(255,255,255,0.03){% endif %};font-size:17px;line-height:1;box-shadow:{% if active == 'now-playing' %}inset 0 1px 0 rgba(255,255,255,0.16){% else %}none{% endif %};\">♫</a>
  <a href=\"/details\" class=\"nav-link{% if active == 'details' %} active{% endif %}\" aria-label=\"Details\" style=\"display:flex;align-items:center;justify-content:center;width:42px;height:42px;color:{% if active == 'details' %}#ffffff{% else %}#9ca3af{% endif %};text-decoration:none;border-radius:999px;border:1px solid rgba(255,255,255,0.12);background:{% if active == 'details' %}rgba(255,255,255,0.14){% else %}rgba(255,255,255,0.03){% endif %};font-size:17px;line-height:1;box-shadow:{% if active == 'details' %}inset 0 1px 0 rgba(255,255,255,0.16){% else %}none{% endif %};\">⋯</a>
  <a href=\"/clock\" class=\"nav-link{% if active == 'clock' %} active{% endif %}\" aria-label=\"Clock Controls\" style=\"display:flex;align-items:center;justify-content:center;width:42px;height:42px;color:{% if active == 'clock' %}#ffffff{% else %}#9ca3af{% endif %};text-decoration:none;border-radius:999px;border:1px solid rgba(255,255,255,0.12);background:{% if active == 'clock' %}rgba(255,255,255,0.14){% else %}rgba(255,255,255,0.03){% endif %};font-size:17px;line-height:1;box-shadow:{% if active == 'clock' %}inset 0 1px 0 rgba(255,255,255,0.16){% else %}none{% endif %};\">⏰</a>
</nav>
"""


NOW_PLAYING_TEMPLATE = """
<!doctype html>
<html>
  <head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\"><title>Now Playing</title>
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: radial-gradient(circle at top, #111827 0%, #06070a 60%); color: #f5f7fa; padding: 0; min-height:100vh; margin:0; }
    .page { min-height: 100vh; display:flex; flex-direction:column; justify-content:space-between; padding: 8px 8px 78px; }
    .shell { flex:1; display:flex; align-items:center; justify-content:center; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 24px; padding: 12px; box-shadow: 0 24px 60px rgba(0,0,0,0.28); backdrop-filter: blur(18px); }
    .content { width:100%; display:flex; flex-direction:column; align-items:center; text-align:center; gap:10px; }
    .cover-shell { width:min(100%, 360px); aspect-ratio:1/1; border-radius:22px; overflow:hidden; background:linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02)); border:1px solid rgba(255,255,255,0.12); box-shadow: 0 16px 32px rgba(0,0,0,0.24); }
    .art { width:100%; height:100%; object-fit:cover; display:block; background:#111827; }
    .placeholder { display:flex; align-items:center; justify-content:center; color:#94a3b8; font-size:1rem; }
    .eyebrow { font-size:0.78rem; text-transform:uppercase; letter-spacing:0.16em; color:#8fa0b8; margin-bottom:4px; }
    .title { font-size:clamp(1.5rem, 5vw, 2.15rem); line-height:1.06; margin:0; font-weight:700; }
    .subtitle { font-size:0.98rem; color:#cbd5e1; margin:0; line-height:1.45; max-width:560px; }
    .volume-row { width:min(300px, 100%); margin-top:2px; display:flex; align-items:center; gap:10px; justify-content:center; }
    .volume-track { flex:1; height:7px; border-radius:999px; background:rgba(255,255,255,0.12); overflow:hidden; }
    .volume-fill { height:100%; border-radius:999px; background:linear-gradient(90deg, #60a5fa, #818cf8); transition:width 0.25s ease; }
    .volume-value { font-size:0.9rem; color:#cbd5e1; min-width:42px; text-align:right; }
    .fade-highlight { animation: fadePulse 0.7s ease; }
    @keyframes fadePulse { 0% { opacity: 0.25; transform: translateY(2px); } 100% { opacity: 1; transform: translateY(0); } }
    @media (max-width: 700px) {
      .page { padding: 8px 8px 78px; }
      .shell { padding: 10px; border-radius: 20px; }
      .cover-shell { width:min(100%, 320px); border-radius: 20px; }
      .volume-row { width:100%; }
    }
  </style></head>
  <body>
    <div class=\"page\">
      <div class=\"shell\">
        <div class=\"content\">
          <div class=\"cover-shell\">
            <img id=\"cover-image\" class=\"art\" src=\"{{ state.cover_image or '' }}\" alt=\"Album art\" style=\"{{ 'display:block;' if state.cover_image else 'display:none;' }}\">
            <div id=\"cover-placeholder\" class=\"art placeholder\" style=\"{{ '' if state.cover_image else 'display:flex;' }}\">No album art yet</div>
          </div>
          <div>
            <div class=\"eyebrow\">Now Playing</div>
            <h1 class=\"title\" id=\"title\">{{ state.title or 'Nothing playing right now' }}</h1>
            <p class=\"subtitle\" id=\"artist-album\">{{ state.artist or 'Waiting for metadata' }} • {{ state.album or 'No album info yet' }}</p>
            <div class=\"volume-row\">
              <div class=\"volume-track\"><div id=\"volume-bar\" class=\"volume-fill\" style=\"width:0%;\"></div></div>
              <div id=\"volume-value\" class=\"volume-value\">0%</div>
            </div>
          </div>
        </div>
      </div>
      {{ nav | safe }}
    </div>
    <script>
      function updateField(id, value) {
        const element = document.getElementById(id);
        if (!element) return;
        const nextValue = value ?? '—';
        if (element.textContent !== nextValue) {
          element.textContent = nextValue;
          element.classList.remove('fade-highlight');
          void element.offsetWidth;
          element.classList.add('fade-highlight');
        }
      }

      function updateVolume(percent) {
        const bar = document.getElementById('volume-bar');
        const value = document.getElementById('volume-value');
        if (!bar || !value) return;
        const safePercent = Number(percent) || 0;
        bar.style.width = `${Math.max(0, Math.min(100, safePercent))}%`;
        value.textContent = `${Math.max(0, Math.min(100, safePercent))}%`;
      }

      function updateCover(imageDataUrl) {
        const image = document.getElementById('cover-image');
        const placeholder = document.getElementById('cover-placeholder');
        if (!image || !placeholder) return;
        if (imageDataUrl) {
          image.src = imageDataUrl;
          image.style.display = 'block';
          placeholder.style.display = 'none';
        } else {
          image.style.display = 'none';
          placeholder.style.display = 'flex';
          image.removeAttribute('src');
        }
      }

      let refreshTimer = null;
      let refreshInFlight = false;

      async function refreshState() {
        if (document.hidden || refreshInFlight) {
          scheduleRefresh();
          return;
        }

        refreshInFlight = true;
        try {
          const response = await fetch('/api/state');
          if (!response.ok) return;
          const state = await response.json();
          updateField('title', state.title || 'Nothing playing right now');
          updateField('artist-album', `${state.artist || 'Waiting for metadata'} • ${state.album || 'No album info yet'}`);
          updateVolume(state.volume_percent ?? 0);
          updateCover(state.cover_image || '');
        } catch (err) {
          console.error(err);
        } finally {
          refreshInFlight = false;
          scheduleRefresh();
        }
      }

      function scheduleRefresh() {
        if (refreshTimer) clearTimeout(refreshTimer);
        if (document.hidden) return;
        refreshTimer = setTimeout(refreshState, 3000);
      }

      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
          scheduleRefresh();
        }
      });

      scheduleRefresh();
      refreshState();
    </script>
  </body>
</html>
"""


DETAILS_TEMPLATE = """
<!doctype html>
<html>
  <head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\"><title>Details</title>
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #06070a; color: #f5f7fa; padding: 12px; min-height:100vh; margin:0; }
    .page { max-width: 860px; margin: 0 auto; }
    .shell { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 24px; padding: 14px; box-shadow: 0 24px 60px rgba(0,0,0,0.28); backdrop-filter: blur(18px); }
    .eyebrow { font-size:0.78rem; text-transform:uppercase; letter-spacing:0.16em; color:#8fa0b8; margin-bottom:8px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
    .stat { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:12px; min-height:92px; }
    .label { font-size:11px; text-transform:uppercase; color:#64748b; margin-bottom:6px; letter-spacing:0.12em; }
    .value { font-size:0.98rem; font-weight:600; color:#f8fafc; line-height:1.4; }
    .volume-track { height:8px; border-radius:999px; background:rgba(255,255,255,0.12); overflow:hidden; margin-top:8px; }
    .volume-fill { height:100%; border-radius:999px; background:linear-gradient(90deg, #60a5fa, #818cf8); }
    @media (max-width: 700px) {
      body { padding: 10px; }
      .shell { padding: 12px; border-radius: 20px; }
      .grid { grid-template-columns: 1fr 1fr; gap: 8px; }
      .stat { min-height: 84px; padding: 10px; }
    }
  </style></head>
  <body>
    <div class=\"page\">
      {{ nav | safe }}
      <div class=\"shell\">
        <div class=\"eyebrow\">Playback Details</div>
        <h1 style=\"margin:0 0 16px; font-size:1.5rem;\">Details</h1>
        <div class=\"grid\">
          <div class=\"stat\"><div class=\"label\">Artist</div><div class=\"value\">{{ state.artist or '—' }}</div></div>
          <div class=\"stat\"><div class=\"label\">Album</div><div class=\"value\">{{ state.album or '—' }}</div></div>
          <div class=\"stat\"><div class=\"label\">Title</div><div class=\"value\">{{ state.title or '—' }}</div></div>
          <div class=\"stat\">
            <div class=\"label\">Volume</div>
            <div class=\"value\">{{ state.volume_percent or '—' }}%</div>
            <div class=\"volume-track\"><div class=\"volume-fill\" style=\"width:{{ (state.volume_percent or 0) }}%;\"></div></div>
          </div>
          <div class=\"stat\"><div class=\"label\">Last topic</div><div class=\"value\">{{ state.last_topic or '—' }}</div></div>
          <div class=\"stat\"><div class=\"label\">Status</div><div class=\"value\">{{ state.status or 'unknown' }}</div></div>
        </div>
      </div>
    </div>
  </body>
</html>
"""


CLOCK_TEMPLATE = """
<!doctype html>
<html>
  <head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\"><title>Clock Controls</title>
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #06070a; color: #f5f7fa; padding: 12px; min-height:100vh; margin:0; }
    .page { max-width: 860px; margin: 0 auto; }
    .shell { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 24px; padding: 14px; box-shadow: 0 24px 60px rgba(0,0,0,0.28); backdrop-filter: blur(18px); }
    .eyebrow { font-size:0.78rem; text-transform:uppercase; letter-spacing:0.16em; color:#8fa0b8; margin-bottom:10px; }
    .field { display:flex; flex-direction:column; gap:6px; margin-bottom:10px; }
    label { color:#cbd5e1; font-size:0.95rem; }
    input, select, button { padding:12px; border-radius:14px; border:1px solid rgba(255,255,255,0.12); background:rgba(255,255,255,0.04); color:#f8fafc; width:100%; margin-top:2px; box-sizing:border-box; font-size:1rem; }
    button { background:linear-gradient(90deg, #60a5fa, #818cf8); cursor:pointer; font-weight:600; border:none; padding:12px 14px; width:auto; min-width:144px; } 
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .hint { color:#94a3b8; font-size:0.95rem; margin-top:12px; line-height:1.45; }
    .toast { display:none; margin-top:12px; padding:10px 12px; border-radius:12px; background:rgba(34,197,94,0.16); border:1px solid rgba(74,222,128,0.25); color:#dcfce7; font-size:0.95rem; }
    .toast.show { display:block; }
    @media (max-width: 700px) {
      body { padding: 10px; }
      .shell { padding: 12px; border-radius: 20px; }
      .grid { grid-template-columns: 1fr; }
      button { width:100%; }
    }
  </style></head>
  <body>
    <div class=\"page\">
      {{ nav | safe }}
      <div class=\"shell\">
        <div class=\"eyebrow\">Clock Settings</div>
        <h1 style=\"margin:0 0 16px; font-size:1.5rem;\">Clock Controls</h1>
        <form id=\"clock-form\">
          <div class=\"grid\">
            <div class=\"field\">
              <label for=\"clock-enabled\">Clock enabled</label>
              <input id=\"clock-enabled\" type=\"checkbox\" name=\"clock.enabled\" value=\"true\" {{ 'checked' if config.clock.enabled else '' }}>
            </div>
            <div class=\"field\">
              <label for=\"clock-type\">Clock type</label>
              <select id=\"clock-type\" name=\"clock.type\">
                <option value=\"analog\" {{ 'selected' if config.clock.type == 'analog' else '' }}>analog</option>
                <option value=\"digital\" {{ 'selected' if config.clock.type == 'digital' else '' }}>digital</option>
              </select>
            </div>
          </div>
          <div class=\"grid\">
            <div class=\"field\">
              <label for=\"clock-start\">Start time</label>
              <input id=\"clock-start\" name=\"clock.time_window.start\" value=\"{{ config.clock.time_window.start }}\">
            </div>
            <div class=\"field\">
              <label for=\"clock-end\">End time</label>
              <input id=\"clock-end\" name=\"clock.time_window.end\" value=\"{{ config.clock.time_window.end }}\">
            </div>
          </div>
          <button type=\"submit\">Save settings</button>
          <div id=\"save-toast\" class=\"toast\">Settings updated</div>
        </form>
        <p class=\"hint\">Changes are written back to your YAML configuration file immediately.</p>
        <script>
          const form = document.getElementById('clock-form');
          const toast = document.getElementById('save-toast');

          form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const formData = new FormData(form);
            try {
              const response = await fetch('/api/config', {
                method: 'POST',
                body: formData
              });
              if (response.ok) {
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 2200);
              }
            } catch (err) {
              console.error(err);
            }
          });
        </script>
      </div>
    </div>
  </body>
</html>
"""


class DisplayState:
    def __init__(self):
        self._state: dict[str, Any] = {
            "status": "starting",
            "last_topic": None,
            "last_payload": None,
            "artist": None,
            "album": None,
            "title": None,
            "volume": None,
            "volume_percent": None,
            "cover": None,
            "cover_art": None,
            "cover_image": "",
        }

    def update(self, key: str, value: Any) -> None:
        if key == "cover_art":
            if isinstance(value, (bytes, bytearray)):
                self._state["cover_art"] = "present"
                self._state["cover_image"] = build_image_data_url(bytes(value))
            else:
                self._state["cover_art"] = None
                self._state["cover_image"] = ""
        else:
            self._state[key] = value

    def get(self) -> dict[str, Any]:
        state = dict(self._state)
        state["cover_art"] = "present" if state.get("cover_image") else None
        return state


class ConfigStore:
    def __init__(self, config_path: Path | str):
        self.config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self.load()

    def load(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file {self.config_path} does not exist.")
        with self.config_path.open() as handle:
            self._config = safe_load(handle) or {}
        return self._config

    def save(self) -> None:
        with self.config_path.open("w") as handle:
            safe_dump(self._config, handle, sort_keys=False)

    def get(self) -> dict[str, Any]:
        return self._config

    def update_from_form(self, form_data: dict[str, Any]) -> None:
        for key, value in form_data.items():
            self._set_nested_value(key, value)
        self.save()

    def _set_nested_value(self, key: str, value: str) -> None:
        parts = key.split(".")
        current: Any = self._config
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        leaf = parts[-1]
        if value.lower() in {"true", "false"}:
            current[leaf] = value.lower() == "true"
        else:
            current[leaf] = value


def create_app(config_path: Path | str = "config.yaml", display_state: DisplayState | None = None) -> Flask:
    config_store = ConfigStore(config_path)
    app = Flask(__name__)
    state = display_state or DisplayState()

    @app.get("/")
    def index():
        return render_template_string(
            NOW_PLAYING_TEMPLATE,
            nav=render_template_string(
                NAV_TEMPLATE,
                active="now-playing",
            ),
            config=config_store.get(),
            state=state.get(),
            message="",
        )

    @app.get("/details")
    def details_page():
        return render_template_string(
            DETAILS_TEMPLATE,
            nav=render_template_string(
                NAV_TEMPLATE,
                active="details",
            ),
            config=config_store.get(),
            state=state.get(),
            message="",
        )

    @app.get("/clock")
    def clock_page():
        return render_template_string(
            CLOCK_TEMPLATE,
            nav=render_template_string(
                NAV_TEMPLATE,
                active="clock",
            ),
            config=config_store.get(),
            state=state.get(),
            message="",
        )

    @app.post("/api/config")
    def update_config():
        config_store.update_from_form(request.form)
        return jsonify({"status": "ok"})

    @app.get("/api/state")
    def get_state():
        return jsonify(state.get())

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)
