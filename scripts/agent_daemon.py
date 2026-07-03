#!/usr/bin/env python3
"""
BOSS Agent Daemon — runs on Boston's Mac, listens for tasks from the Boston Agent,
fires Claude Code to execute them, reports results to ntfy.

Setup:
  python3 scripts/agent_daemon.py &

Or use the LaunchDaemon (see scripts/com.boss.agent-daemon.plist).

Task format (sent via ntfy topic bossai-agent-tasks):
  {"id": "...", "task": "...", "priority": "high|low"}
"""

import os
import sys
import json
import subprocess
import time
import logging
import hashlib
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError

BOSS_HQ = os.path.expanduser("~/Desktop/BOSS_HQ")
# Daemon I/O lives in ~/Library/Application Support/BOSS (accessible by launchd)
# Claude still executes in BOSS_HQ if it's accessible, otherwise here too
DAEMON_HOME = os.path.expanduser("~/Library/Application Support/BOSS")
NTFY_BASE = "https://ntfy.sh"
NTFY_TASKS_TOPIC = "bossai-agent-tasks"
NTFY_ALERTS_TOPIC = "bossai-bostonrossall-alerts"
LOG_FILE = os.path.join(DAEMON_HOME, "log.json")
PROCESSED_FILE = os.path.join(DAEMON_HOME, "processed_ids.txt")
CLAUDE_BIN = "/usr/local/bin/claude"
# LaunchAgent can't access ~/Desktop (macOS TCC). Use DAEMON_HOME for cwd.
# Grant Full Disk Access to python3 in System Settings to enable BOSS_HQ cwd.
CLAUDE_WORK_DIR = DAEMON_HOME

PERMISSIONS = {
    "allowed": [
        "read_files", "run_scripts", "atlas_scan", "ops_report",
        "lead_engine_discover", "export_dashboards", "git_commit_push",
        "ntfy_alerts", "cost_tracker",
    ],
    "requires_approval": [
        "retell_agent_edit", "n8n_workflow_edit", "spend_over_50",
        "irreversible_delete", "external_api_post",
    ],
    "denied": [
        "retell_agent_delete", "n8n_workflow_delete", "killswitch",
        "call_903_430", "call_louisiana", "real_money_trade",
    ],
}

