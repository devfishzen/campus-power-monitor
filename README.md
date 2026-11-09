# 校园电费监控

定时查询「完美校园」智能水电的**剩余电量**，低于阈值时发邮件到 QQ 邮箱；自带 Web 设置页，可以在线改阈值、填授权码、发测试邮件。

> 这是一个通用的完美校园水电 H5 客户端模板。不同学校的 `customerid`、房间名不同，需要自己填。
> 与完美校园、任何学校官方均无关联，接口来自公开 H5，仅建议查询本人有权查看的房间。

## 功能

- 每天定时查询（cron 可配，默认 08:30）
- 剩余电量 ≤ 阈值时发邮件，20 小时内不重复
- 连续 2 次查询失败也发邮件，避免服务挂了不知道
- SQLite 保存历史读数
- 网页查看当前电量
- Web 设置页：改阈值、填/换 QQ 邮箱授权码、发测试邮件
- Docker 一键部署，数据持久化

## 数据来源

「校园e码通 / 完美校园」的智能水电页面，实际请求的是：

```
POST https://xqh5.17wanxiao.com/smartWaterAndElectricityService/SWAEServlet
```

两步：`getbindroom` 拿房间 `roomverify`，`h5_getstuindexpage` 拿电表 `odd`（剩余电量）。
只需要「学号 + 学校编号 + 房间号」，不需要校园卡密码，也不需要微信。

接口细节和字段说明见 [docs/api-notes.md](docs/api-notes.md)。

## 快速开始

### 1. 填配置

```bash
cp .env.example .env
```

至少填这几项：

| 变量 | 填什么 |
|---|---|
| `ECODE_ACCOUNT` | 你的学号/工号 |
| `ECODE_CUSTOMERCODE` | 学校编号，抓包时 e码通跳转 URL 里的 `customerid` |
| `ECODE_ROOM` | 房间名，小程序「智能水电」页面顶部，例如 `A栋-101` |
| `SMTP_USER` | 你的 QQ 邮箱 |
| `SMTP_PASS` | QQ 邮箱授权码（不是 QQ 密码） |
| `MAIL_TO` | 收件邮箱 |
| `ADMIN_PASSWORD` | 设置页登录密码，建议随机 16 位 |

不知道学校编号？按 [docs/capture-windows.md](docs/capture-windows.md) 抓一次包，看 URL 里的 `customerid`。
房间名不确定也没关系：先填个大概，`livecheck` 报错时会列出账号绑定的房间。

### 2. 先验证接口（不需要 Docker）

```bash
python -m scripts.livecheck
```

正常输出：

```
房间：A栋-101
剩余电量：100.5 度
今日用电：12 度
```

这一步只用 Python 标准库。

### 3. 启动

```bash
mkdir -p data
sudo chown -R 1000:1000 data   # Linux 需要；Windows Docker Desktop 可跳过
bash deploy.sh
```

或手动：

```bash
docker compose up -d --build
```

打开 `http://<服务器IP>:8080`。

### 4. 设置页

打开 `http://<服务器IP>:8080/settings`，输入：

- 用户名：`ADMIN_USER`（默认 `admin`）
- 密码：`ADMIN_PASSWORD`

可以改阈值、填授权码、点「发送测试邮件」。

## 配置说明

| 变量 | 默认 | 说明 |
|---|---|---|
| `PROVIDER` | `mock` | `ecode` 查真实数据；`mock` 演示 |
| `CHECK_CRON` | `30 8 * * *` | 每天 08:30 |
| `THRESHOLD_KWH` | `30` | 低于该值告警 |
| `ALERT_COOLDOWN_HOURS` | `20` | 同类告警冷却 |
| `DB_PATH` | `/data/dianfei.db` | SQLite |
| `OVERRIDES_PATH` | `/data/overrides.json` | Web 设置页覆盖值 |
| `ECODE_ACCOUNT` | 空 | 学号 |
| `ECODE_CUSTOMERCODE` | 空 | 学校编号 |
| `ECODE_ROOM` | 空 | 房间名 |
| `ECODE_ROOMVERIFY` | 空 | 可选，直接指定房间 ID |
| `SMTP_HOST/PORT` | `smtp.qq.com:465` | QQ 邮箱 |
| `SMTP_USER/PASS` | 空 | 邮箱 + 授权码 |
| `MAIL_TO` | 空 | 收件人 |
| `ADMIN_USER` | `admin` | 设置页用户名 |
| `ADMIN_PASSWORD` | 空 | 留空则设置页关闭 |
| `API_TOKEN` | 空 | `/api/run` 令牌，可选 |

