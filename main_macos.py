#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import messagebox, Menu, ttk
import subprocess
import os
import sys
import requests
import json
import webbrowser
import platform
from pathlib import Path
import textwrap
import urllib.parse
import threading
import tempfile
import zipfile
import shutil
import locale

# 当前版本号
CURRENT_VERSION = "1.0.7" 

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

lang_data = {}

def get_system_language():
    try:
        output = subprocess.check_output(["defaults", "read", "-g", "AppleLocale"], text=True).strip()
        if output.startswith(('zh_CN', 'zh_TW', 'zh_HK', 'zh_SG')):
            return 'zh'
    except:
        pass
    return 'en'

def load_language():
    global lang_data
    try:
        lang_path = resource_path("languages.json")
        if os.path.exists(lang_path):
            with open(lang_path, "r", encoding="utf-8") as f:
                languages = json.load(f)
            system_lang = get_system_language()
            lang_data = languages.get(system_lang, languages['en'])
        else:
            lang_data = {} # 兜底
    except Exception as e:
        print(f"Language load error: {e}")
        lang_data = {}

def get_text(key, default=None):
    return lang_data.get(key, default if default else key)

def get_message(key, default=None):
    return lang_data.get("messages", {}).get(key, default if default else key)

load_language()

# ----------------- 路径与持久化 -----------------
def get_persistent_path(filename):
    if platform.system() == "Darwin":
        home = os.path.expanduser("~")
        app_support_dir = os.path.join(home, "Library", "Application Support", "XieXieVPN")
        os.makedirs(app_support_dir, exist_ok=True)
        return os.path.join(app_support_dir, filename)
    else:
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

# ----------------- 自动更新模块 (macOS专用) -----------------
def compare_versions(version1, version2):
    try:
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))
        for i in range(max_len):
            if v1_parts[i] < v2_parts[i]: return -1
            elif v1_parts[i] > v2_parts[i]: return 1
        return 0
    except: return 0

def download_file(url, local_path):
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def perform_macos_update(download_url):
    current_exe = sys.executable
    current_app_path = None
    
    if ".app/" in current_exe:
        current_app_path = current_exe.split(".app/")[0] + ".app"
    
    if not current_app_path:
        messagebox.showerror("Error", "Cannot detect App path. Please download manually.")
        return

    # 显示进度窗
    dl_win = tk.Toplevel()
    dl_win.title(get_text("updating"))
    dl_win.geometry("300x100")
    tk.Label(dl_win, text=get_message("updating")).pack(pady=20)
    ttk.Progressbar(dl_win, mode='indeterminate').pack(fill='x', padx=20)
    dl_win.update()

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "update.zip")
    
    if not download_file(download_url, zip_path):
        dl_win.destroy()
        messagebox.showerror("Error", get_message("download_failed"))
        return
        
    dl_win.destroy()

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        # 寻找新 .app
        new_app_name = None
        for item in os.listdir(temp_dir):
            if item.endswith(".app"):
                new_app_name = item
                break
        
        if not new_app_name:
            raise Exception("No .app found in update package")

        new_app_full_path = os.path.join(temp_dir, new_app_name)
        app_parent_dir = os.path.dirname(current_app_path)
        
        # 生成更新脚本
        update_script = os.path.join(temp_dir, "update.sh")
        script_content = textwrap.dedent(f"""\
            #!/bin/bash
            sleep 2
            rm -rf "{current_app_path}"
            mv "{new_app_full_path}" "{os.path.join(app_parent_dir, new_app_name)}"
            xattr -cr "{os.path.join(app_parent_dir, new_app_name)}"
            open "{os.path.join(app_parent_dir, new_app_name)}"
            rm -rf "{temp_dir}"
        """)
        
        with open(update_script, "w") as f:
            f.write(script_content)
        os.chmod(update_script, 0o755)
        subprocess.Popen(["/bin/bash", update_script])
        sys.exit(0)

    except Exception as e:
        messagebox.showerror("Error", f"Update failed: {e}")

def check_for_updates():
    try:
        response = requests.get("https://xiexievpn.com/cn/mac/version.json", timeout=5)
        if response.status_code == 200:
            info = response.json()
            latest = info.get("version", "0.0.0")
            min_ver = info.get("minVersion", "0.0.0")
            # 假设 JSON 中 mac 下载链接字段为 mac_url，如果没有则尝试默认
            download_url = info.get("mac_url", "https://xiexievpn.com/mac/XieXieVPN-mac.zip")

            if compare_versions(CURRENT_VERSION, latest) < 0:
                is_force = compare_versions(CURRENT_VERSION, min_ver) < 0
                msg = f"{get_message('optional_update_msg')}\n{get_message('version_label')}: {latest}"
                
                if is_force:
                    messagebox.showinfo(get_message("update_required"), get_message("force_update_msg"))
                    perform_macos_update(download_url)
                else:
                    if messagebox.askyesno(get_message("update_available"), msg):
                        perform_macos_update(download_url)
    except Exception as e:
        print(f"Update check error: {e}")

def grant_permission(path):
    if os.path.exists(path):
        os.chmod(path, 0o755)

