import json
import os
import subprocess
import sys
from pathlib import Path

from . import policy
from .policy import ComparisonError, MAX_RESULT_BYTES

ROOT = Path(__file__).resolve().parents[2]


def run_worker(folder, items):
    (folder / "manifest.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    # The parser needs no database credentials, API keys or inherited Python paths.
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
    env["PYTHONUTF8"] = "1"
    with subprocess.Popen(
        [sys.executable, "-m", "backend.comparison.worker", str(folder)], cwd=ROOT,
        env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    ) as process:
        try:
            process.wait(timeout=policy.WORKER_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise ComparisonError("timeout", f"Qayta ishlash {policy.WORKER_SECONDS:g} soniya chegarasidan oshdi.", 422) from None
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        output = folder / "result.json"
        if process.returncode or not output.exists() or output.stat().st_size > MAX_RESULT_BYTES:
            raise ComparisonError("resource_limit", "Parser to‘xtadi yoki resurs chegarasidan oshdi.")
        result = json.loads(output.read_text(encoding="utf-8"))
        if "error" in result:
            error = result["error"]
            raise ComparisonError(error["code"], error["message"], result.get("http_status", 422), error.get("file"))
        return result
