"""JinDou Cloud 首次部署可视化配置向导。

在宿主机以纯 Python 标准库运行，不依赖项目 venv 或任何容器：
    python3 scripts/config-wizard/config-wizard.py [--host 0.0.0.0] [--port 8642]

解析仓库根目录 .env.example 生成分组表单，校验后原子写入 .env
（写前自动备份为 .env.bak.<时间戳>）。
"""

import argparse
import html
import json
import os
import re
import secrets
import shutil
import string
import tempfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

GROUP_RE = re.compile(r"^#\s*[-=]+\s*(.+?)\s*[-=]+\s*$")
KEY_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$")
COMMENT_KEYS = ("SECRET", "PASSWORD", "TOKEN", "ENCRYPT_KEY", "METRICS_TOKEN")
REQUIRED_KEYS = ("SECRET_KEY", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY")
STD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*_-"


def default_root() -> Path:
    return Path(os.path.dirname(os.path.abspath(__file__))).resolve().parent.parent


def random_password(length: int = 40) -> str:
    return "".join(secrets.choice(STD_ALPHABET) for _ in range(length))


def random_secret(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


class Field:
    def __init__(self, key, default, group, hint, required, sensitive):
        self.key = key
        self.default = default
        self.group = group
        self.hint = hint
        self.required = required
        self.sensitive = sensitive

    def to_dict(self):
        return {
            "key": self.key,
            "default": self.default,
            "group": self.group,
            "hint": self.hint,
            "required": self.required,
            "sensitive": self.sensitive,
        }


def parse_env_example(root: Path) -> list[dict]:
    example = root / ".env.example"
    if not example.exists():
        raise FileNotFoundError(f"缺少 {example}")
    groups: list[dict] = []
    current_group = "基础"
    current_hint = ""
    fields: list[dict] = []
    last_hint = ""
    for raw in example.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line:
            current_hint = ""
            continue
        m = GROUP_RE.match(line)
        if m:
            current_group = m.group(1).strip()
            current_hint = ""
            continue
        trangroup = line.startswith("#") and ("=====" in line or "-----" in line)
        if line.lstrip().startswith("#"):
            if not trangroup:
                hint = line.lstrip()[1:].strip()
                if hint:
                    last_hint = hint
            continue
        if line.startswith("#"):
            continue
        km = KEY_RE.match(line)
        if not km:
            continue
        key, default = km.group(1), km.group(2)
        upper = key.upper()
        sensitive = any(tok in upper for tok in COMMENT_KEYS)
        required = key in REQUIRED_KEYS
        hint = last_hint
        last_hint = ""
        field = Field(key, default, current_group, hint, required, sensitive)
        if current_group not in [g["name"] for g in groups]:
            groups.append({"name": current_group, "fields": []})
        for g in groups:
            if g["name"] == current_group:
                g["fields"].append(field.to_dict())
                break
    return groups


def validate(values: dict) -> list[str]:
    errors = []
    if not values.get("SECRET_KEY"):
        errors.append("SECRET_KEY 不能为空")
    else:
        sk = values["SECRET_KEY"]
        if len(sk) < 32:
            errors.append("SECRET_KEY 必须不少于 32 字符")
        if any(w in sk.lower() for w in ("change", "placeholder", "example")):
            errors.append("SECRET_KEY 疑似占位符/弱口令，请点击「随机生成」")
    for req in REQUIRED_KEYS:
        if req in values and not values.get(req):
            errors.append(f"{req} 不能为空")
    return errors


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JinDou Cloud 部署配置向导</title>
<style>
  :root { --bg:#0f1419; --card:#1a222c; --line:#2a3543; --fg:#e6edf3;
          --muted:#8b98a5; --accent:#3b82f6; --ok:#22c55e; --err:#ef4444; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font:14px/1.6 -apple-system,Segoe UI,Roboto,PingFang SC,Microsoft YaHei,sans-serif; }
  .wrap { max-width:860px; margin:0 auto; padding:32px 20px 80px; }
  h1 { font-size:22px; margin:0 0 4px; }
  .sub { color:var(--muted); margin:0 0 24px; }
  .group { background:var(--card); border:1px solid var(--line); border-radius:12px; margin-bottom:20px; overflow:hidden; }
  .group summary { padding:14px 18px; cursor:pointer; font-weight:600; user-select:none; }
  .group-wrap { padding:4px 18px 18px; }
  .field { margin-top:14px; }
  .field label { display:flex; align-items:center; gap:8px; margin-bottom:4px; }
  .field .key { font-family:ui-monospace,Menlo,monospace; font-size:13px; }
  .badge { font-size:11px; padding:1px 7px; border-radius:20px; }
  .badge.req { background:rgba(59,130,246,.15); color:#7db3ff; }
  .badge.sensitive { background:rgba(245,158,11,.15); color:#fbbf24; }
  .hint { color:var(--muted); font-size:12px; margin:2px 0 6px; }
  input[type=text],input[type=password] { width:100%; padding:9px 11px; border-radius:8px;
    border:1px solid var(--line); background:#0f1419; color:var(--fg); font-size:14px; }
  input:focus { outline:none; border-color:var(--accent); }
  .row { display:flex; gap:8px; }
  .row input { flex:1; }
  button { cursor:pointer; border-radius:8px; border:1px solid var(--line);
    background:var(--card); color:var(--fg); padding:6px 12px; }
  button.gen { font-size:12px; }
  button.primary { background:var(--accent); border-color:var(--accent); color:#fff; font-weight:600; }
  .actions { position:sticky; bottom:0; padding:14px 0; background:linear-gradient(transparent, var(--bg) 30%); }
  .actions button { padding:11px 24px; font-size:15px; }
  .bar { position:sticky; top:0; background:var(--bg); padding:12px 0 6px; margin-bottom:8px;
         display:flex; gap:6px; align-items:center; }
  .chip { padding:3px 11px; border-radius:20px; border:1px solid var(--line); font-size:12px; cursor:pointer; color:var(--muted); }
  .chip.active { color:var(--fg); border-color:var(--accent); }
  .msg { display:none; padding:12px 14px; border-radius:10px; margin:14px 0; }
  .msg.err { display:block; background:rgba(239,68,68,.1); border:1px solid rgba(239,68,68,.4); color:var(--err); }
  .msg.ok  { display:block; background:rgba(34,197,94,.1); border:1px solid rgba(34,197,94,.4); color:var(--ok); }
  details > summary { list-style:none; position:relative; }
  details > summary::after { content:'▾'; position:absolute; right:18px; color:var(--muted); }
  details[open] > summary::after { content:'▴'; }
</style>
</head>
<body>
<div class="wrap">
  <h1>JinDou Cloud 部署配置向导</h1>
  <p class="sub" id="subtitle">首次部署引导 · 生成仓库根目录 <code>.env</code></p>
  <div class="bar" id="bar"></div>
  <div id="error" class="msg err" style="display:none"></div>
  <div id="ok" class="msg ok" style="display:none"></div>
  <form id="form">{groupsHtml}</form>
  <div class="actions">
    <button type="button" class="primary" onclick="submitAll()">生成并写入 .env</button>
    <button type="button" onclick="regenerateDynamic()">随机重置敏感项</button>
  </div>
</div>
<script>
const fields = {fields};
const groups = {groupsJson};
let groupFilter = new Set(groups.map(g => g.name));
function esc(s) {{ return String(s).replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}})[c]); }}
function buildBar() {{
  const bar = document.getElementById('bar');
  bar.innerHTML = groups.map(g =>
    `<span class="chip ${{groupFilter.has(g.name)?'active':''}}" onclick="toggleGroup('${{esc(g.name)}}')">${{esc(g.name)}}</span>`
  ).join('');
}}
function toggleGroup(name) {{
  if (groupFilter.has(name)) groupFilter.delete(name); else groupFilter.add(name);
  buildBar();
  document.querySelectorAll('details').forEach(d => {{
    const g = d.querySelector('summary').textContent.trim();
    d.style.display = groupFilter.has(g) ? '' : 'none';
  }});
}}
function collect() {{
  const out = {{}};
  document.querySelectorAll('input[id]').forEach(inp => {{ out[inp.id] = inp.value; }});
  return out;
}}
function regenerateDynamic() {{
  Object.entries(fields).forEach(([k, f]) => {{
    if (f.sensitive) {{
      const el = document.getElementById(k);
      if (el) el.value = genValue(k);
    }}
  }});
}}
function genValue(k) {{
  const f = fields[k] || {{}};
  const upper = k.toUpperCase();
  if (upper.indexOf('SECRET') >= 0) {{ return token(48); }}
  if (upper.indexOf('PASSWORD') >= 0 || upper.indexOf('TOKEN') >= 0 || upper.indexOf('ENCRYPT') >= 0) {{ return pass(); }}
  return token(24);
}}
function pass() {{ const a="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*_-"; let s=""; for(let i=0;i<40;i++) s+=a[Math.floor(Math.random()*a.length)]; return s; }}
function token(n) {{ const a="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"; let s=""; while(s.length<n) s+=a[Math.floor(Math.random()*a.length)]; return s; }}
function show(sel, text) {{
  document.getElementById('error').style.display='none';
  document.getElementById('ok').style.display='none';
  const el = document.getElementById(sel);
  if (text) {{ el.textContent=text; el.style.display='block'; }}
}}
async function submitAll() {{
  const ok = document.getElementById('ok'); ok.style.display='none';
  const err = document.getElementById('error'); err.style.display='none';
  const res = await fetch('/submit', {{
    method:'POST',
    headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:new URLSearchParams(collect()).toString()
  }});
  const data = await res.json();
  if (data.ok) {{
    document.getElementById('subtitle').textContent =
      '已写入: ' + data.path + ' (含自动备份)\n请退出向导后运行: make prod';
    show('ok', '✔ ' + data.message + '\\n\\n'+ (data.errors||[]).map(e=>'· '+e).join('\\n'));
    buildBar();
  }} else {{
    show('error', '✘ 校验未通过:\\n' + (data.errors||[]).map(e=>'· '+e).join('\\n'));
  }}
}}
</script>
</body>
</html>"""


class WizardHandler(BaseHTTPRequestHandler):
    root: Path
    groups: list[dict]

    def log_message(self, *args):
        pass

    def _json(self, obj, status=200):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            self.send_response(200)
            body = render_html(self.groups)
            data = body.encode("utf-8")
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.split("?")[0] == "/health":
            self._json({"ok": True})
            return
        self._json({"ok": False}, 404)

    def do_POST(self):
        if self.path.split("?")[0] != "/submit":
            self._json({"ok": False, "errors": ["未支持的操作"]}, 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        submitted = parse_qs(raw, keep_blank_values=True)
        values = {f["key"]: (submitted.get(f["key"], [""])[0] or f.get("default", "") or "") for g in self.groups for f in g["fields"]}
        errors = validate(values)
        if errors:
            self._json({"ok": False, "errors": errors})
            return
        try:
            target = write_env(self.root, self.groups, values)
        except Exception as exc:
            self._json({"ok": False, "errors": [f"写入失败: {exc}"]})
            return
        self._json({"ok": True, "path": str(target), "message": "配置已写入", "errors": []})


def render_html(groups: list[dict]) -> str:
    parts = []
    for group in groups:
        rows = []
        for field in group["fields"]:
            key, default = field["key"], field.get("default", "")
            hint_html = f'<div class="hint">{html.escape(field.get("hint") or "")}</div>' if field.get("hint") else ""
            badge = ""
            if field.get("required"):
                badge += '<span class="badge req">必填</span>'
            if field.get("sensitive"):
                badge += '<span class="badge sensitive">敏感</span>'
            input_type = "password" if field.get("sensitive") else "text"
            gen = f'<button type="button" class="gen" onclick="document.getElementById(\'{key}\').value=genValue(\'{key}\')">随机</button>' if field.get("sensitive") else ""
            rows.append(
                f'<div class="field">'
                f'<label><span class="key">{html.escape(key)}</span>{badge}</label>'
                f'{hint_html}'
                f'<div class="row"><input type="{input_type}" id="{html.escape(key)}" '
                f'value="{html.escape(str(default))}">{gen}</div>'
                f"</div>"
            )
        parts.append(f'<details open><summary>{html.escape(group["name"])}</summary><div class="group-wrap">{"".join(rows)}</div></details>')
    fields_json = json.dumps({f["key"]: f for g in groups for f in g["fields"]}, ensure_ascii=False)
    groups_json = json.dumps([{"name": g["name"]} for g in groups], ensure_ascii=False)
    body_html = "\n".join(parts)
    return HTML_TEMPLATE.replace("{groupsHtml}", body_html).replace("{fields}", fields_json).replace("{groupsJson}", groups_json)


def write_env(root: Path, groups: list[dict], values: dict) -> Path:
    target = root / ".env"
    if target.exists():
        backup = root / f".env.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(target, backup)
    lines = []
    for group in groups:
        lines.append(f"# ==================== {group['name']} ====================")
        for field in group["fields"]:
            if field.get("hint"):
                for hint_line in field["hint"].split("\n"):
                    lines.append(f"# {hint_line}")
            lines.append(f"{field['key']}={values.get(field['key'], '')}")
        lines.append("")
    payload = "\n".join(lines).rstrip() + "\n"
    fd, tmp_path = tempfile.mkstemp(dir=str(root), prefix=".env.tmp.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, target)
        os.chmod(target, 0o600)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return target


def main():
    parser = argparse.ArgumentParser(description="JinDou Cloud 首次部署可视化配置向导")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8642)
    parser.add_argument("--root", type=str, default=None, help="仓库根目录（默认取脚本上级两级）")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else default_root()
    groups = parse_env_example(root)
    WizardHandler.root = root
    WizardHandler.groups = groups
    server = ThreadingHTTPServer((args.host, args.port), WizardHandler)
    print(f"向导已启动: http://{args.host}:{args.port}")
    print(f"字段分组数: {len(groups)}")
    print(f"目标文件: {root / '.env'}  (Ctrl-C 退出)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出")
        server.shutdown()


if __name__ == "__main__":
    main()