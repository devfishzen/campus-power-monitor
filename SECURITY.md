# Security

## 不要提交的内容

- `.env`：学号、QQ 邮箱授权码、设置页密码
- `data/`：SQLite 数据库、`overrides.json`（可能含授权码）
- 任何抓包文件（HAR、`.mitm`）里通常含 token/学号

`.gitignore` 已经忽略这些路径；提交前请再确认：

```bash
git status --short
git ls-files | grep -E '(^|/)\.env$|^data/'
```

## 部署建议

- 设置页使用 HTTP Basic，**不要直接暴露在公网 HTTP 上**；公网访问请套 HTTPS 反向代理（Caddy/Nginx）或 Tailscale/WireGuard
- `chmod 600 .env`，`data/overrides.json` 默认 600
- `ADMIN_PASSWORD` 用随机密码；不要复用 QQ 密码
- 8080 端口只在内网开放

## 上游接口

完美校园水电 H5 没有鉴权，只凭学号 + 学校编号 + 房间号。本项目只应查询本人有权查看的房间，不要用于遍历他人房间或高频请求。

## 报告问题

如果发现安全问题，请在 GitHub 仓库开一个 Issue（不要贴真实学号、授权码、token），或使用 GitHub 的私密安全报告功能。
