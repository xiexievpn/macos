#!/bin/bash

# 获取资源目录与配置目录
RESOURCE_DIR="${1:-$(cd "$(dirname "$0")" && pwd)}"
CONFIG_DIR="${2:-$HOME/Library/Application Support/XieXieVPN}"
CONFIG_FILE="$CONFIG_DIR/config.json"

# 兼容开发环境及 PyInstaller v5/v6 .app 目录结构 (Frameworks / Resources / MacOS)
SINGBOX_BIN=""
for candidate in \
    "$RESOURCE_DIR/sing-box" \
    "$(cd "$RESOURCE_DIR/.." 2>/dev/null && pwd)/Frameworks/sing-box" \
    "$(cd "$RESOURCE_DIR/.." 2>/dev/null && pwd)/Resources/sing-box" \
    "$(cd "$RESOURCE_DIR/.." 2>/dev/null && pwd)/MacOS/sing-box"; do
    if [ -f "$candidate" ]; then
        SINGBOX_BIN="$candidate"
        break
    fi
done

mkdir -p "$CONFIG_DIR"

# 停止旧的代理进程
pkill -9 -f "sing-box run -c" 2>/dev/null || true
killall -9 sing-box 2>/dev/null || true
killall -9 xray 2>/dev/null || true

# 确保规则集文件在配置目录中可用
for srs in geoip-cn.srs geosite-cn.srs; do
    for srs_dir in "$RESOURCE_DIR" "$(cd "$RESOURCE_DIR/.." 2>/dev/null && pwd)/Resources" "$(cd "$RESOURCE_DIR/.." 2>/dev/null && pwd)/Frameworks"; do
        if [ -f "$srs_dir/$srs" ] && [ ! -f "$CONFIG_DIR/$srs" ]; then
            cp -f "$srs_dir/$srs" "$CONFIG_DIR/$srs" 2>/dev/null || true
            break
        fi
    done
done

# 配置活跃网络服务的系统代理
configure_proxy_for_service() {
    local svc="$1"
    networksetup -setwebproxy "$svc" 127.0.0.1 1080 2>/dev/null || true
    networksetup -setsecurewebproxy "$svc" 127.0.0.1 1080 2>/dev/null || true
    networksetup -setsocksfirewallproxy "$svc" 127.0.0.1 10808 2>/dev/null || true
    networksetup -setproxybypassdomains "$svc" 127.0.0.1 localhost 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12 "*.local" 2>/dev/null || true
    networksetup -setwebproxystate "$svc" on 2>/dev/null || true
    networksetup -setsecurewebproxystate "$svc" on 2>/dev/null || true
    networksetup -setsocksfirewallproxystate "$svc" on 2>/dev/null || true
}

APPLIED_COUNT=0
while IFS= read -r service; do
    [[ -z "$service" || "$service" == \** ]] && continue
    info=$(networksetup -getinfo "$service" 2>/dev/null || true)
    if echo "$info" | grep -qE "IP address: [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+"; then
        configure_proxy_for_service "$service"
        APPLIED_COUNT=$((APPLIED_COUNT + 1))
    fi
done < <(networksetup -listallnetworkservices 2>/dev/null | tail -n +2)

# 如果没有检测到带 IP 的服务，回退设置所有非禁用网络接口
if [ "$APPLIED_COUNT" -eq 0 ]; then
    while IFS= read -r service; do
        [[ -z "$service" || "$service" == \** ]] && continue
        configure_proxy_for_service "$service"
    done < <(networksetup -listallnetworkservices 2>/dev/null | tail -n +2)
fi

# 启动 sing-box
if [ -n "$SINGBOX_BIN" ] && [ -f "$SINGBOX_BIN" ] && [ -f "$CONFIG_FILE" ]; then
    chmod +x "$SINGBOX_BIN" 2>/dev/null || true
    xattr -d com.apple.quarantine "$SINGBOX_BIN" 2>/dev/null || true
    cd "$CONFIG_DIR" || exit 1
    nohup "$SINGBOX_BIN" run -c "$CONFIG_FILE" > "$CONFIG_DIR/sing-box.log" 2>&1 &
    sleep 0.5
    if ! pgrep -f "sing-box run -c" >/dev/null 2>&1; then
        echo "sing-box failed to start:" >&2
        cat "$CONFIG_DIR/sing-box.log" >&2 2>/dev/null || true
        exit 1
    fi
else
    echo "Error: sing-box binary or config.json not found ($SINGBOX_BIN / $CONFIG_FILE)" >&2
    exit 1
fi
