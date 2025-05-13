#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import messagebox, Menu
import subprocess
import os
import sys
import requests
import json
import webbrowser
import platform

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_persistent_path(filename):
    if platform.system() == "Darwin":
        home = os.path.expanduser("~")
        app_support_dir = os.path.join(home, "Library", "Application Support", "XieXieVPN")
        os.makedirs(app_support_dir, exist_ok=True)
        return os.path.join(app_support_dir, filename)
    else:
        # 其它系统自行处理
        return filename

AUTOSTART_FILE = get_persistent_path("autostart_state.txt")

def save_autostart_state(state: bool):
    with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
        f.write("1" if state else "0")

def load_autostart_state() -> bool:
    if os.path.exists(AUTOSTART_FILE):
        with open(AUTOSTART_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() == "1"
    return False

def toggle_autostart_mac(should_enable: bool):
    # 用户目录下的 LaunchAgents 路径
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(parents=True, exist_ok=True)

    # plist 文件名和完整路径
    plist_name = "com.xiexievpn.launcher.plist"
    plist_path = launch_agents_dir / plist_name

    if should_enable:
        program_executable = sys.executable 
        script_path = os.path.abspath(__file__)

        plist_content = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
                    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
            <dict>
                <key>Label</key>
                <string>com.xiexievpn.launcher</string>
                
                <key>ProgramArguments</key>
                <array>
                    <string>{program_executable}</string>
                    <string>{script_path}</string>
                </array>

                <key>RunAtLoad</key>
                <true/>
            </dict>
            </plist>
        """)

        # 写入 plist 文件
        with open(plist_path, "w", encoding="utf-8") as f:
            f.write(plist_content)

        # load plist 到 launchctl
        try:
            # 先 unload 一下，避免已经存在时出错
            subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
            subprocess.run(["launchctl", "load", str(plist_path)], check=True)
            print("已启用开机自启并加载 Launch Agent。")
        except subprocess.CalledProcessError as e:
            print(f"无法加载 Launch Agent: {e}")
    else:
        # 如果取消勾选，则 unload 并删除 plist
        if plist_path.exists():
            try:
                subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
            except subprocess.CalledProcessError as e:
                print(f"无法卸载 Launch Agent: {e}")
            try:
                plist_path.unlink()
                print("已禁用开机自启，删除 Launch Agent 文件。")
            except OSError as e:
                print(f"无法删除 {plist_path}: {e}")
        else:
            print("未找到对应的 Launch Agent 文件，无需删除。")

def on_chk_change(*args):
    save_autostart_state(chk_autostart.get())
    toggle_autostart_mac(chk_autostart.get())

proxy_state = 0

def set_general_proxy():
    global proxy_state
    try:
        # 先执行 close.sh 以确保先杀掉先前可能残留的 xray 进程
        subprocess.run(["/bin/bash", resource_path("close.sh")], check=True)
        # 再执行 internet.sh 启动 xray 并设置代理
        subprocess.run(["/bin/bash", resource_path("internet.sh")], check=True)
        messagebox.showinfo("Information", "加速设置成功")
        btn_general_proxy.config(state="disabled")
        btn_close_proxy.config(state="normal")
        proxy_state = 1
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Failed to set general proxy: {e}")

def close_proxy():
    global proxy_state
    try:
        subprocess.run(["/bin/bash", resource_path("close.sh")], check=True)
        messagebox.showinfo("Information", "加速已关闭")
        btn_close_proxy.config(state="disabled")
        btn_general_proxy.config(state="normal")
        proxy_state = 0
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Failed to close proxy: {e}")

def on_closing():
    close_state = btn_close_proxy["state"]
    general_state = btn_general_proxy["state"]
    if close_state == "normal":
        if general_state == "disabled":  # 说明此时加速是开的
            try:
                subprocess.run(["/bin/bash", resource_path("close.sh")], check=True)
                messagebox.showinfo("Information", "加速已暂时关闭")
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"Failed to close proxy on exit: {e}")
    window.destroy()

def save_uuid(uuid):
    with open(get_persistent_path("uuid.txt"), "w", encoding="utf-8") as f:
        f.write(uuid)

def load_uuid():
    path_ = get_persistent_path("uuid.txt")
    if os.path.exists(path_):
        with open(path_, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

def remove_uuid_file():
    path_ = get_persistent_path("uuid.txt")
    if os.path.exists(path_):
        os.remove(path_)

def check_login():
    entered_uuid = entry_uuid.get().strip()
    try:
        response = requests.post("https://vvv.xiexievpn.com/login", json={"code": entered_uuid}, timeout=5)
        if response.status_code == 200:
            if chk_remember.get():
                save_uuid(entered_uuid)
            login_window.destroy()
            show_main_window(entered_uuid)
        else:
            remove_uuid_file()
            if response.status_code == 401:
                messagebox.showerror("Error", "无效的随机码")
            elif response.status_code == 403:
                messagebox.showerror("Error", "访问已过期")
            else:
                messagebox.showerror("Error", "服务器错误")
    except requests.exceptions.RequestException as e:
        remove_uuid_file()
        messagebox.showerror("Error", f"无法连接到服务器: {e}")

def on_remember_changed(*args):
    if not chk_remember.get():
        remove_uuid_file()

def do_adduser(uuid):
    try:
        requests.post(
            "https://vvv.xiexievpn.com/adduser",
            json={"code": uuid},
            timeout=2
        )
    except requests.exceptions.RequestException as e:
        print(f"调用 /adduser 出错或超时(可忽略)：{e}")

def poll_getuserinfo(uuid):
    try:
        response = requests.post(
            "https://vvv.xiexievpn.com/getuserinfo",
            json={"code": uuid},
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        response.raise_for_status()
        response_data = response.json()
        v2rayurl = response_data.get("v2rayurl", "")

        if v2rayurl:
            parse_and_write_config(v2rayurl)
            return
        else:
            window.after(3000, lambda: poll_getuserinfo(uuid))

    except requests.exceptions.RequestException as e:
        window.after(3000, lambda: poll_getuserinfo(uuid))

def parse_and_write_config(url_string):
    try:
        if not url_string.startswith("vless://"):
            messagebox.showerror("Error", "服务器返回的数据不符合预期格式（不是 vless:// 开头）")
            return

        uuid = url_string.split("@")[0].split("://")[1]
        domain = url_string.split("@")[1].split(":")[0].split(".")[0]

        config_data = {
            "log": {
                "loglevel": "error"
            },
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "rules": [
                    {
                        "type": "field",
                        "domain": ["geosite:category-ads-all"],
                        "outboundTag": "block"
                    },
                    {
                        "type": "field",
                        "protocol": ["bittorrent"],
                        "outboundTag": "direct"
                    },
                    {
                        "type": "field",
                        "domain": ["geosite:geolocation-!cn"],
                        "outboundTag": "proxy"
                    },
                    {
                        "type": "field",
                        "ip": ["geoip:cn", "geoip:private"],
                        "outboundTag": "proxy"
                    }
                ]
            },
            "inbounds": [
                {
                    "listen": "127.0.0.1",
                    "port": 10808,
                    "protocol": "socks"
                },
                {
                    "listen": "127.0.0.1",
                    "port": 1080,
                    "protocol": "http"
                }
            ],
            "outbounds": [
                {
                    "protocol": "vless",
                    "settings": {
                        "vnext": [
                            {
                                "address": f"{domain}.rocketchats.xyz",
                                "port": 443,
                                "users": [
                                    {
                                        "id": uuid,
                                        "encryption": "none",
                                        "flow": "xtls-rprx-vision"
                                    }
                                ]
                            }
                        ]
                    },
                    "streamSettings": {
                        "network": "tcp",
                        "security": "reality",
                        "realitySettings": {
                            "show": False,
                            "fingerprint": "chrome",
                            "serverName": f"{domain}.rocketchats.xyz",
                            "publicKey": "mUzqKeHBc-s1m03iD8Dh1JoL2B9JwG5mMbimEoJ523o",
                            "shortId": "",
                            "spiderX": ""
                        }
                    },
                    "tag": "proxy"
                },
                {
                    "protocol": "freedom",
                    "tag": "direct"
                },
                {
                    "protocol": "blackhole",
                    "tag": "block"
                }
            ]
        }

        with open(resource_path("config.json"), "w", encoding="utf-8") as config_file:
            json.dump(config_data, config_file, indent=4)

    except Exception as e:
        print(f"提取配置信息时发生错误: {e}")
        messagebox.showerror("Error", f"提取配置信息时发生错误: {e}")

def fetch_config_data(uuid):
    try:
        response = requests.post(
            "https://vvv.xiexievpn.com/getuserinfo",
            json={"code": uuid},
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        response.raise_for_status()
        response_data = response.json()
        v2rayurl = response_data.get("v2rayurl", "")
        zone = response_data.get("zone", "")

        if not v2rayurl and not zone:
            print("v2rayurl 和 zone 都为空，先调用 /adduser...")
            do_adduser(uuid)
            window.after(10, lambda: poll_getuserinfo(uuid))
        elif not v2rayurl:
            window.after(10, lambda: poll_getuserinfo(uuid))
        else:
            parse_and_write_config(v2rayurl)

    except requests.exceptions.RequestException as e:
        print(f"无法连接到服务器: {e}")
        messagebox.showerror("Error", f"无法连接到服务器: {e}")

def show_main_window(uuid):
    global window, btn_general_proxy, btn_close_proxy, chk_autostart
    window = tk.Tk()
    window.title("谢谢网络加速器")
    window.geometry("300x250")

    # macOS 上图标可以使用 .icns，或者干脆省略
    try:
        window.iconbitmap(resource_path("favicon.icns"))
    except Exception:
        pass

    window.protocol("WM_DELETE_WINDOW", on_closing)

    btn_general_proxy = tk.Button(window, text="打开加速", command=set_general_proxy)
    btn_close_proxy = tk.Button(window, text="关闭加速", command=close_proxy)
    btn_general_proxy.pack(pady=10)
    btn_close_proxy.pack(pady=10)

    # 开机自启
    chk_autostart = tk.BooleanVar()
    chk_autostart.set(load_autostart_state())
    chk_autostart.trace_add("write", on_chk_change)
    chk_autostart_button = tk.Checkbutton(window, text="开机自启动（示例）", variable=chk_autostart)
    chk_autostart_button.pack(pady=10)

    # 切换区域超链接
    lbl_switch_region = tk.Label(window, text="切换区域", fg="blue", cursor="hand2")
    lbl_switch_region.pack(pady=5)
    lbl_switch_region.bind("<Button-1>", lambda event: (
        messagebox.showinfo("切换区域", "切换区域后需重启此应用程序"),
        webbrowser.open(f"https://v.getsteamcard.com/app.html?code={uuid}")
    ))

    # 进入主窗口时尝试获取配置
    fetch_config_data(uuid)

    window.deiconify()
    # 让窗口置顶一下再取消，类似 Windows 版
    window.attributes('-topmost', True)
    window.attributes('-topmost', False)

    window.mainloop()

login_window = tk.Tk()
login_window.title("登录")
login_window.geometry("300x200")
try:
    login_window.iconbitmap(resource_path("favicon.icns"))
except Exception:
    pass

label_uuid = tk.Label(login_window, text="请输入随机码:")
label_uuid.pack(pady=10)

entry_uuid = tk.Entry(login_window)
entry_uuid.pack(pady=5)

# 在 macOS 下，Tk 默认对 Ctrl+X/C/V/A 的支持不完善，下面的绑定只是示例
entry_uuid.bind("<Command-a>", lambda event: entry_uuid.select_range(0, tk.END))  
entry_uuid.bind("<Command-c>", lambda event: login_window.clipboard_append(entry_uuid.selection_get()))
entry_uuid.bind("<Command-v>", lambda event: entry_uuid.insert(tk.INSERT, login_window.clipboard_get()))

# 右键菜单示例
menu = Menu(entry_uuid, tearoff=0)
def copy_text():
    try:
        login_window.clipboard_clear()
        login_window.clipboard_append(entry_uuid.selection_get())
    except:
        pass

def paste_text():
    try:
        entry_uuid.insert(tk.INSERT, login_window.clipboard_get())
    except:
        pass

def select_all():
    entry_uuid.select_range(0, tk.END)

menu.add_command(label="复制", command=copy_text)
menu.add_command(label="粘贴", command=paste_text)
menu.add_command(label="全选", command=select_all)

def show_context_menu(event):
    menu.post(event.x_root, event.y_root)

entry_uuid.bind("<Button-2>", show_context_menu)
entry_uuid.bind("<Button-3>", show_context_menu)

chk_remember = tk.BooleanVar()
chk_remember_button = tk.Checkbutton(login_window, text="下次自动登录", variable=chk_remember)
chk_remember_button.pack(pady=5)
chk_remember.trace_add("write", on_remember_changed)

btn_login = tk.Button(login_window, text="登录", command=check_login)
btn_login.pack(pady=10)

saved_uuid = load_uuid()
if saved_uuid:
    entry_uuid.insert(0, saved_uuid)
    check_login()

login_window.mainloop()