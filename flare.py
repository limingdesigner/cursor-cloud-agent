#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""焰口：用 codex666 的 gpt-image-2.5-flare 出图。

参数与此前测试一致，只接收提示词：

    POST https://codex666ai.com/v1/images/generations
    {
      "model": "gpt-image-2.5-flare",
      "prompt": "<提示词>",
      "size": "1024x576",
      "quality": "medium",
      "response_format": "url"
    }

用法：
    python3 flare.py                  打开本地页面，输入提示词出图
    python3 flare.py "一只红灯笼"      命令行出图，文件写到 flare-out/
"""

from __future__ import annotations

import json
import os
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY_FILE = ROOT / ".flare-key"
OUT_DIR = ROOT / "flare-out"

API_URL = "https://codex666ai.com/v1/images/generations"
MODEL = "gpt-image-2.5-flare"
SIZE = "1024x576"
QUALITY = "medium"
RESPONSE_FORMAT = "url"
TIMEOUT = 180

HOST = "127.0.0.1"
PORT = 8765


def load_key() -> str:
    env = os.environ.get("CODEX666_API_KEY", "").strip()
    if env:
        return env
    if KEY_FILE.is_file():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    return ""


def save_key(key: str) -> None:
    KEY_FILE.write_text(key.strip() + "\n", encoding="utf-8")
    try:
        KEY_FILE.chmod(0o600)
    except OSError:
        pass


def png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    return None


def build_body(prompt: str) -> dict:
    return {
        "model": MODEL,
        "prompt": prompt,
        "size": SIZE,
        "quality": QUALITY,
        "response_format": RESPONSE_FORMAT,
    }


def generate(prompt: str, key: str | None = None) -> dict:
    text = prompt.strip()
    if not text:
        raise ValueError("提示词是空的")
    if len(text) > 4000:
        raise ValueError("提示词超过 4000 字")
    token = (key or load_key()).strip()
    if not token:
        raise ValueError("还没有密钥。在页面里填一次，或设置 CODEX666_API_KEY")

    body = build_body(text)
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"接口返回 {err.code}：{detail[:800]}") from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"连不上 codex666ai.com：{err.reason}") from err
    elapsed = time.perf_counter() - started

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as err:
        raise RuntimeError(f"接口返回的不是 JSON（HTTP {status}）") from err

    data = payload.get("data") or []
    if not data or not isinstance(data, list):
        raise RuntimeError(f"响应里没有图片：{json.dumps(payload, ensure_ascii=False)[:800]}")
    item = data[0]
    image_url = item.get("url") or ""
    b64 = item.get("b64_json") or ""
    if image_url.startswith("data:"):
        comma = image_url.find(",")
        import base64

        image = base64.b64decode(image_url[comma + 1 :])
    elif b64:
        import base64

        image = base64.b64decode(b64)
        image_url = ""
    elif image_url.startswith("http://") or image_url.startswith("https://"):
        try:
            with urllib.request.urlopen(image_url, timeout=60) as img_resp:
                image = img_resp.read()
        except urllib.error.URLError as err:
            raise RuntimeError(f"图片链接下载失败：{err.reason}") from err
    else:
        raise RuntimeError("响应里既没有图片链接，也没有 base64")

    OUT_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"flare-{stamp}.png"
    path = OUT_DIR / filename
    # Avoid clobbering a same-second file.
    n = 2
    while path.exists():
        filename = f"flare-{stamp}-{n}.png"
        path = OUT_DIR / filename
        n += 1
    path.write_bytes(image)
    width, height = png_size(image) or (None, None)
    usage = payload.get("usage") or {}
    return {
        "file": filename,
        "path": str(path),
        "bytes": len(image),
        "elapsed": round(elapsed, 2),
        "width": width,
        "height": height,
        "model": payload.get("model") or MODEL,
        "size": payload.get("size") or SIZE,
        "quality": payload.get("quality") or QUALITY,
        "output_tokens": (usage.get("output_tokens") if isinstance(usage, dict) else None),
        "remote_url": image_url if image_url.startswith("http") else "",
        "request": body,
    }


PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>焰口 · flare</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,520;9..144,680&family=IBM+Plex+Mono:wght@400;500&family=Noto+Sans+SC:wght@420;560&display=swap" rel="stylesheet" />
<style>
  :root {
    --ink: #1a120c;
    --paper: #f3e6d4;
    --paper-2: #efe0c8;
    --ember: #e4572e;
    --ember-deep: #9c2f16;
    --gold: #e7b15a;
    --soot: #2a211b;
    --line: rgba(26, 18, 12, 0.14);
    --shadow: 0 24px 60px rgba(40, 16, 6, 0.28);
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; min-height: 100%; }
  body {
    color: var(--ink);
    font-family: "Noto Sans SC", sans-serif;
    background:
      radial-gradient(900px 480px at 12% -10%, rgba(228, 87, 46, 0.38), transparent 60%),
      radial-gradient(700px 420px at 100% 0%, rgba(231, 177, 90, 0.28), transparent 55%),
      linear-gradient(165deg, #2c2118 0%, #14100d 48%, #1c1410 100%);
    min-height: 100vh;
  }
  body::before {
    content: "";
    pointer-events: none;
    position: fixed;
    inset: 0;
    opacity: 0.18;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='.55'/></svg>");
    mix-blend-mode: overlay;
  }
  main {
    position: relative;
    max-width: 1120px;
    margin: 0 auto;
    padding: 36px 22px 64px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 24px;
    margin-bottom: 28px;
    color: var(--paper);
  }
  .mark {
    font-family: Fraunces, serif;
    font-weight: 680;
    font-size: clamp(52px, 8vw, 92px);
    line-height: 0.85;
    letter-spacing: -0.04em;
    margin: 0;
  }
  .mark span { color: var(--gold); }
  .lede {
    max-width: 340px;
    margin: 0;
    font-size: 14px;
    line-height: 1.65;
    color: rgba(243, 230, 212, 0.78);
  }
  .slate {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 14px 0 0;
  }
  .slate b {
    font-family: "IBM Plex Mono", monospace;
    font-weight: 500;
    font-size: 12px;
    letter-spacing: 0.02em;
    color: var(--ink);
    background: var(--gold);
    padding: 4px 8px;
  }
  .stage {
    display: grid;
    grid-template-columns: minmax(280px, 380px) 1fr;
    gap: 18px;
    align-items: start;
  }
  .panel, .frame {
    background: var(--paper);
    border-radius: 6px 28px 6px 6px;
    box-shadow: var(--shadow);
  }
  .panel { padding: 22px 22px 18px; }
  label {
    display: block;
    font-size: 12px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ember-deep);
    margin-bottom: 8px;
  }
  textarea, input[type="password"] {
    width: 100%;
    border: 1px solid var(--line);
    background: rgba(255, 252, 246, 0.72);
    color: var(--ink);
    font: 16px/1.55 "Noto Sans SC", sans-serif;
    padding: 12px 14px;
    resize: vertical;
    border-radius: 2px;
  }
  textarea { min-height: 180px; }
  textarea:focus, input:focus { outline: 2px solid var(--ember); border-color: transparent; }
  .row { display: flex; gap: 10px; align-items: center; margin-top: 14px; }
  button {
    appearance: none;
    border: 0;
    cursor: pointer;
    background: var(--ember);
    color: #fffaf4;
    font-family: Fraunces, serif;
    font-size: 22px;
    letter-spacing: 0.04em;
    padding: 10px 22px 12px;
    border-radius: 999px;
  }
  button:disabled { opacity: 0.55; cursor: progress; }
  button.ghost {
    background: transparent;
    color: var(--ink);
    border: 1px solid var(--line);
    font-family: "Noto Sans SC", sans-serif;
    font-size: 14px;
    padding: 8px 12px;
  }
  .status {
    font-family: "IBM Plex Mono", monospace;
    font-size: 12px;
    color: var(--ember-deep);
    min-height: 1.2em;
  }
  .keybox { margin-top: 18px; padding-top: 14px; border-top: 1px dashed var(--line); }
  .keybox p { margin: 0 0 8px; font-size: 13px; line-height: 1.5; }
  .frame {
    min-height: 420px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
  }
  .frame::after {
    content: "";
    position: absolute;
    width: 220px;
    height: 220px;
    right: -60px;
    top: -80px;
    background: radial-gradient(circle, rgba(228, 87, 46, 0.45), transparent 68%);
    pointer-events: none;
  }
  .viewport {
    flex: 1;
    background:
      linear-gradient(180deg, rgba(26,18,12,0.04), transparent 30%),
      repeating-linear-gradient(90deg, transparent, transparent 18px, rgba(26,18,12,0.03) 19px);
    border: 1px solid var(--line);
    min-height: 320px;
    display: grid;
    place-items: center;
    position: relative;
  }
  .viewport img {
    width: 100%;
    height: auto;
    display: block;
    max-height: 640px;
    object-fit: contain;
    background: #111;
  }
  .empty {
    text-align: center;
    padding: 24px;
    color: rgba(26, 18, 12, 0.55);
    font-family: Fraunces, serif;
    font-size: 28px;
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin-top: 12px;
    font-family: "IBM Plex Mono", monospace;
    font-size: 12px;
  }
  .meta a { color: var(--ember-deep); }
  .err {
    color: #fff6ee;
    background: var(--ember-deep);
    padding: 12px 14px;
    font-size: 14px;
    line-height: 1.5;
  }
  @media (max-width: 860px) {
    .stage { grid-template-columns: 1fr; }
    header { flex-direction: column; align-items: flex-start; }
    .frame { min-height: 0; }
  }
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1 class="mark">焰<span>口</span></h1>
      <div class="slate">
        <b>gpt-image-2.5-flare</b>
        <b>1024×576</b>
        <b>quality medium</b>
        <b>16:9</b>
      </div>
    </div>
    <p class="lede">只写提示词。模型、尺寸、画质都锁在上次 codex666 测试那一组上，出图后直接显示在右边。</p>
  </header>
  <div class="stage">
    <section class="panel">
      <label for="prompt">提示词</label>
      <textarea id="prompt" placeholder="画一张某高中科创社在星光集市上的宣传海报"></textarea>
      <div class="row">
        <button id="go" type="button">出图</button>
        <span class="status" id="status"></span>
      </div>
      <div class="keybox" id="keybox" hidden>
        <p>本机还没有密钥。填一次就存在本地 <code>.flare-key</code>，不会出现在页面源码里。</p>
        <input id="key" type="password" placeholder="sk-..." autocomplete="off" />
        <div class="row">
          <button class="ghost" id="savekey" type="button">保存密钥</button>
        </div>
      </div>
    </section>
    <section class="frame">
      <div class="viewport" id="viewport">
        <div class="empty">还没有画面</div>
      </div>
      <div class="meta" id="meta"></div>
    </section>
  </div>
</main>
<script>
const promptEl = document.getElementById("prompt");
const go = document.getElementById("go");
const statusEl = document.getElementById("status");
const viewport = document.getElementById("viewport");
const meta = document.getElementById("meta");
const keybox = document.getElementById("keybox");

async function refreshKey() {
  const res = await fetch("/api/key");
  const data = await res.json();
  keybox.hidden = !!data.present;
}
refreshKey();

document.getElementById("savekey").onclick = async () => {
  const key = document.getElementById("key").value.trim();
  if (!key) return;
  const res = await fetch("/api/key", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
  if (!res.ok) {
    statusEl.textContent = "密钥没保存上";
    return;
  }
  document.getElementById("key").value = "";
  keybox.hidden = true;
  statusEl.textContent = "密钥已留在本机";
};

go.onclick = async () => {
  const prompt = promptEl.value.trim();
  if (!prompt) {
    statusEl.textContent = "先写提示词";
    return;
  }
  go.disabled = true;
  statusEl.textContent = "正在出图…";
  meta.innerHTML = "";
  viewport.innerHTML = '<div class="empty">曝光中</div>';
  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "出图失败");
    viewport.innerHTML = `<img alt="生成结果" src="/outputs/${encodeURIComponent(data.file)}?t=${Date.now()}" />`;
    const dims = data.width && data.height ? `${data.width}×${data.height}` : data.size;
    statusEl.textContent = `${data.elapsed}s`;
    meta.innerHTML = `
      <span>${dims}</span>
      <span>${(data.bytes / 1024).toFixed(0)} KB</span>
      <span>${data.model}</span>
      <a href="/outputs/${encodeURIComponent(data.file)}" download>下载</a>
    `;
  } catch (err) {
    viewport.innerHTML = `<div class="err">${err.message}</div>`;
    statusEl.textContent = "失败";
    if (String(err.message).includes("密钥")) keybox.hidden = false;
  } finally {
    go.disabled = false;
  }
};

promptEl.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") go.click();
});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Flare/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 1_000_000:
            raise ValueError("请求太大")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("请求体必须是对象")
        return data

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/key":
            self._json(200, {"present": bool(load_key())})
            return
        if path.startswith("/outputs/"):
            name = Path(path[len("/outputs/") :]).name
            file_path = OUT_DIR / name
            if not file_path.is_file() or file_path.suffix.lower() != ".png":
                self._json(404, {"error": "没有这张图"})
                return
            self._send(200, file_path.read_bytes(), "image/png")
            return
        self._json(404, {"error": "没有这个地址"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            data = self._read_json()
        except (ValueError, json.JSONDecodeError) as err:
            self._json(400, {"error": str(err)})
            return
        if path == "/api/key":
            key = str(data.get("key") or "").strip()
            if not key.startswith("sk-") or len(key) < 20:
                self._json(400, {"error": "密钥格式不对"})
                return
            save_key(key)
            self._json(200, {"ok": True})
            return
        if path == "/api/generate":
            try:
                result = generate(str(data.get("prompt") or ""))
            except (ValueError, RuntimeError) as err:
                self._json(400, {"error": str(err)})
                return
            self._json(200, result)
            return
        self._json(404, {"error": "没有这个地址"})


def serve(open_browser: bool) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"焰口已开：{url}")
    print("参数锁定：gpt-image-2.5-flare / 1024x576 / quality=medium / response_format=url")
    if not load_key():
        print("还没有密钥。在页面里填一次，或 export CODEX666_API_KEY=...")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "--serve":
        serve(open_browser="--no-browser" not in argv)
        return 0
    if argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    prompt = " ".join(a for a in argv if a != "--no-browser").strip()
    try:
        result = generate(prompt)
    except (ValueError, RuntimeError) as err:
        print(err, file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in result.items() if k != "request"}, ensure_ascii=False, indent=2))
    print("请求体：")
    print(json.dumps(result["request"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