## Web 设置页的优先级

设置页保存到 `data/overrides.json`（权限 600），**优先于 `.env`**：

- 改阈值 → 保存后立即生效
- 填授权码 → 立即用于下一次发信
- 想恢复 `.env` 的值：删除 `data/overrides.json` 后重启

```bash
rm data/overrides.json
docker compose up -d --force-recreate
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 监控页 |
| GET | `/settings` | 设置页（HTTP Basic） |
| GET | `/healthz` | 健康检查 |
| GET | `/api/current` | 最新读数 |
| GET | `/api/history?days=30` | 历史读数 |
| POST | `/api/run` | 立即查询；设置 `API_TOKEN` 后需带 `X-Api-Token` |
| POST | `/api/settings` | 保存阈值/授权码（HTTP Basic） |
| POST | `/api/settings/test-email` | 测试邮件（HTTP Basic） |

## 目录

```
app/
  main.py          FastAPI 路由 + 调度
  webui.py         页面渲染（无框架依赖）
  config.py        配置
  overrides.py     Web 设置页覆盖值
  service.py       查询 → 入库 → 阈值 → 告警
  notifier.py      QQ 邮箱 SMTP
  store.py         SQLite
  providers/
    ecode.py           完美校园 H5 客户端
    wanxiao_parse.py   响应解析
    mock.py            演示数据
docs/
  api-notes.md         接口说明
  capture-windows.md   抓包方法
scripts/
  livecheck.py     实网查询（无需 Docker）
  mailcheck.py     本机测试邮件
  send_test.py     容器内测试邮件
  selftest.py      核心逻辑自检
```

## 部署到服务器 / PVE

见 [README-DEPLOY.md](README-DEPLOY.md)。4GB 内存的 PVE 用 2GB LXC 足够。

## 安全

- `.env` 含学号、QQ 授权码、设置页密码；`chmod 600 .env`，不要提交到 git
- `data/overrides.json` 含授权码，权限 600
- 设置页是 HTTP Basic + 明文 HTTP，**只适合内网**；公网访问请套 HTTPS 反代或 Tailscale/WireGuard
- 上游接口没有鉴权，只凭学号 + 学校编号 + 房间号；请只查询本人有权查看的房间，不要遍历他人房间
- 查询频率保持每天 1–2 次，不要给学校接口造成压力

## 常见问题

| 现象 | 处理 |
|---|---|
| `ECODE_CUSTOMERCODE 未配置` | 填学校编号（抓包 URL 的 `customerid`） |
| `账号没有绑定房间` | 学号或学校编号不对 |
| `没有匹配到房间` | `ECODE_ROOM` 和实际房间名不一致；按报错列出的房间名改，或填 `ECODE_ROOMVERIFY` |
| `响应里没有找到电表` | 房间号不对，或该房间只有水表 |
| 邮件 535 | 授权码失效/服务未开/频率限制；重新生成 QQ 授权码，等 15–30 分钟再试 |
| 收不到邮件 | 先跑 `python -m scripts.mailcheck`；查垃圾箱、QQ 邮箱提醒设置 |

## 免责声明

本项目仅用于学习与个人自用，不保证接口长期可用；因使用本项目导致的账号限制、数据误差等风险由使用者自行承担。

## License

[MIT](LICENSE)
