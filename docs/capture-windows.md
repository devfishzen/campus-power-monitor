# 抓包指南：找到「智能水电」的接口

> 2026-10-26 已确认接口，见 [api-notes.md](api-notes.md)。本文保留作为抓包方法备查。

目标只有一个：搞清楚小程序在**登录**和**查剩余电量**时，到底请求了哪个 URL、带了什么参数、返回了什么。

接口已经在 `app/providers/ecode.py` 实现，整个服务可以脱离微信自动跑。

---

## 一、先判断：是不是必须依赖微信

抓完看两点：

1. **登录请求体**里有没有 `code` 字段（微信 `wx.login` 返回的临时码）。
2. 后续请求是不是只带 `token` / `Cookie`，还是必须带 `openid`。

| 情况 | 结论 |
|---|---|
| 登录用 `学号 + 密码 + 姓名`，返回 token | ✅ 最理想，服务器可以直接登录 |
| 登录体里有 `code`，服务端拿 code 换 openid | ⚠️ 需要“复用长期 token + 失效提醒”，或找 H5 版 |
| 请求头有 `sign` / `timestamp` / `nonce` | ⚠️ 需要把签名算法也逆出来，工作量 +1 天 |

---

## 二、方案 A：Windows 微信 + mitmproxy（推荐）

### 1. 装 mitmproxy

官网安装包，或：

```powershell
pipx install mitmproxy
```

启动：

```powershell
mitmweb --listen-port 8080 --web-port 8081
```

浏览器会打开 `http://127.0.0.1:8081`，这是抓包控制台。

### 2. 信任 mitmproxy 的证书

证书在：

```
%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer
```

双击 → 安装证书 → **本地计算机** → 将所有证书放入下列存储 → **受信任的根证书颁发机构** → 完成 → 安全警告选“是”。

> 抓完记得删掉这张证书，别长期留着。

### 3. 让微信走代理

先试系统代理（免费、最简单）：

- Windows 设置 → 网络和 Internet → 代理 → 手动设置代理
- 地址 `127.0.0.1`，端口 `8080`，保存

然后打开 PC 微信 → 左下角小程序面板 → 搜索「校园e码通」→ 登录 → 其他服务 → 更多 → 智能水电。

如果 mitmweb 里能看到 `WeChatAppEx.exe` 的请求，就成功了。

**看不到请求**的话，用 Proxifier（31 天试用）：

1. Profile → Proxy Servers → Add：`127.0.0.1:8080`，Protocol 选 HTTPS
2. Profile → Proxification Rules → Add：
   - Name：`WeChat`
   - Applications：`WeChat.exe;WeChatAppEx.exe;WeChatBrowser.exe;WeChatUtility.exe;WeChatPlayer.exe`
   - Action：Proxy `127.0.0.1:8080`
3. 默认规则保持 Direct，启用 Proxifier

> `WeChatAppEx.exe` 是关键，小程序跑在这个进程里，只代理 `WeChat.exe` 往往抓不到。

### 4. 抓这两个动作

1. **登录**：如果已是登录态，先在小程序里退出登录，再重新用学号+密码+姓名登录
2. **查电费**：进入「智能水电」，点右上角刷新，等页面出现剩余电量数值

### 5. 在 mitmweb 里找

过滤框输入：

```
~u zytec | ~u ecode | ~u ecard | ~u elec | ~u water | ~u meter | ~u room
```

重点看返回 JSON 的请求，尤其是包含剩余电量数值、房间号的那条。

---

## 三、要发我什么（脱敏后）

不用发整包，按下面清单发就够：

### 1. 登录

- 请求：`Method` + `URL`
- 请求体字段名（值打码），例如：`account=***&password=***&name=***`
- 响应：字段名 + 结构，`token` 只留前 6 位，保留 `expiresIn` / `expireTime`
- 请求头里有没有 `sign`、`timestamp`、`nonce`、`schoolId`、`tenantId`

### 2. 智能水电

- 进入页面后所有 XHR 的 URL 列表（截图即可）
- 返回剩余电量的那条：完整 URL、请求头字段名、响应 JSON（房间号可打码，剩余电量数值保留）
- 房间/楼栋是怎么传的：`roomId`、`roomNo`、`buildingId` 还是拼在 URL 里

### 3. 判断项

- 登录体里有没有 `code`
- token 大概多久过期（响应里的字段，或隔天再打开看是否要重新登录）
- 点「充值」是不是跳到另一个小程序/H5（如果跳走，说明电费是独立系统，可能更好抓）

### 4. 截图建议

mitmweb 里选中请求 → 右侧 Request / Response 面板截图：

- `Authorization` / `Cookie` / `token` 用黑块挡住，只留字段名
- 学号、姓名、房间号打码
- 保留 URL、Method、Content-Type、JSON 的 key 和数值

---

## 四、常见问题

**Q：mitmweb 里全是 `Client TLS handshake failed`？**
证书没被信任。确认装到了「本地计算机 → 受信任的根证书颁发机构」，然后完全退出微信再重开。

**Q：微信能上网，但 mitmweb 一条记录都没有？**
小程序没走系统代理。用 Proxifier，并确认规则包含 `WeChatAppEx.exe`。

**Q：小程序提示“网络异常”？**
正常，说明流量被代理拦截了但证书没被信任。回到第 2 步。

**Q：必须用 PC 微信吗？**
不是。安卓手机也能抓，但 Android 7+ 不信任用户证书，需要 root 把证书装进系统区；iPhone 装完证书后在「关于本机 → 证书信任设置」里打开，通常可行。PC 微信最省事。

**Q：抓完怎么恢复？**
关掉系统代理、退出 Proxifier、删除 mitmproxy 根证书。

---

## 五、如果抓不到

按优先级退：

1. **找 H5 版**：问学校网络中心/后勤有没有网页版电费查询；或在 PC 微信里点开智能水电时看有没有网页加载痕迹。
2. **手机 ADB + OCR**：旧安卓手机常亮放宿舍，服务器通过 `adb` 截图，OCR 识别剩余电量。不需要抓包，但要多一台手机，且微信可能杀后台。
3. **长期 token**：只抓一次登录，把 token 存起来用，失效时邮件提醒你重新抓。半自动，但最省事。

---

## 六、安全

- 只抓自己的账号，不要抓别人的
- 抓包时不要连公共 Wi-Fi
- `.mitm` / HAR 文件里有明文 token，发人之前一定脱敏
- 抓完删除证书和抓包文件
