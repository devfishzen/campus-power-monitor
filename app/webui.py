"""HTML 页面渲染，不依赖 FastAPI，方便单独测试。"""

from __future__ import annotations

import html

from .models import Reading

STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; display: grid; place-items: center;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  background: #f4f6f8; color: #1c2833; padding: 24px;
}
.card {
  background: #fff; border-radius: 18px; padding: 28px 32px; width: min(460px, 100%);
  box-shadow: 0 10px 30px rgba(0, 0, 0, .08); text-align: center;
}
.room { font-size: 15px; color: #5d6d7e; letter-spacing: .5px; }
.value { font-size: 64px; font-weight: 700; line-height: 1.1; margin: 10px 0 6px; }
.unit { font-size: 22px; font-weight: 500; margin-left: 4px; }
.muted { font-size: 13px; color: #7f8c8d; margin-top: 6px; }
.footer { margin-top: 18px; font-size: 12px; color: #aab7b8; }
.footer a { color: #2471a3; text-decoration: none; }
.settings { text-align: left; margin-top: 18px; display: grid; gap: 14px; }
.settings label { font-size: 13px; color: #5d6d7e; display: grid; gap: 6px; }
.settings input {
  width: 100%; padding: 10px 12px; border: 1px solid #d5dbdb; border-radius: 10px;
  font-size: 16px; background: #fff; color: #1c2833;
}
.settings .row { display: flex; gap: 10px; flex-wrap: wrap; }
.settings button {
  padding: 10px 18px; border: 0; border-radius: 10px; background: #1e8449;
  color: #fff; font-size: 15px; cursor: pointer;
}
.settings button.secondary { background: #5d6d7e; }
.settings .msg { min-height: 20px; font-size: 14px; }
.settings .ok { color: #1e8449; }
.settings .err { color: #c0392b; }
@media (prefers-color-scheme: dark) {
  body { background: #101418; color: #ecf0f1; }
  .card { background: #1b2128; box-shadow: none; }
  .room, .muted, .settings label { color: #95a5a6; }
  .settings input { background: #101418; border-color: #2c3e50; color: #ecf0f1; }
}
"""


def page(title: str, body: str, refresh: bool = False) -> str:
    meta = '<meta http-equiv="refresh" content="60">' if refresh else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{meta}
<title>{html.escape(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="card">
{body}
</div>
</body>
</html>"""


def dashboard(
    reading: Reading | None,
    threshold: float,
    mail_enabled: bool,
    admin_enabled: bool,
) -> str:
    if reading is None:
        body = '<p class="muted">暂无数据，等待第一次查询。</p>'
    else:
        local_time = reading.fetched_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        low = reading.remaining_kwh <= threshold
        color = "#c0392b" if low else "#1e8449"
        today = (
            f"{reading.today_kwh:g} 度"
            if reading.today_kwh is not None
            else "—"
        )
        body = f"""
        <div class="room">{html.escape(reading.room)}</div>
        <div class="value" style="color:{color}">{reading.remaining_kwh:.1f}<span class="unit">度</span></div>
        <div class="muted">今日用电 {today} · 告警阈值 {threshold:g} 度</div>
        <div class="muted">查询时间 {local_time}</div>
        """

    mail_status = "邮件已配置" if mail_enabled else "邮件未配置"
    if admin_enabled:
        settings_link = '<a href="/settings">设置</a>'
    else:
        settings_link = '<span title="在 .env 设置 ADMIN_PASSWORD 后重启">设置未启用</span>'
    body += f'<div class="footer">{mail_status} · {settings_link} · 每 60 秒刷新</div>'
    return page("电费监控", body, refresh=True)


def settings_page(
    threshold: float,
    smtp_pass_set: bool,
    mail_to: str,
    mail_enabled: bool,
) -> str:
    pass_placeholder = (
        "已配置，留空表示不修改" if smtp_pass_set else "未配置，请填写授权码"
    )
    mail_status = "已配置" if mail_enabled else "未配置"
    body = f"""
    <div class="room">设置</div>
    <div class="muted">修改后立即生效，并保存到 data/overrides.json</div>

    <form id="settings-form" class="settings">
      <label>剩余电量告警阈值（度）
        <input id="threshold" type="number" step="0.1" min="0" max="10000"
               value="{threshold:g}" required>
      </label>

      <label>QQ 邮箱授权码
        <input id="smtp_pass" type="password" autocomplete="new-password"
               placeholder="{pass_placeholder}">
      </label>

      <div class="muted">邮件通知：{mail_status}（收件人 {html.escape(mail_to or "未配置")}）</div>

      <div class="row">
        <button type="submit">保存</button>
        <button type="button" id="test-mail" class="secondary">发送测试邮件</button>
      </div>
      <div id="msg" class="msg"></div>
    </form>

    <div class="footer"><a href="/">返回监控页</a></div>

    <script>
    const form = document.getElementById('settings-form');
    const msg = document.getElementById('msg');

    function show(text, ok) {{
      msg.textContent = text;
      msg.className = 'msg ' + (ok ? 'ok' : 'err');
    }}

    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      const threshold = Number(document.getElementById('threshold').value);
      const pass = document.getElementById('smtp_pass').value.trim();
      const payload = {{ threshold_kwh: threshold }};
      if (pass) payload.smtp_pass = pass;

      const response = await fetch('/api/settings', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload)
      }});
      const data = await response.json().catch(() => ({{}}));
      if (response.ok) {{
        show('已保存', true);
        document.getElementById('smtp_pass').value = '';
      }} else {{
        show(typeof data.detail === 'string' ? data.detail : '保存失败', false);
      }}
    }});

    document.getElementById('test-mail').addEventListener('click', async () => {{
      const response = await fetch('/api/settings/test-email', {{ method: 'POST' }});
      const data = await response.json().catch(() => ({{}}));
      if (response.ok) {{
        show('测试邮件已发送，请检查收件箱和垃圾箱', true);
      }} else {{
        show(typeof data.detail === 'string' ? data.detail : '发送失败', false);
      }}
    }});
    </script>
    """
    return page("设置", body)
