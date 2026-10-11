"""Excerpt: run user code as a subprocess and kill the whole process tree on timeout.

Context: automation scripts sometimes launch a headless browser. Killing only the
Python child leaves orphan chromium processes eating the server. Starting the child
in its own session gives it its own process group, so one kill takes everything.
"""
import os
import signal
import subprocess


def run_script(cmd, env, timeout):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, env=env, start_new_session=True)  # own process group
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        killpg(p)
        out, err = p.communicate()
        return {"error": f"timed out ({timeout}s)", "stdout": (out or "")[-8000:]}
    return {"ok": p.returncode == 0, "stdout": (out or "")[-8000:], "stderr": (err or "")[-8000:]}


def killpg(p):
    """Kill a process and its whole group (orphaned children included)."""
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            p.kill()
        except OSError:
            pass
