#!/bin/bash
cd "$(dirname "$0")"

pkill xray

# 同样的自动检测逻辑，确保关对网卡
DEFAULT_DEV=$(route -n get default | grep 'interface:' | awk '{print $2}')
if [ -z "$DEFAULT_DEV" ]; then
    SERVICE_NAME="Wi-Fi"
else
    SERVICE_NAME=$(networksetup -listallhardwareports | grep -B 1 "$DEFAULT_DEV" | grep "Hardware Port" | cut -d ": " -f 2)
fi
if [ -z "$SERVICE_NAME" ]; then SERVICE_NAME="Wi-Fi"; fi

networksetup -setwebproxystate "$SERVICE_NAME" off
networksetup -setsecurewebproxystate "$SERVICE_NAME" off
networksetup -setsocksfirewallproxystate "$SERVICE_NAME" off

exit 0
