#!/bin/bash

# 终止 sing-box 与旧版 xray 进程
pkill -9 -f "sing-box" 2>/dev/null || true
killall -9 sing-box 2>/dev/null || true
killall -9 xray 2>/dev/null || true

# 关闭所有网络接口的代理配置
while IFS= read -r service; do
    [[ -z "$service" || "$service" == \** ]] && continue
    networksetup -setwebproxystate "$service" off 2>/dev/null || true
    networksetup -setsecurewebproxystate "$service" off 2>/dev/null || true
    networksetup -setsocksfirewallproxystate "$service" off 2>/dev/null || true
done < <(networksetup -listallnetworkservices 2>/dev/null | tail -n +2)

exit 0
