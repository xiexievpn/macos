#!/bin/bash

cd "$(dirname "$0")"

CONFIG_PATH="$HOME/Library/Application Support/XieXieVPN/config.json"

./xray -c "$CONFIG_PATH" > /dev/null 2>&1 &

sudo networksetup -setwebproxy "Wi-Fi" 127.0.0.1 1080
sudo networksetup -setsecurewebproxy "Wi-Fi" 127.0.0.1 1080
sudo networksetup -setsocksfirewallproxy "Wi-Fi" 127.0.0.1 1080

sudo networksetup -setwebproxystate "Wi-Fi" on
sudo networksetup -setsecurewebproxystate "Wi-Fi" on
sudo networksetup -setsocksfirewallproxystate "Wi-Fi" on

exit 0