os.makedirs(DAEMON_HOME, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(DAEMON_HOME, "daemon.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("boss-agent")


def ntfy_send(message: str, title: str = "BOSS Agent", topic: str = NTFY_ALERTS_TOPIC) -> None:
    try:
        safe_title = title.encode("ascii", "replace").decode("ascii")
        req = Request(
            f"{NTFY_BASE}/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": safe_title, "Priority": "default", "Content-Type": "text/plain; charset=utf-8"},
            method="POST",
        )
        urlopen(req, timeout=8)
    except Exception as e:
        log.error(f"ntfy send failed: {e}")


def load_processed() -> set:
    if not os.path.exists(PROCESSED_FILE):
        return set()
    with open(PROCESSED_FILE) as f:
        return set(line.strip() for line in f if line.strip())


def mark_processed(task_id: str) -> None:
    with open(PROCESSED_FILE, "a") as f:
        f.write(task_id + "\n")


def log_action(task_id: str, task: str, output: str, success: bool) -> None:
    entry = {
        "id": task_id,
        "task": task,
        "output": output[:2000],
        "success": success,
        "ts": datetime.utcnow().isoformat(),
    }
    entries = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE) as f:
                entries = json.load(f)
        except Exception:
            entries = []
    entries.insert(0, entry)
    entries = entries[:200]  # keep last 200
    with open(LOG_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def find_claude() -> str:
    """Find claude binary."""
    candidates = [
        CLAUDE_BIN,
        "/usr/bin/claude",
        os.path.expanduser("~/.local/bin/claude"),
        os.path.expanduser("~/.npm-global/bin/claude"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    # Try which
    try:
        result = subprocess.run(["which", "claude"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "claude"


def run_claude_task(task: str) -> tuple[bool, str]:
    """Run a task via Claude Code CLI. Returns (success, output)."""
    claude = find_claude()
    # Inject BOSS_HQ context so claude knows where the project is even if cwd is different
    boss_hq = os.path.expanduser("~/Desktop/BOSS_HQ")
    context_prefix = (
        f"BOSS Systems project is at {boss_hq}. "
        f"CLAUDE.md is at {boss_hq}/CLAUDE.md. "
        f"All scripts are in {boss_hq}/scripts/. "
    ) if not task.startswith("BOSS Systems") else ""
    full_task = context_prefix + task
    cmd = [
        claude,
        "--dangerously-skip-permissions",
        "-p",
        full_task,
    ]
    log.info(f"Running claude task: {task[:100]}...")
    log.info(f"Claude binary: {claude}, cwd: {CLAUDE_WORK_DIR}")
    log.info(f"ENV HOME={os.environ.get('HOME','?')} PATH={os.environ.get('PATH','?')[:60]}")
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max per task
            cwd=CLAUDE_WORK_DIR,
        )
        output = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        success = result.returncode == 0
        log.info(f"Claude exit code: {result.returncode}")
        log.info(f"Claude stdout: {result.stdout[:300]}")
        log.info(f"Claude stderr: {result.stderr[:300]}")
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Claude task timed out after 5 minutes"
    except FileNotFoundError:
        return False, f"Claude CLI not found at '{claude}'. Install Claude Code first."
    except Exception as e:
        return False, f"Error running claude: {e}"


def process_task(msg: dict, processed: set) -> None:
    task_id = msg.get("id") or hashlib.md5(msg.get("task", "").encode()).hexdigest()[:12]
    if task_id in processed:
        log.info(f"Already processed task {task_id}, skipping")
        return

    task = msg.get("task", "").strip()
    if not task:
        log.warning(f"Empty task in message: {msg}")
        return

    priority = msg.get("priority", "low")
    log.info(f"[{priority.upper()}] Processing task {task_id}: {task[:80]}")

    ntfy_send(f"Starting task:\n{task[:200]}", title="BOSS Agent — Working")

    success, output = run_claude_task(task)
    mark_processed(task_id)
    log_action(task_id, task, output, success)

    status = "✅ Done" if success else "❌ Failed"
    ntfy_msg = f"{status} [{task_id}]\n\nTask: {task[:150]}\n\nResult: {output[:500]}"
    ntfy_send(ntfy_msg, title=f"BOSS Agent — {status}")

    log.info(f"Task {task_id} {'succeeded' if success else 'failed'}: {output[:200]}")


def subscribe_ntfy() -> None:
    """Subscribe to ntfy topic via SSE stream and process tasks."""
    url = f"{NTFY_BASE}/{NTFY_TASKS_TOPIC}/sse"
    log.info(f"Subscribing to ntfy topic: {NTFY_TASKS_TOPIC}")
    processed = load_processed()

    while True:
        try:
            req = Request(url, headers={"Accept": "text/event-stream"})
            with urlopen(req, timeout=3600) as resp:
                buffer = ""
                for line in resp:
                    try:
                        text = line.decode("utf-8").strip()
                    except Exception:
                        continue

                    if not text:
                        if buffer.strip():
                            for chunk in buffer.split("\n"):
                                chunk = chunk.strip()
                                if chunk.startswith("data:"):
                                    data_str = chunk[5:].strip()
                                    try:
                                        data = json.loads(data_str)
                                        event_type = data.get("event", "")
                                        if event_type == "message":
                                            payload_str = data.get("message", "{}")
                                            try:
                                                payload = json.loads(payload_str)
                                                process_task(payload, processed)
                                                processed = load_processed()
                                            except json.JSONDecodeError:
                                                # Treat raw message text as the task
                                                process_task({"task": payload_str}, processed)
                                                processed = load_processed()
                                    except json.JSONDecodeError:
                                        pass
                        buffer = ""
                    else:
                        buffer += text + "\n"

        except URLError as e:
            log.warning(f"ntfy stream disconnected: {e}. Reconnecting in 30s...")
            time.sleep(30)
        except KeyboardInterrupt:
            log.info("Daemon stopped by user.")
            break
        except Exception as e:
            log.error(f"Unexpected error: {e}. Reconnecting in 60s...")
            time.sleep(60)


def main():
    os.makedirs(DAEMON_HOME, exist_ok=True)
    log.info("BOSS Agent Daemon starting...")
    ntfy_send("BOSS Agent Daemon is online and listening for tasks.", title="BOSS Agent — Online")
    subscribe_ntfy()


if __name__ == "__main__":
    main()
