# 谢谢网络加速器 (XieXie VPN macOS Client)

基于 `sing-box` 双协议内核（Hysteria 2 + VLESS-Reality）的 macOS 原生客户端，功能与 Windows 客户端保持 100% 同步。

## 核心特性
- **双协议内核 (`sing-box v1.10.7`)**：原生支持 `Hysteria 2` 与 `VLESS + Reality`，内置 `geoip-cn.srs` / `geosite-cn.srs` 国内外智能分流与防污染 DNS。
- **并发测速与智能降级**：支持 `自动选择`、`Hysteria2`、`VLESS` 协议切换；Hysteria 2 走独立临时端口真实 HTTP 204 测速，UDP 受阻时自动无缝降级至 VLESS。
- **双 API 端点容灾**：控制面请求自动在 `payapi.xiexievpn.com` 与 `vvv.xiexievpn.com` 之间故障转移，并强制绕过系统代理防止死锁。
- **后台断线自愈 (`Watchdog`)**：连接期间每 15 秒检测代理连通性，连续失败自动重拉订阅、重新测速并热重载。
- **启动网络自愈 (`repair_on_login.sh`)**：登录时自动清理残留代理进程、重置系统代理与刷新 DNS 缓存。
- **在线区域切换与自动更新**：支持 5 大地区实时切换（含建机进度轮询与保持连接自动重连）及多源在线自动更新。

## 本地打包命令
```bash
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "谢谢网络加速器" \
  --icon "favicon.icns" \
  --add-data "favicon.icns:." \
  --add-data "favicon.ico:." \
  --add-data "internet.sh:." \
  --add-data "close.sh:." \
  --add-data "repair_on_login.sh:." \
  --add-data "sing-box:." \
  --add-data "geoip-cn.srs:." \
  --add-data "geosite-cn.srs:." \
  --add-data "languages.json:." \
  --add-data "flags:flags" \
  main_macos.py
```
