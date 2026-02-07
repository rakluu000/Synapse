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
        flex-wrap: wrap;
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
      .btn.active { border-color: var(--accent); }
      .hint { color: var(--muted); font-size: 12px; }
      details {
        border: 1px solid var(--border);
        border-radius: 10px;
        background: rgba(255,255,255,0.02);
        margin: 6px 0;
        overflow: hidden;
      }
      summary {
        cursor: pointer;
        padding: 8px 10px;
        font-size: 12px;
        user-select: none;
        list-style: none;
      }
      summary::-webkit-details-marker { display: none; }
      .detailsBody { padding: 8px 10px 10px; }
      .row {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        margin: 6px 0 2px;
      }
      .pill {
        background: rgba(255,255,255,0.06);
        color: var(--text);
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 4px 8px;
        cursor: pointer;
        font-size: 11px;
      }
      .pill:hover { border-color: rgba(79,140,255,0.6); }
      .pill.active { border-color: var(--accent); }
      .label {
        color: var(--muted);
        font-size: 11px;
        margin-top: 6px;
      }
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
          <button class="btn active" id="timeline">Timeline</button>
          <button class="btn" id="browse">Browse</button>
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
      const timelineBtn = document.getElementById('timeline');
      const browseBtn = document.getElementById('browse');

      let active = null;
      let view = 'timeline';
      let lastTree = null;

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

      function mkButton(path, label, cls) {
        const b = document.createElement('button');
        b.className = cls || 'file';
        b.textContent = label || path;
        b.onclick = () => openFile(path, b);
        return b;
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

      function splitSlugPhase(stem, knownSlugs) {
        // Handles optional numeric suffix like "-2" used by Synapse unique_path().
        // If known slugs (from plan files) are available, use the longest prefix match to
        // support phases that contain hyphens (e.g. "draft-impl").
        let base = stem;
        const m = base.match(/^(.*)-(\\d+)$/);
        if (m) base = m[1];

        if (knownSlugs && knownSlugs.length) {
          for (const s of knownSlugs) {
            if (base === s) return { slug: s, phase: 'unknown' };
            if (base.startsWith(s + '-')) {
              const phase = base.slice(s.length + 1);
              return { slug: s, phase: phase || 'unknown' };
            }
          }
        }

        const idx = base.lastIndexOf('-');
        if (idx === -1) return { slug: base, phase: 'unknown' };
        return { slug: base.slice(0, idx), phase: base.slice(idx + 1) };
      }

      function buildTimeline(tree) {
        const slugs = new Map(); // slug -> { slug, plan_files:[], phases: Map(phase -> {phase, context_files:[], models: Map(model -> {model, runs: Map(ts -> run)})}) }
        const verify_logs = []; // { ts, path, name }
        const ungrouped = { plan_files: [], context_files: [], prompt_files: [], patch_files: [], log_files: [] };

        function getSlug(slug) {
          if (!slugs.has(slug)) {
            slugs.set(slug, { slug, plan_files: [], phases: new Map() });
          }
          return slugs.get(slug);
        }
        function getPhase(slugObj, phase) {
          if (!slugObj.phases.has(phase)) {
            slugObj.phases.set(phase, { phase, context_files: [], models: new Map() });
          }
          return slugObj.phases.get(phase);
        }
        function getModel(phaseObj, model) {
          if (!phaseObj.models.has(model)) {
            phaseObj.models.set(model, { model, runs: new Map() });
          }
          return phaseObj.models.get(model);
        }
        function getRun(modelObj, ts) {
          if (!modelObj.runs.has(ts)) {
            modelObj.runs.set(ts, { ts, prompt: null, output: null, diff: null, log: null, logAttempt: 0 });
          }
          return modelObj.runs.get(ts);
        }

        const knownSlugs = [];

        (tree.plan_files || []).forEach((path) => {
          const m = path.match(/^\\.synapse\\/plan\\/(.+)\\.md$/);
          if (!m) return ungrouped.plan_files.push(path);
          const slug = m[1];
          getSlug(slug).plan_files.push(path);
        });

        // Prefer longest match first.
        knownSlugs.push(...Array.from(slugs.keys()).sort((a, b) => b.length - a.length));

        (tree.context_files || []).forEach((path) => {
          const m = path.match(/^\\.synapse\\/context\\/(.+)\\.md$/);
          if (!m) return ungrouped.context_files.push(path);
          const parts = splitSlugPhase(m[1], knownSlugs);
          if (!parts.slug) return ungrouped.context_files.push(path);
          const slugObj = getSlug(parts.slug);
          const phaseObj = getPhase(slugObj, parts.phase);
          phaseObj.context_files.push(path);
        });

        (tree.prompt_files || []).forEach((path) => {
          const m = path.match(/^\\.synapse\\/prompts\\/(\\d{8}-\\d{6})-(.+)-(claude|gemini)\\.prompt(?:-\\d+)?\\.md$/);
          if (!m) return ungrouped.prompt_files.push(path);
          const ts = m[1];
          const parts = splitSlugPhase(m[2], knownSlugs);
          const model = m[3];
          if (!parts.slug || !parts.phase) return ungrouped.prompt_files.push(path);
          const run = getRun(getModel(getPhase(getSlug(parts.slug), parts.phase), model), ts);
          run.prompt = path;
        });

        (tree.patch_files || []).forEach((path) => {
          let m = path.match(/^\\.synapse\\/patches\\/(\\d{8}-\\d{6})-(.+)-(claude|gemini)(?:-\\d+)?\\.md$/);
          if (m) {
            const ts = m[1];
            const parts = splitSlugPhase(m[2], knownSlugs);
            const model = m[3];
            if (!parts.slug || !parts.phase) return ungrouped.patch_files.push(path);
            const run = getRun(getModel(getPhase(getSlug(parts.slug), parts.phase), model), ts);
            run.output = path;
            return;
          }
          m = path.match(/^\\.synapse\\/patches\\/(\\d{8}-\\d{6})-(.+)-(claude|gemini)(?:-\\d+)?\\.diff$/);
          if (m) {
            const ts = m[1];
            const parts = splitSlugPhase(m[2], knownSlugs);
            const model = m[3];
            if (!parts.slug || !parts.phase) return ungrouped.patch_files.push(path);
            const run = getRun(getModel(getPhase(getSlug(parts.slug), parts.phase), model), ts);
            run.diff = path;
            return;
          }
          ungrouped.patch_files.push(path);
        });

        (tree.log_files || []).forEach((path) => {
          let m = path.match(/^\\.synapse\\/logs\\/(\\d{8}-\\d{6})-(.+)-(claude|gemini)-stream(?:-attempt(\\d+))?\\.jsonl$/);
          if (m) {
            const ts = m[1];
            const parts = splitSlugPhase(m[2], knownSlugs);
            const model = m[3];
            const attempt = m[4] ? parseInt(m[4], 10) : 1;
            if (!parts.slug || !parts.phase) return ungrouped.log_files.push(path);
            const run = getRun(getModel(getPhase(getSlug(parts.slug), parts.phase), model), ts);
            if (attempt >= (run.logAttempt || 0)) {
              run.log = path;
              run.logAttempt = attempt;
            }
            return;
          }
          m = path.match(/^\\.synapse\\/logs\\/(\\d{8}-\\d{6})-verify-(.+)\\.log$/);
          if (m) {
            verify_logs.push({ ts: m[1], name: m[2], path });
            return;
          }
          ungrouped.log_files.push(path);
        });

        // Convert maps to sorted arrays
        const slugArr = Array.from(slugs.values()).map((s) => {
          const phaseArr = Array.from(s.phases.values()).map((ph) => {
            const modelArr = Array.from(ph.models.values()).map((mo) => {
              const runsArr = Array.from(mo.runs.values()).sort((a, b) => (a.ts < b.ts ? 1 : -1));
              return { model: mo.model, runs: runsArr };
            }).sort((a, b) => a.model.localeCompare(b.model));
            const ctx = (ph.context_files || []).slice().sort();
            return { phase: ph.phase, context_files: ctx, models: modelArr };
          }).sort((a, b) => a.phase.localeCompare(b.phase));
          return { slug: s.slug, plan_files: (s.plan_files || []).slice().sort(), phases: phaseArr };
        });

        function latestTsForSlug(s) {
          let best = '';
          (s.phases || []).forEach((ph) => {
            (ph.models || []).forEach((mo) => {
              (mo.runs || []).forEach((r) => {
                if (r.ts && r.ts > best) best = r.ts;
              });
            });
          });
          return best;
        }
        slugArr.sort((a, b) => {
          const ta = latestTsForSlug(a);
          const tb = latestTsForSlug(b);
          if (ta !== tb) return ta < tb ? 1 : -1;
          return a.slug.localeCompare(b.slug);
        });

        verify_logs.sort((a, b) => (a.ts < b.ts ? 1 : -1));

        return { slugs: slugArr, verify_logs, ungrouped };
      }

      function renderBrowse(tree) {
        addSection('State', tree.state_files);
        addSection('Plans', tree.plan_files);
        addSection('Prompts', tree.prompt_files);
        addSection('Patches', tree.patch_files);
        addSection('Context packs', tree.context_files);
        addSection('Logs', tree.log_files);
      }

      function renderTimeline(tree) {
        const tl = buildTimeline(tree);

        // State (always handy)
        if (tree.state_files && tree.state_files.length) {
          const sec = document.createElement('div');
          sec.className = 'section';
          const h = document.createElement('h3');
          h.textContent = 'State';
          sec.appendChild(h);
          tree.state_files.forEach((p) => sec.appendChild(mkButton(p, p, 'file')));
          treeEl.appendChild(sec);
        }

        // Verify logs (global)
        if (tl.verify_logs.length) {
          const sec = document.createElement('div');
          sec.className = 'section';
          const h = document.createElement('h3');
          h.textContent = 'Verify logs';
          sec.appendChild(h);
          tl.verify_logs.forEach((v) => {
            const label = `${v.ts}  verify  ${v.name}`;
            sec.appendChild(mkButton(v.path, label, 'file'));
          });
          treeEl.appendChild(sec);
        }

        // Per-slug timeline
        const sec = document.createElement('div');
        sec.className = 'section';
        const h = document.createElement('h3');
        h.textContent = 'Timeline (by slug → phase → model)';
        sec.appendChild(h);

        if (!tl.slugs.length) {
          const hint = document.createElement('div');
          hint.className = 'hint';
          hint.textContent = '(no grouped artifacts yet)';
          sec.appendChild(hint);
          treeEl.appendChild(sec);
        } else {
          tl.slugs.forEach((s, idx) => {
            const d = document.createElement('details');
            d.open = idx === 0;
            const sum = document.createElement('summary');
            sum.textContent = s.slug;
            d.appendChild(sum);

            const body = document.createElement('div');
            body.className = 'detailsBody';

            if (s.plan_files.length) {
              const lab = document.createElement('div');
              lab.className = 'label';
              lab.textContent = 'Plan';
              body.appendChild(lab);
              s.plan_files.forEach((p) => body.appendChild(mkButton(p, p, 'file')));
            }

            s.phases.forEach((ph) => {
              const pd = document.createElement('details');
              const ps = document.createElement('summary');
              ps.textContent = `phase: ${ph.phase}`;
              pd.appendChild(ps);

              const pb = document.createElement('div');
              pb.className = 'detailsBody';

              if (ph.context_files.length) {
                const lab = document.createElement('div');
                lab.className = 'label';
                lab.textContent = 'Context packs';
                pb.appendChild(lab);
                ph.context_files.forEach((p) => pb.appendChild(mkButton(p, p, 'file')));
              }

              ph.models.forEach((mo) => {
                const md = document.createElement('details');
                const ms = document.createElement('summary');
                ms.textContent = `model: ${mo.model}`;
                md.appendChild(ms);

                const mb = document.createElement('div');
                mb.className = 'detailsBody';

                if (!mo.runs.length) {
                  const hint = document.createElement('div');
                  hint.className = 'hint';
                  hint.textContent = '(none)';
                  mb.appendChild(hint);
                }

                mo.runs.forEach((r) => {
                  const rd = document.createElement('details');
                  const rs = document.createElement('summary');
                  rs.textContent = r.ts;
                  rd.appendChild(rs);

                  const rb = document.createElement('div');
                  rb.className = 'detailsBody';

                  const row = document.createElement('div');
                  row.className = 'row';
                  if (r.prompt) row.appendChild(mkButton(r.prompt, 'prompt', 'pill'));
                  if (r.output) row.appendChild(mkButton(r.output, 'output', 'pill'));
                  if (r.diff) row.appendChild(mkButton(r.diff, 'diff', 'pill'));
                  if (r.log) row.appendChild(mkButton(r.log, 'log', 'pill'));
                  if (!r.prompt && !r.output && !r.diff && !r.log) {
                    const hint = document.createElement('div');
                    hint.className = 'hint';
                    hint.textContent = '(no files)';
                    rb.appendChild(hint);
                  } else {
                    rb.appendChild(row);
                  }

                  rd.appendChild(rb);
                  mb.appendChild(rd);
                });

                md.appendChild(mb);
                pb.appendChild(md);
              });

              pd.appendChild(pb);
              body.appendChild(pd);
            });

            d.appendChild(body);
            sec.appendChild(d);
          });

          treeEl.appendChild(sec);
        }

        // Ungrouped (fallback)
        const anyUngrouped =
          tl.ungrouped.plan_files.length ||
          tl.ungrouped.context_files.length ||
          tl.ungrouped.prompt_files.length ||
          tl.ungrouped.patch_files.length ||
          tl.ungrouped.log_files.length;
        if (anyUngrouped) {
          const sec2 = document.createElement('div');
          sec2.className = 'section';
          const h2 = document.createElement('h3');
          h2.textContent = 'Ungrouped (filename did not match expected patterns)';
          sec2.appendChild(h2);
          const groups = [
            ['Plans', tl.ungrouped.plan_files],
            ['Context', tl.ungrouped.context_files],
            ['Prompts', tl.ungrouped.prompt_files],
            ['Patches', tl.ungrouped.patch_files],
            ['Logs', tl.ungrouped.log_files],
          ];
          groups.forEach(([title, files]) => {
            if (!files.length) return;
            const lab = document.createElement('div');
            lab.className = 'label';
            lab.textContent = title;
            sec2.appendChild(lab);
            files.slice().sort().forEach((p) => sec2.appendChild(mkButton(p, p, 'file')));
          });
          treeEl.appendChild(sec2);
        }
      }

      function setView(next) {
        view = next;
        timelineBtn.classList.toggle('active', view === 'timeline');
        browseBtn.classList.toggle('active', view === 'browse');
        if (view === 'timeline') {
          timelineBtn.classList.add('active');
          browseBtn.classList.remove('active');
        } else {
          browseBtn.classList.add('active');
          timelineBtn.classList.remove('active');
        }
        render();
      }

      function render() {
        treeEl.innerHTML = '';
        contentEl.textContent = '';
        filePathEl.textContent = 'Select a file.';
        active = null;
        if (!lastTree) return;
        if (view === 'browse') return renderBrowse(lastTree);
        return renderTimeline(lastTree);
      }

      async function refresh() {
        statusEl.textContent = 'Refreshing...';
        try {
          lastTree = await getJson('/api/tree');
          statusEl.textContent = '';
          render();
        } catch (e) {
          statusEl.textContent = 'Error';
          treeEl.textContent = String(e);
        }
      }

      refreshBtn.onclick = refresh;
      timelineBtn.onclick = () => setView('timeline');
      browseBtn.onclick = () => setView('browse');
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