def run_admin_script(script_name):
    script_full_path = resource_path(script_name)
    cmd = f'''do shell script "/bin/bash \\"{script_full_path}\\"" with administrator privileges'''
    try:
        subprocess.run(["osascript", "-e", cmd], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def toggle_autostart_mac(should_enable: bool):
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    plist_name = "com.xiexievpn.launcher.plist"
    plist_path = launch_agents_dir / plist_name

    if should_enable:
        program_executable = sys.executable 
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
                </array>
                <key>RunAtLoad</key>
                <true/>
            </dict>
            </plist>
        """)
        with open(plist_path, "w", encoding="utf-8") as f:
            f.write(plist_content)
        try:
            subprocess.run(["launchctl", "unload", str(plist_path)], check=False, stderr=subprocess.DEVNULL)
            subprocess.run(["launchctl", "load", str(plist_path)], check=True)
        except Exception: pass
    else:
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], check=False, stderr=subprocess.DEVNULL)
            try: plist_path.unlink()
            except: pass

def on_chk_change(*args):
    save_autostart_state(chk_autostart.get())
    toggle_autostart_mac(chk_autostart.get())

proxy_state = 0

def set_general_proxy():
    global proxy_state
    grant_permission(resource_path("xray"))
    grant_permission(resource_path("internet.sh"))
    grant_permission(resource_path("close.sh"))

    if run_admin_script("internet.sh"):
        messagebox.showinfo(get_text("app_title"), get_message("vpn_setup_success"))
        btn_general_proxy.config(state="disabled")
        btn_close_proxy.config(state="normal")
        proxy_state = 1
    else:
        messagebox.showerror("Error", "Permission Denied")
        
def close_proxy():
    global proxy_state
    if run_admin_script("close.sh"):
        messagebox.showinfo(get_text("app_title"), get_message("vpn_closed"))
        btn_close_proxy.config(state="disabled")
        btn_general_proxy.config(state="normal")
        proxy_state = 0
    else:
        messagebox.showerror("Error", "Failed to close")

def on_closing():
    if btn_close_proxy["state"] == "normal":
        try:
            subprocess.run(["/bin/bash", resource_path("close.sh")], check=True)
            messagebox.showinfo(get_text("app_title"), get_message("vpn_temp_closed"))
        except: pass
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
        response = requests.post("https://vvv.xiexievpn.com/login", json={"code": entered_uuid}, timeout=10)
        if response.status_code == 200:
            if chk_remember.get():
                save_uuid(entered_uuid)
            login_window.destroy()
            show_main_window(entered_uuid)
        else:
            remove_uuid_file()
            if response.status_code == 401:
                messagebox.showerror("Error", get_message("invalid_code"))
            elif response.status_code == 403:
                messagebox.showerror("Error", get_message("expired"))
            else:
                messagebox.showerror("Error", get_message("server_error"))
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"{get_message('connection_error')}: {e}")

def on_remember_changed(*args):
    if not chk_remember.get():
        remove_uuid_file()

def do_adduser(uuid):
    try:
        requests.post("https://vvv.xiexievpn.com/adduser", json={"code": uuid}, timeout=2)
    except: pass

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
    except:
        window.after(3000, lambda: poll_getuserinfo(uuid))

def parse_and_write_config(url_string):
    try:
        if not url_string.startswith("vless://"): return
        uuid = url_string.split("@")[0].split("://")[1]
        domain = url_string.split("@")[1].split(":")[0].split(".")[0]

        try:
            query_part = url_string.split("?")[1].split("#")[0]
            params = urllib.parse.parse_qs(query_part)
            public_key = params.get('pbk', [''])[0] 
            short_id = params.get('sid', [''])[0]    
            sni = params.get('sni', [f"{domain}.rocketchats.xyz"])[0].replace("www.", "")
            if not public_key: public_key = "mUzqKeHBc-s1m03iD8Dh1JoL2B9JwG5mMbimEoJ523o" 
            if not short_id: short_id = "" 
        except:
            public_key = "mUzqKeHBc-s1m03iD8Dh1JoL2B9JwG5mMbimEoJ523o"
            short_id = ""
            sni = f"{domain}.rocketchats.xyz"

        config_data = {
            "log": {"loglevel": "error"},
            "dns": {
                "servers": [
                    {"tag": "bootstrap", "address": "223.5.5.5", "domains": [], "expectIPs": ["geoip:cn"], "detour": "direct"},
                    # --- 重要修复: 原代码此处末尾有空格 ---
                    {"tag": "remote-doh", "address": "https://1.1.1.1/dns-query", "detour": "proxy"},
                    "localhost"
                ],
                "queryStrategy": "UseIPv4"
            },
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "rules": [
                    {"type": "field", "inboundTag": ["dns-in"], "outboundTag": "proxy"},
                    {"type": "field", "domain": ["geosite:category-ads-all"], "outboundTag": "block"},
                    {"type": "field", "protocol": ["bittorrent"], "outboundTag": "direct"},
                    {"type": "field", "domain": ["geosite:geolocation-!cn"], "outboundTag": "proxy"},
                    {"type": "field", "ip": ["geoip:cn", "geoip:private"], "outboundTag": "direct"}
                ]
            },
            "inbounds": [
                {"tag": "dns-in", "listen": "127.0.0.1", "port": 53, "protocol": "dokodemo-door", "settings": {"address": "8.8.8.8", "port": 53, "network": "tcp,udp"}},
                {"listen": "127.0.0.1", "port": 10808, "protocol": "socks"},
                {"listen": "127.0.0.1", "port": 1080, "protocol": "http"}
            ],
            "outbounds": [
                {
                    "protocol": "vless",
                    "settings": {
                        "vnext": [{
                            "address": f"{domain}.rocketchats.xyz", "port": 443, 
                            "users": [{"id": uuid, "encryption": "none", "flow": "xtls-rprx-vision"}]
                        }]
                    },
                    "streamSettings": {
                        "network": "tcp", "security": "reality",
                        "realitySettings": {
                            "show": False, "fingerprint": "chrome", "serverName": sni, 
                            "publicKey": public_key, "shortId": short_id, "spiderX": ""
                        }
                    },
                    "tag": "proxy"
                },
                {"protocol": "freedom", "tag": "direct"},
                {"protocol": "blackhole", "tag": "block"}
            ]
        }
        
        with open(get_persistent_path("config.json"), "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)

    except Exception as e:
        messagebox.showerror("Error", f"Config Error: {e}")

def fetch_config_data(uuid):
    try:
        response = requests.post(
            "https://vvv.xiexievpn.com/getuserinfo",
            json={"code": uuid},
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        v2rayurl = data.get("v2rayurl", "")
        if not v2rayurl:
            do_adduser(uuid)
            window.after(10, lambda: poll_getuserinfo(uuid))
        else:
            parse_and_write_config(v2rayurl)
    except: pass

def show_main_window(uuid):
    global window, btn_general_proxy, btn_close_proxy, chk_autostart
    window = tk.Tk()
    window.title(get_text("app_title"))
    window.geometry("300x250")

    try: window.iconbitmap(resource_path("favicon.icns"))
    except: pass
    window.protocol("WM_DELETE_WINDOW", on_closing)

    btn_general_proxy = tk.Button(window, text=get_text("open_vpn"), command=set_general_proxy)
    btn_close_proxy = tk.Button(window, text=get_text("close_vpn"), command=close_proxy)
    btn_general_proxy.pack(pady=10)
    btn_close_proxy.pack(pady=10)

    chk_autostart = tk.BooleanVar()
    chk_autostart.set(load_autostart_state())
    chk_autostart.trace_add("write", on_chk_change)
    tk.Checkbutton(window, text=get_text("autostart"), variable=chk_autostart).pack(pady=10)

    lbl = tk.Label(window, text=get_text("switch_region"), fg="blue", cursor="hand2")
    lbl.pack(pady=5)
    lbl.bind("<Button-1>", lambda e: (
        messagebox.showinfo(get_text("switch_region"), get_message("switch_region_msg")),
        webbrowser.open(f"https://cn.xiexievpn.com/app.html?code={uuid}")
    ))

    fetch_config_data(uuid)
    
    # 异步检查更新
    threading.Thread(target=check_for_updates, daemon=True).start()

    window.deiconify()
    window.attributes('-topmost', True)
    window.attributes('-topmost', False)
    window.mainloop()

# ----------------- 登录窗口 -----------------
login_window = tk.Tk()
login_window.title(get_text("login_title"))
login_window.geometry("300x200")
try: login_window.iconbitmap(resource_path("favicon.icns"))
except: pass

tk.Label(login_window, text=get_text("login_prompt")).pack(pady=10)
entry_uuid = tk.Entry(login_window)
entry_uuid.pack(pady=5)

# Mac 快捷键兼容
entry_uuid.bind("<Command-a>", lambda e: entry_uuid.select_range(0, tk.END))
entry_uuid.bind("<Command-c>", lambda e: login_window.clipboard_append(entry_uuid.selection_get() if entry_uuid.selection_present() else ""))
entry_uuid.bind("<Command-v>", lambda e: entry_uuid.insert(tk.INSERT, login_window.clipboard_get()))

# 右键菜单
menu = Menu(entry_uuid, tearoff=0)
menu.add_command(label=get_text("copy", "Copy"), command=lambda: login_window.clipboard_append(entry_uuid.selection_get() if entry_uuid.selection_present() else ""))
menu.add_command(label=get_text("paste", "Paste"), command=lambda: entry_uuid.insert(tk.INSERT, login_window.clipboard_get()))
def show_context_menu(event): menu.post(event.x_root, event.y_root)
entry_uuid.bind("<Button-2>", show_context_menu)
entry_uuid.bind("<Button-3>", show_context_menu)

chk_remember = tk.BooleanVar()
tk.Checkbutton(login_window, text=get_text("auto_login"), variable=chk_remember).pack(pady=5)
chk_remember.trace_add("write", on_remember_changed)

tk.Button(login_window, text=get_text("login_button"), command=check_login).pack(pady=10)

saved_uuid = load_uuid()
if saved_uuid:
    entry_uuid.insert(0, saved_uuid)
    check_login()

login_window.mainloop()

