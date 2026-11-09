# 完美校园「智能水电」接口说明

「校园e码通 / 完美校园」的智能水电 H5，实测不需要登录、不需要密码、不需要微信。

- Base：`https://xqh5.17wanxiao.com/smartWaterAndElectricityService`
- 接口：`POST /SWAEServlet`
- 请求体为空，参数全部放在 query 里
- 需要 cookie jar：第一次响应会下发 `acw_tc`、`SERVERID`，后续请求带上

## 1. 查询账号绑定的房间

```
POST /SWAEServlet
  ?param={"cmd":"getbindroom","account":"学号"}
  &customercode=<学校编号>
  &method=getbindroom
```

`customercode` 是学校编号，来自 e码通跳转 URL 里的 `customerid`。不同学校不同，必须自己抓一次。

返回（`body` 是 JSON 字符串，需要二次解析）：

```json
{
  "code_": 0,
  "result_": "true",
  "body": "{\"result\":\"0\",\"roomfullname\":\"A栋宿舍_学生公寓A栋_1层_101房间\",\"roomverify\":\"1-2--3-101\",\"detaillist\":[{\"odd\":\"50.0\",\"businesstype\":\"1\"},{\"odd\":\"100.0\",\"businesstype\":\"0\"}]}"
}
```

有的账号返回 `roomlist` 数组，有的直接返回单个房间对象；代码两种都兼容。

## 2. 查询房间水电明细

```
POST /SWAEServlet
  ?param={"cmd":"h5_getstuindexpage","roomverify":"1-2--3-101","account":"学号","timestamp":"20260101083000000"}
  &customercode=<学校编号>
  &method=h5_getstuindexpage
  &command=JBSWaterElecService
```

`timestamp` 格式 `yyyyMMddHHmmss000`，用当前时间即可。

返回的 `body` 里：

| 字段 | 含义 |
|---|---|
| `roomfullname` | 房间名，如 `学生公寓A栋-101房间` |
| `modlist[]` | 表列表，一个房间可能同时有电控和水表 |
| `modlist[].devicename` | `DDS1351电控` = 电表；`CJ/T188-2004水表` = 水表 |
| `modlist[].bussnesstype` | `0` = 电，`1` = 水 |
| `modlist[].odd` | **剩余电量（度）** |
| `modlist[].todayuse` | 今日用电（度） |
| `modlist[].weekuselist` | 最近 7 天，`daydate` / `dayuse` |

解析规则：先排除 `devicename` 含「水表」的，再优先取 `bussnesstype == 0` 的那条。

## 3. 请求头

```
User-Agent: ... Wanxiao/5.8.6
X-Requested-With: com.newcapec.mobile.ncp
Referer: https://xqh5.17wanxiao.com/userwaterelecmini/index.html
Origin: https://xqh5.17wanxiao.com
Content-Type: application/x-www-form-urlencoded
```

## 4. 注意

- 接口没有签名、没有 token；`param` 是 URL 编码的 JSON。
- 服务器 IP 可以访问，不需要校园网。
- 只查自己的学号/房间；不要拿它遍历别人的房间。
- 频率保持每天 1–2 次。
- 如果以后接口加了登录，只需在 `app/providers/ecode.py` 里补 cookie/登录步骤，解析逻辑不用动。
