#!/bin/bash

cd "$(dirname "$0")"

pkill xray

sudo networksetup -setwebproxystate "Wi-Fi" off
sudo networksetup -setsecurewebproxystate "Wi-Fi" off
sudo networksetup -setsocksfirewallproxystate "Wi-Fi" off

exit 0
