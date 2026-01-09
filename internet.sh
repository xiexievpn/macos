#!/bin/bash
cd "$(dirname "$0")"

CONFIG_PATH="$HOME/Library/Application Support/XieXieVPN/config.json"
LOG_PATH="$HOME/Library/Application Support/XieXieVPN/xray.log"

# 1. 杀掉可能残留的旧进程
pkill xray

# 2. 启动 xray
# 注意：因为父进程是 root (osascript 提权)，xray 也会以 root 运行
./xray -c "$CONFIG_PATH" > "$LOG_PATH" 2>&1 &

# 3. [关键] 自动检测当前使用的网络服务名称 (Wi-Fi, Ethernet, USB LAN等)
# 逻辑：获取默认路由网卡(如 en0) -> 反查对应的服务名称
DEFAULT_DEV=$(route -n get default | grep 'interface:' | awk '{print $2}')
if [ -z "$DEFAULT_DEV" ]; then
    SERVICE_NAME="Wi-Fi" # 没网时的兜底
else
    SERVICE_NAME=$(networksetup -listallhardwareports | grep -B 1 "$DEFAULT_DEV" | grep "Hardware Port" | cut -d ": " -f 2)
fi
# 如果反查失败，回退到 Wi-Fi
if [ -z "$SERVICE_NAME" ]; then SERVICE_NAME="Wi-Fi"; fi

# 4. 设置系统代理
# 注意：SOCKS 端口已修正为 10808
networksetup -setwebproxy "$SERVICE_NAME" 127.0.0.1 1080
networksetup -setsecurewebproxy "$SERVICE_NAME" 127.0.0.1 1080
networksetup -setsocksfirewallproxy "$SERVICE_NAME" 127.0.0.1 10808

networksetup -setwebproxystate "$SERVICE_NAME" on
networksetup -setsecurewebproxystate "$SERVICE_NAME" on
networksetup -setsocksfirewallproxystate "$SERVICE_NAME" on

exit 0
