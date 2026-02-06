from __future__ import annotations

import argparse
import http.server
import json
import threading
import urllib.parse
import webbrowser
from pathlib import Path

from .common import SynapseError, find_project_root, synapse_paths


_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Synapse Viewer</title>
    <style>
      :root {
        --bg: #0b0e14;
        --panel: #101521;
        --text: #e6e6e6;
        --muted: #9aa4b2;
        --border: #283046;
        --accent: #4f8cff;
        --code: #0f172a;
      }
      body {
        margin: 0;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
        background: var(--bg);
        color: var(--text);
      }
      header {
        padding: 12px 16px;
        border-bottom: 1px solid var(--border);
        background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0));
      }
      header .title {
        font-weight: 600;
        letter-spacing: 0.2px;
      }
      header .subtitle {
        margin-top: 4px;
        color: var(--muted);
        font-size: 12px;
      }
      .wrap {
        display: grid;
        grid-template-columns: 360px 1fr;
        min-height: calc(100vh - 56px);
      }
      .sidebar {
        border-right: 1px solid var(--border);
        background: var(--panel);
        padding: 12px;
        overflow: auto;
      }
      .main {
        padding: 12px;
        overflow: auto;
      }
      .section {
        margin-bottom: 12px;
      }
      .section h3 {
        margin: 12px 0 8px;
        font-size: 13px;
        color: var(--muted);
        font-weight: 600;
      }
      .file {
        display: block;
        width: 100%;
        text-align: left;
        padding: 8px 10px;
        margin: 4px 0;
        border: 1px solid var(--border);
        border-radius: 8px;
        background: rgba(255,255,255,0.02);
        color: var(--text);
        cursor: pointer;
        font-size: 12px;
      }
      .file:hover { border-color: rgba(79,140,255,0.6); }
      .file.active { border-color: var(--accent); }
      .toolbar {
        display: flex;
        gap: 8px;
        align-items: center;
        margin-bottom: 10px;
      }
      .btn {
        background: rgba(255,255,255,0.06);
        color: var(--text);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 7px 10px;
        cursor: pointer;
        font-size: 12px;
      }
      .btn:hover { border-color: rgba(79,140,255,0.6); }
      .hint { color: var(--muted); font-size: 12px; }
      pre {
        margin: 0;
        padding: 12px;
        border: 1px solid var(--border);
        border-radius: 10px;
        background: var(--code);
        overflow: auto;
        white-space: pre;
        font-size: 12px;
        line-height: 1.45;
      }
    </style>
  </head>
  <body>
    <header>
      <div class="title">Synapse Viewer</div>
      <div class="subtitle">Browse <code>./.synapse/**</code> prompts, outputs, patches, logs, and state.</div>
    </header>
    <div class="wrap">
      <div class="sidebar">
        <div class="toolbar">
          <button class="btn" id="refresh">Refresh</button>
          <span class="hint" id="status"></span>
        </div>
        <div id="tree"></div>
      </div>
      <div class="main">
        <div class="section">
          <div class="hint" id="filePath">Select a file.</div>
        </div>
        <pre id="content"></pre>
      </div>
    </div>
    <script>
      const statusEl = document.getElementById('status');
      const treeEl = document.getElementById('tree');
      const contentEl = document.getElementById('content');
      const filePathEl = document.getElementById('filePath');
      const refreshBtn = document.getElementById('refresh');

      let active = null;

      async function getJson(url) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(await res.text());
        return await res.json();
      }

      async function getText(url) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(await res.text());
        return await res.text();
      }

      function addSection(title, files) {
        const sec = document.createElement('div');
        sec.className = 'section';
        const h = document.createElement('h3');
        h.textContent = title;
        sec.appendChild(h);
        if (!files || files.length === 0) {
          const p = document.createElement('div');
          p.className = 'hint';
          p.textContent = '(none)';
          sec.appendChild(p);
          treeEl.appendChild(sec);
          return;
        }
        files.forEach((path) => {
          const b = document.createElement('button');
          b.className = 'file';
          b.textContent = path;
          b.onclick = () => openFile(path, b);
          sec.appendChild(b);
        });
        treeEl.appendChild(sec);
      }

      async function openFile(path, btn) {
        try {
          statusEl.textContent = 'Loading...';
          const text = await getText('/api/file?path=' + encodeURIComponent(path));
          contentEl.textContent = text;
          filePathEl.textContent = path;
          if (active) active.classList.remove('active');
          btn.classList.add('active');
          active = btn;
          statusEl.textContent = '';
        } catch (e) {
          statusEl.textContent = 'Error';
          contentEl.textContent = String(e);
        }
      }

      async function refresh() {
        statusEl.textContent = 'Refreshing...';
        treeEl.innerHTML = '';
        contentEl.textContent = '';
        filePathEl.textContent = 'Select a file.';
        active = null;
        try {
          const tree = await getJson('/api/tree');
          addSection('State', tree.state_files);
          addSection('Plans', tree.plan_files);
          addSection('Prompts', tree.prompt_files);
          addSection('Patches', tree.patch_files);
          addSection('Context packs', tree.context_files);
          addSection('Logs', tree.log_files);
          statusEl.textContent = '';
        } catch (e) {
          statusEl.textContent = 'Error';
          treeEl.textContent = String(e);
        }
      }

      refreshBtn.onclick = refresh;
      refresh();
    </script>
  </body>
</html>
"""


def _list_rel_files(*, project_root: Path, root: Path) -> list[str]:
    if not root.exists():
        return []
    out: list[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out.append(str(p.relative_to(project_root)).replace("\\", "/"))
    return out


def _within_synapse(synapse_root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(synapse_root.resolve())
        return True
    except Exception:
        return False


def cmd_ui(args: argparse.Namespace) -> int:
    project_root = find_project_root(Path(args.project_dir))
    paths = synapse_paths(project_root)
    syn_root = paths.synapse_dir
    if not syn_root.exists():
        raise SynapseError(f".synapse not found under: {project_root} (run synapse init first)")

    host = str(getattr(args, "host", "127.0.0.1"))
    port = int(getattr(args, "port", 8765))
    open_browser = not bool(getattr(args, "no_open", False))

    state_files: list[str] = []
    for p in (paths.state_json, paths.index_json):
        if p.exists():
            state_files.append(str(p.relative_to(project_root)).replace("\\", "/"))

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, *, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/":
                return self._send(200, _HTML.encode("utf-8"), content_type="text/html; charset=utf-8")
            if parsed.path == "/favicon.ico":
                return self._send(204, b"", content_type="text/plain; charset=utf-8")
            if parsed.path == "/api/tree":
                payload = {
                    "state_files": state_files,
                    "plan_files": _list_rel_files(project_root=project_root, root=paths.plan_dir),
                    "prompt_files": _list_rel_files(project_root=project_root, root=paths.prompts_dir),
                    "patch_files": _list_rel_files(project_root=project_root, root=paths.patches_dir),
                    "context_files": _list_rel_files(project_root=project_root, root=paths.context_dir),
                    "log_files": _list_rel_files(project_root=project_root, root=paths.logs_dir),
                }
                return self._send(
                    200,
                    (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
                    content_type="application/json; charset=utf-8",
                )
            if parsed.path == "/api/file":
                qs = urllib.parse.parse_qs(parsed.query)
                raw = (qs.get("path") or [""])[0]
                rel = Path(raw.replace("/", "\\"))
                if rel.is_absolute():
                    return self._send(400, b"absolute path not allowed\n", content_type="text/plain; charset=utf-8")
                full = (project_root / rel).resolve()
                if not _within_synapse(syn_root, full):
                    return self._send(403, b"only .synapse/** is accessible\n", content_type="text/plain; charset=utf-8")
                if not full.exists() or not full.is_file():
                    return self._send(404, b"not found\n", content_type="text/plain; charset=utf-8")
                data = full.read_bytes()
                max_bytes = 2_000_000
                if len(data) > max_bytes:
                    data = data[:max_bytes] + b"\n\n...(truncated)\n"
                return self._send(200, data, content_type="text/plain; charset=utf-8")
            return self._send(404, b"not found\n", content_type="text/plain; charset=utf-8")

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            # Keep the viewer quiet by default.
            return

    httpd = http.server.ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{httpd.server_address[1]}/"
    print(f"ui: {url}")
    if open_browser:
        threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
