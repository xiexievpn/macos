#!/bin/bash

# 登录/启动网络自愈脚本：清理残留代理进程、重置系统代理并刷新 DNS 缓存
pkill -9 -f "sing-box" 2>/dev/null || true
killall -9 sing-box 2>/dev/null || true
killall -9 xray 2>/dev/null || true

while IFS= read -r service; do
    [[ -z "$service" || "$service" == \** ]] && continue
    networksetup -setwebproxystate "$service" off 2>/dev/null || true
    networksetup -setsecurewebproxystate "$service" off 2>/dev/null || true
    networksetup -setsocksfirewallproxystate "$service" off 2>/dev/null || true
done < <(networksetup -listallnetworkservices 2>/dev/null | tail -n +2)

# 刷新 macOS DNS 缓存（非特权模式）
dscacheutil -flushcache 2>/dev/null || true

exit 0
