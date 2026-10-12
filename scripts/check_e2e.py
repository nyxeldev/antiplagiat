"""Run synthetic real HTTP checks against owned loopback production servers.

Run from the project root with .venv/Scripts/python.exe scripts/check_e2e.py.
Build frontend first. No database, private files, browser or external HTTP needed.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.tests.fixtures import TEXT, docx, pdf, multipart  # noqa: E402
from backend.comparison.matching import ARABIC_WARNING, INVISIBLE_WARNING  # noqa: E402

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(url, body=None, content_type=None, headers=None):
    supplied = dict(headers or {})
    if content_type:
        supplied["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=supplied)
    try:
        response = OPENER.open(req, timeout=100)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        content = response.read()
        if "application/json" in response.headers.get("Content-Type", ""):
            content = json.loads(content)
        return response.status, content


def wait_for(process, url):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Owned test server exited during startup")
        try:
            if request(url)[0] == 200:
                return
        except (OSError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError("Owned test server did not start")


def main():
    if not (ROOT / "frontend/.next/BUILD_ID").exists():
        raise RuntimeError("Run npm.cmd run build in frontend first")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is unavailable")
    processes = []
    checks = 0
    with tempfile.TemporaryDirectory(prefix="antiplagiat-e2e-") as scratch:
        scratch = Path(scratch)
        env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH"}}
        env.update(TEMP=str(scratch), TMP=str(scratch), PYTHONUTF8="1", NEXT_TELEMETRY_DISABLED="1")
        backend_port = free_port()
        frontend_port = free_port()
        while frontend_port == backend_port:
            frontend_port = free_port()
        backend = f"http://127.0.0.1:{backend_port}"
        frontend = f"http://127.0.0.1:{frontend_port}"
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(backend_port), "--no-access-log"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags))
            wait_for(processes[-1], backend + "/health")
            processes.append(subprocess.Popen([node, "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", str(frontend_port)], cwd=ROOT / "frontend", env={**env, "NODE_ENV": "production", "ANTIPLAGIAT_API_URL": backend}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags))
            wait_for(processes[-1], frontend)
            status, html = request(frontend)
            assert status == 200 and "Islom akademiyasi — Antiplagiat" in html.decode()
            assert b'lang="uz"' in html
            checks += 1
            assert request(backend + "/health") == (200, {"status": "ok"})
            assert request(backend + "/ready") == (503, {"status": "not_ready"})
            checks += 2

            def upload(files, expected_status=200, code=None, percent=None, extra_headers=None):
                nonlocal checks
                body, kind = multipart(files)
                status, result = request(frontend + "/api/compare", body, kind, {"X-Antiplagiat-Local": "1", **(extra_headers or {})})
                assert status == expected_status, (status, result.get("error"))
                if code:
                    assert result["error"]["code"] == code, result["error"]
                    assert "coverage_percent" not in result
                if percent is not None:
                    assert result["coverage_percent"] == percent, result["coverage_percent"]
                    for source in result["sources"]:
                        for match in source["matches"]:
                            for key, doc in [("document", result["document"]), ("source", source)]:
                                span = match[key]
                                assert doc["text"][span["start"]:span["end"]] == span["text"]
                assert not list(scratch.glob("antiplagiat-*")), "Temporary upload files leaked"
                checks += 1
                return result

            target = ("document", "target.txt", TEXT.encode())
            for name, data in [("source.txt", TEXT.encode()), ("source.docx", docx()), ("source.pdf", pdf())]:
                upload([target, ("sources", name, data)], percent=100)
            upload([target, ("sources", "other.txt", b"osmon dengiz toglar qushlar yomgir daraxt")], percent=0)
            part = b"bir ikki uch tort besh olti"
            upload([("document", "partial.txt", part + b" yetti sakkiz toqqiz on"), ("sources", "one.txt", part), ("sources", "two.txt", part)], percent=60)
            upload([("document", "unicode.txt", "😀 O‘ZBEK  gʻoya\nmaʼno cafe\u0301 ＡＢＣ Straße".encode()), ("sources", "normal.txt", "o'zbek g'oya ma'no café abc strasse".encode())], percent=100)
            clean = "lotin matn uchun aniq manba nusxa"
            for invisible in ("\u200b", "\u00ad", "\u200c", "\ufeff", "\u200b\u00ad\u200c\ufeff"):
                changed = clean.replace("lotin", "lo" + invisible + "tin")
                result = upload([("document", "changed.txt", changed.encode()),
                                 ("sources", "clean.txt", clean.encode())], percent=100)
                assert result["document"]["text"] == changed
                assert result["sources"][0]["matches"][0]["method"] == "shingle"
                assert INVISIBLE_WARNING in result["limitations"]
                assert result["parameters"]["normalization_version"] == "uz-latin-v2"
            for text, warning in [("هذا نص عربي واضح للاختبار فقط", False),
                                  ("هَذا نص عربي واضح للاختبار فقط", True)]:
                result = upload([("document", "arabic.txt", text.encode()),
                                 ("sources", "same.txt", text.encode())], percent=100)
                assert (ARABIC_WARNING in result["limitations"]) == warning
                assert result["document"]["text"] == text
            unsafe = b"<script>alert('synthetic')</script> bir ikki uch tort besh"
            escaped = upload([("document", "safe.txt", unsafe), ("sources", "source.txt", unsafe)], percent=100)
            assert escaped["document"]["text"] == unsafe.decode()
            cases = [(b"", "empty.txt", "empty", 422), (b"broken", "broken.docx", "corrupt", 422),
                     (pdf(text="", scan=True), "scan.pdf", "no_text_layer", 422),
                     (pdf(encrypted=True), "locked.pdf", "encrypted", 422),
                     (b"invalid", "bad.exe", "unsupported", 415), (b"\xff", "bad.txt", "encoding", 422),
                     (b"x" * (10 * 1024 * 1024 + 1), "large.txt", "file_limit", 413)]
            for data, name, code, status in cases:
                upload([("document", name, data), ("sources", "source.txt", TEXT.encode())], status, code)
            upload([target], 400, "file_count")
            upload([target, ("sources", "source.txt", TEXT.encode())], 403, extra_headers={"Origin": "https://example.invalid"})
            body, kind = multipart([target, ("sources", "source.txt", TEXT.encode())])
            assert request(backend + "/compare", body, kind)[0] == 403
            checks += 1
            print(f"PASS: {checks} real HTTP checks; production frontend -> FastAPI -> worker -> report.")
            print("Three formats, exact/different/partial/duplicate/Unicode, invisible runs, Arabic warnings, policy version, offsets, errors, limits, local-only and cleanup verified.")
            print(f"Owned loopback ports: backend={backend_port}, frontend={frontend_port}")
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            print("Owned test servers stopped.")


if __name__ == "__main__":
    main()
