from __future__ import annotations
import datetime as _dt
import json
import queue
import random
import re
import subprocess
import shutil
import threading
import time
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Optional
from .common import SynapseError, WriteGuard, safe_mkdir, synapse_paths, unique_path

@dataclass
class ModelRun:
    model: str
    prompt: str
    cwd: Path
    resume: Optional[str]
    timeout_seconds: int
    log_path: Path
    max_line_bytes: int
    guard: Optional[WriteGuard] = None
    output_text: str = ""
    session_id: Optional[str] = None
    exit_code: Optional[int] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    truncated_stdout_lines: int = 0
    truncated_stderr_lines: int = 0

def model_argv(model: str, *, resume: Optional[str]) -> list[str]:
    if model == "gemini":
        cmd = "gemini"
        if os.name == "nt" and shutil.which("gemini.cmd"):
            cmd = "gemini.cmd"
        argv = [cmd, "-o", "stream-json", "--approval-mode", "default", "-p", ""]
        if resume:
            argv += ["--resume", resume]
        return argv
    if model == "claude":
        cmd = "claude"
        if os.name == "nt" and shutil.which("claude.cmd"):
            cmd = "claude.cmd"
        argv = [
            cmd,
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--disable-slash-commands",
            "--permission-mode",
            "plan",
            "--tools",
            "",
            "--strict-mcp-config",
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
    argv = model_argv(run.model, resume=run.resume)
    if run.guard:
        run.guard.assert_allowed(run.log_path)
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
            if proc.stdin is not None:
                try:
                    proc.stdin.write(run.prompt)
                    if not run.prompt.endswith("\n"):
                        proc.stdin.write("\n")
                    proc.stdin.close()
                except Exception:
                    pass

            if proc.stdout is None:
                raise SynapseError("No stdout pipe from model process")

            sentinel = object()
            stdout_q: queue.Queue[object] = queue.Queue()
            stderr_q: queue.Queue[object] = queue.Queue()

            def _read_pipe(pipe, q: queue.Queue[object]) -> None:
                if pipe is None:
                    q.put(sentinel)
                    return
                try:
                    for ln in pipe:
                        q.put(ln)
                finally:
                    q.put(sentinel)

            t_out = threading.Thread(target=_read_pipe, args=(proc.stdout, stdout_q), daemon=True)
            t_err = threading.Thread(target=_read_pipe, args=(proc.stderr, stderr_q), daemon=True)
            t_out.start()
            t_err.start()

            stdout_done = False
            stderr_done = False
            timed_out = False
            deadline = time.monotonic() + run.timeout_seconds

            while True:
                if not timed_out and time.monotonic() > deadline and proc.poll() is None:
                    timed_out = True
                    try:
                        proc.kill()
                    except Exception:
                        pass

                try:
                    item = stdout_q.get(timeout=0.05)
                except queue.Empty:
                    item = None

                if item is sentinel:
                    stdout_done = True
                elif isinstance(item, str):
                    ln = item
                    if run.max_line_bytes > 0:
                        b = ln.encode("utf-8", errors="replace")
                        if len(b) > run.max_line_bytes:
                            run.truncated_stdout_lines += 1
                            prefix = b[: run.max_line_bytes].decode("utf-8", errors="replace")
                            logf.write(
                                json.dumps(
                                    {
                                        "type": "synapse",
                                        "subtype": "stdout_truncated",
                                        "original_bytes": len(b),
                                        "limit_bytes": run.max_line_bytes,
                                        "prefix": prefix,
                                    },
                                    ensure_ascii=False,
                                )
                                + "\n"
                            )
                            continue
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

                for _ in range(200):
                    try:
                        eitem = stderr_q.get_nowait()
                    except queue.Empty:
                        break
                    if eitem is sentinel:
                        stderr_done = True
                        break
                    if not isinstance(eitem, str):
                        continue
                    ln = eitem
                    if run.max_line_bytes > 0:
                        b = ln.encode("utf-8", errors="replace")
                        if len(b) > run.max_line_bytes:
                            run.truncated_stderr_lines += 1
                            prefix = b[: run.max_line_bytes].decode("utf-8", errors="replace")
                            logf.write(
                                json.dumps(
                                    {
                                        "type": "synapse",
                                        "subtype": "stderr_truncated",
                                        "original_bytes": len(b),
                                        "limit_bytes": run.max_line_bytes,
                                        "prefix": prefix,
                                    },
                                    ensure_ascii=False,
                                )
                                + "\n"
                            )
                            continue
                    logf.write(
                        json.dumps(
                            {"type": "stderr", "content": ln.rstrip("\r\n")},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

                if stdout_done and stderr_done and proc.poll() is not None:
                    break
                if timed_out and proc.poll() is None and time.monotonic() > deadline + 5:
                    break

            if proc.poll() is None:
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=1)
                    except Exception:
                        pass

            t_out.join(timeout=2)
            t_err.join(timeout=2)

            if timed_out:
                run.exit_code = None
                run.error = f"timeout after {run.timeout_seconds}s"
                run.duration_seconds = time.time() - start
                run.session_id = session_id
                run.output_text = final_text or "".join(buf)
                return run

            run.exit_code = proc.returncode

    except Exception as e:
        try:
            if run.guard:
                run.guard.assert_allowed(run.log_path)
            safe_mkdir(run.log_path.parent)
            with run.log_path.open("a", encoding="utf-8", newline="\n") as logf:
                logf.write(
                    json.dumps(
                        {
                            "type": "synapse_error",
                            "error_type": type(e).__name__,
                            "message": str(e),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
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
    run_ts: Optional[str] = None,
) -> ModelRun:
    runner = defaults.get("runner", {})
    timeout_seconds = int(runner.get("timeout_seconds", 3600))
    retries = max(0, int(runner.get("retries", 2)))
    backoff_cfg = runner.get("retry_backoff", {})
    base_seconds = float(backoff_cfg.get("base_seconds", 2))
    max_seconds = float(backoff_cfg.get("max_seconds", 30))
    jitter = bool(backoff_cfg.get("jitter", True))
    stream_json = runner.get("stream_json", {})
    max_line_bytes = int(stream_json.get("max_line_bytes", 10_485_760)) if isinstance(stream_json, dict) else 10_485_760
    if max_line_bytes <= 0:
        max_line_bytes = 10_485_760

    guard = WriteGuard.from_defaults(project_root=project_root, defaults=defaults)

    ts = (run_ts or "").strip() or _dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    for attempt in range(1, retries + 2):
        attempt_suffix = "" if attempt == 1 else f"-attempt{attempt}"
        base_log_path = synapse_paths(project_root).logs_dir / f"{ts}-{slug}-{phase}-{model}-stream{attempt_suffix}.jsonl"
        log_path = unique_path(base_log_path)
        guard.assert_allowed(log_path)
        run = ModelRun(
            model=model,
            prompt=prompt,
            cwd=project_root,
            resume=resume,
            timeout_seconds=timeout_seconds,
            log_path=log_path,
            max_line_bytes=max_line_bytes,
            guard=guard,
        )
        run = run_model_once(run)
        if run.exit_code == 0 and run.output_text.strip() == "" and not run.error:
            run.error = "exit_code=0 but no assistant output parsed from stream-json"
        ok = run.exit_code == 0 and run.output_text.strip() != ""
        if ok:
            return run
        if attempt <= retries:
            _backoff_sleep(base_seconds, attempt=attempt, max_seconds=max_seconds, jitter=jitter)
            continue
        return run
    raise AssertionError("unreachable")

def extract_unified_diff(text: str) -> Optional[str]:
    m = re.search(r"```(?:diff|patch)[ \t]*\r?\n(.*?)\r?\n```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        diff = m.group(1).strip("\n") + "\n"
        if "diff --git" in diff or (diff.startswith("---") and "\n+++" in diff):
            return diff
    for m2 in re.finditer(r"^--- .*$", text, flags=re.MULTILINE):
        s = text[m2.start() :].strip("\n")
        if "\n+++ " in s and "\n@@ " in s:
            return s + "\n"
    idx = text.find("diff --git")
    if idx != -1:
        return text[idx:].strip("\n") + "\n"
    return None
