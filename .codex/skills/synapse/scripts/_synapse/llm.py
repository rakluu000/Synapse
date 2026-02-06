from __future__ import annotations

import datetime as _dt
import json
import random
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Optional

from .common import SynapseError, safe_mkdir, synapse_paths


@dataclass
class ModelRun:
    model: str
    prompt: str
    cwd: Path
    resume: Optional[str]
    timeout_seconds: int
    log_path: Path
    output_text: str = ""
    session_id: Optional[str] = None
    exit_code: Optional[int] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


def model_argv(model: str, prompt: str, *, resume: Optional[str]) -> list[str]:
    if model == "gemini":
        # NOTE: keep CLI args short to avoid Windows command line length limits.
        # Provide the full prompt via stdin (see run_model_once).
        cmd = "gemini.cmd" if os.name == "nt" else "gemini"
        argv = [cmd, "-o", "stream-json", "-y", "-p", ""]
        if resume:
            argv += ["--resume", resume]
        return argv
    if model == "claude":
        argv = [
            "claude",
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--disable-slash-commands",
        ]
        if resume:
            argv += ["--resume", resume]
        return argv
    raise SynapseError(f"Unknown model: {model}")


def parse_stream_json_line(model: str, line: str) -> tuple[Optional[str], Optional[str]]:
    """
    Returns: (delta_text, session_id)
    """
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(obj, dict):
        return None, None

    session_id = obj.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        session_id = None

    if model == "gemini":
        # Only capture assistant output, not the echoed user prompt.
        if obj.get("role") != "assistant":
            return None, session_id
        content = obj.get("content")
        return (content if isinstance(content, str) and content else None), session_id

    if model == "claude":
        result = obj.get("result")
        return (result if isinstance(result, str) and result else None), session_id

    return None, session_id


