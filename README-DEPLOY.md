# 部署说明（服务器）

## 服务器要求

- Debian 12 / Ubuntu 22.04 或更新
- Docker Engine + Docker Compose 插件
- 2 核 / 2GB 内存 / 8GB 磁盘足够
- 8080 端口只在局域网开放，不要直接映射到公网

## 三步部署

```bash
git clone https://github.com/<your-name>/campus-power-monitor.git
cd campus-power-monitor

cp .env.example .env
nano .env                 # 填学号、学校编号、房间、QQ 邮箱、ADMIN_PASSWORD

bash deploy.sh
```

然后打开：

```
http://<服务器IP>:8080
```

`deploy.sh` 会做这些事：

- 检查 Docker / Compose
- `chmod 600 .env`
- 创建 `data/` 并设置容器 UID 1000 可写
- `docker compose build`
- `docker compose up -d`
- 等待 `/healthz` 通过
- 打印当前读数

## 设置页

```
http://<服务器IP>:8080/settings
```

- 用户名：`ADMIN_USER`（默认 `admin`）
- 密码：`ADMIN_PASSWORD`

可以在线改阈值、填 QQ 授权码、发测试邮件。设置保存在 `data/overrides.json`。

## 如果 Docker 还没装

Debian 12 / Ubuntu：

```bash
apt update && apt install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  > /etc/apt/sources.list.d/docker.list
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
```

## 国内网络构建慢

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple bash deploy.sh
```

如果拉取 `python:3.12-slim` 失败，给 Docker 配镜像加速，或先手动拉取基础镜像再重试。

## 日常操作

```bash
docker compose logs -f          # 看日志
docker compose restart          # 重启
docker compose down             # 停止
docker compose up -d            # 启动
docker compose exec dianfei python -m scripts.livecheck   # 手动实网查询
docker compose exec dianfei python scripts/send_test.py   # 测试邮件
```

## 更新

```bash
git pull
bash upgrade.sh
```

`upgrade.sh` 会保留 `.env` 和 `data/`，补齐新配置（如 `ADMIN_PASSWORD`），然后重新构建并重启。

如果是全新部署，用 `bash deploy.sh`。

SQLite 数据在 `data/dianfei.db`，升级不会丢。

## 备份

```bash
docker compose stop
cp -a data data.bak-$(date +%F)
docker compose start
```

PVE 层面再加一个每周 `vzdump` 即可。

## 安全

- `.env` 含学号、QQ 授权码和设置页密码，权限保持 `600`
- 设置页是 HTTP Basic，公网访问必须上 HTTPS 或 Tailscale/WireGuard
- 8080 只开内网
- 不要提交 `.env`、`data/` 到 Git