def run_model_once(run: ModelRun) -> ModelRun:
    start = time.time()
    argv = model_argv(run.model, run.prompt, resume=run.resume)

    safe_mkdir(run.log_path.parent)
    buf: list[str] = []
    final_text: Optional[str] = None
    session_id: Optional[str] = None

    try:
        with run.log_path.open("w", encoding="utf-8", newline="\n") as logf:
            proc = subprocess.Popen(
                argv,
                cwd=str(run.cwd),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            # Send prompt via stdin then close.
            if proc.stdin is not None:
                try:
                    proc.stdin.write(run.prompt)
                    if not run.prompt.endswith("\n"):
                        proc.stdin.write("\n")
                    proc.stdin.close()
                except Exception:
                    pass

            stderr_buf: list[str] = []

            def _read_stderr() -> None:
                if proc.stderr is None:
                    return
                for ln in proc.stderr:
                    stderr_buf.append(ln)

            t = threading.Thread(target=_read_stderr, daemon=True)
            t.start()

            if proc.stdout is None:
                raise SynapseError("No stdout pipe from model process")

            for ln in proc.stdout:
                logf.write(ln)
                ln_stripped = ln.strip()
                if not ln_stripped:
                    continue
                delta, sid = parse_stream_json_line(run.model, ln_stripped)
                if sid and not session_id:
                    session_id = sid
                if not delta:
                    continue
                if run.model == "gemini":
                    buf.append(delta)
                else:
                    final_text = delta

            try:
                proc.wait(timeout=run.timeout_seconds)
            except subprocess.TimeoutExpired:
                proc.kill()
                t.join(timeout=2)
                run.exit_code = None
                run.error = f"timeout after {run.timeout_seconds}s"
                run.duration_seconds = time.time() - start
                run.session_id = session_id
                run.output_text = final_text or "".join(buf)
                return run

            t.join(timeout=5)
            run.exit_code = proc.returncode
            if stderr_buf:
                logf.write("\n")
                logf.write("### STDERR (captured)\n")
                for ln in stderr_buf[-2000:]:
                    logf.write(ln)

    except Exception as e:
        # Ensure the log file contains the error even if the process failed to spawn.
        try:
            safe_mkdir(run.log_path.parent)
            with run.log_path.open("a", encoding="utf-8", newline="\n") as logf:
                logf.write("\n")
                logf.write(f"### SYNAPSE ERROR\n{type(e).__name__}: {e}\n")
        except Exception:
            pass
        run.exit_code = None
        run.error = f"{type(e).__name__}: {e}"
        run.duration_seconds = time.time() - start
        run.session_id = session_id
        run.output_text = final_text or "".join(buf)
        return run

    run.duration_seconds = time.time() - start
    run.session_id = session_id
    run.output_text = "".join(buf) if run.model == "gemini" else (final_text or "")
    return run


def _backoff_sleep(base: float, *, attempt: int, max_seconds: float, jitter: bool) -> None:
    delay = min(max_seconds, base * (2 ** max(0, attempt - 1)))
    if jitter:
        delay = delay * (0.6 + random.random() * 0.8)
    time.sleep(delay)


def run_model_with_retries(
    *,
    model: str,
    prompt: str,
    project_root: Path,
    resume: Optional[str],
    defaults: dict[str, Any],
    slug: str,
    phase: str,
) -> ModelRun:
    runner = defaults.get("runner", {})
    timeout_seconds = int(runner.get("timeout_seconds", 3600))
    retries = int(runner.get("retries", 2))
    backoff_cfg = runner.get("retry_backoff", {})
    base_seconds = float(backoff_cfg.get("base_seconds", 2))
    max_seconds = float(backoff_cfg.get("max_seconds", 30))
    jitter = bool(backoff_cfg.get("jitter", True))

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = synapse_paths(project_root).logs_dir / f"{ts}-{slug}-{phase}-{model}-stream.jsonl"

    last_run: Optional[ModelRun] = None
    for attempt in range(1, retries + 2):
        run = ModelRun(
            model=model,
            prompt=prompt,
            cwd=project_root,
            resume=resume,
            timeout_seconds=timeout_seconds,
            log_path=log_path,
        )
        run = run_model_once(run)
        last_run = run
        ok = run.exit_code == 0 and run.output_text.strip() != ""
        if ok:
            return run
        if attempt <= retries:
            _backoff_sleep(base_seconds, attempt=attempt, max_seconds=max_seconds, jitter=jitter)
            continue
        return run
    return last_run or ModelRun(
        model=model,
        prompt=prompt,
        cwd=project_root,
        resume=resume,
        timeout_seconds=timeout_seconds,
        log_path=log_path,
        error="unknown failure",
    )


def run_model_tasks_parallel(
    tasks: list[dict[str, Any]],
    *,
    defaults: dict[str, Any],
    max_workers: Optional[int] = None,
) -> list[ModelRun]:
    """
    Run multiple model tasks concurrently.

    Each task dict must contain:
      - model, prompt, project_root, resume, slug, phase
    """
    runner = defaults.get("runner", {})
    concurrency = int(runner.get("concurrency", 2))
    workers = max(1, int(max_workers or concurrency or 1))

    results: list[ModelRun] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [
            ex.submit(
                run_model_with_retries,
                model=t["model"],
                prompt=t["prompt"],
                project_root=t["project_root"],
                resume=t.get("resume"),
                defaults=defaults,
                slug=t["slug"],
                phase=t["phase"],
            )
            for t in tasks
        ]
        for fut in as_completed(futs):
            results.append(fut.result())
    return results


def extract_unified_diff(text: str) -> Optional[str]:
    m = re.search(r"```(?:diff|patch)[ \t]*\r?\n(.*?)\r?\n```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        diff = m.group(1).strip("\n") + "\n"
        if "diff --git" in diff or (diff.startswith("---") and "\n+++" in diff):
            return diff
    # 1.5) raw '---/+++' style patch (no diff --git)
    s = text.lstrip()
    if s.startswith("--- ") and "\n+++ " in s and "\n@@ " in s:
        return s.strip("\n") + "\n"
    idx = text.find("diff --git")
    if idx != -1:
        return text[idx:].strip("\n") + "\n"
    return None
