#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox, Menu, ttk
import subprocess
import os
import sys
import requests
from requests.adapters import HTTPAdapter
import json
import webbrowser
import platform
import urllib.parse
import locale
import threading
import time
import tempfile
import shutil
import base64
import socket
import concurrent.futures
import random
import fcntl
import zipfile
import textwrap
from pathlib import Path

CURRENT_VERSION = "1.0.10"
SUB_DOMAIN = "sub.xiexievpn.com"
API_ENDPOINTS = [
    "https://payapi.xiexievpn.com",
    "https://vvv.xiexievpn.com"
]

proxy_state = 0
is_manual_switching = False
pending_autostart = False
current_region = None
current_uuid = None
current_protocol = None
window = None
config_ready = False
protocol_label = None
region_label = None
penalized_protocol = None
penalty_until = 0
current_node_url = None
login_repair_done = False
is_updating = False
lock_file_handle = None

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
        primary = os.path.join(base_path, relative_path)
        if os.path.exists(primary) or not relative_path:
            return primary
        contents_dir = os.path.dirname(base_path)
        for sub in ("Resources", "Frameworks", "MacOS"):
            alt = os.path.join(contents_dir, sub, relative_path)
            if os.path.exists(alt):
                return alt
        return primary
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)


def get_persistent_path(filename):
    home = os.path.expanduser("~")
    if platform.system() == "Darwin":
        folder = os.path.join(home, "Library", "Application Support", "XieXieVPN")
    else:
        folder = os.path.join(home, ".XieXieVPN")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)


def ensure_runtime_rulesets():
    for srs_name in ("geoip-cn.srs", "geosite-cn.srs"):
        src = resource_path(srs_name)
        dst = get_persistent_path(srs_name)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass


def get_system_language():
    try:
        lang_code, _ = locale.getdefaultlocale()
        if lang_code and lang_code.startswith(('zh_CN', 'zh_TW', 'zh_HK', 'zh_SG', 'zh')):
            return 'zh'
    except Exception:
        pass
    try:
        output = subprocess.check_output(["defaults", "read", "-g", "AppleLocale"], text=True, timeout=2).strip()
        if output.startswith(('zh_CN', 'zh_TW', 'zh_HK', 'zh_SG', 'zh')):
            return 'zh'
    except Exception:
        pass
    return 'en'


def load_language():
    global lang_data
    try:
        with open(resource_path("languages.json"), "r", encoding="utf-8") as f:
            languages = json.load(f)
        system_lang = get_system_language()
        lang_data = languages.get(system_lang, languages['en'])
    except Exception:
        lang_data = {
            "app_title": "xiexie vpn",
            "login_title": "login",
            "login_prompt": "your access code:",
            "open_vpn": "open vpn",
            "close_vpn": "close vpn",
            "autostart": "autostart",
            "switch_region": "switch region",
            "auto_login": "automatically login next time",
            "login_button": "login",
            "copy": "copy",
            "paste": "paste",
            "select_all": "select all",
            "region_url": "https://xiexievpn.com/cn/app.html",
            "messages": {}
        }

    if "protocol_label" not in lang_data:
        lang_data["protocol_label"] = "Protocol"
    if "protocol_auto" not in lang_data:
        lang_data["protocol_auto"] = "Auto"
    msgs = lang_data.get("messages", {})
    if "speed_testing" not in msgs:
        msgs["speed_testing"] = "Speed testing..."
    if "speed_test_failed" not in msgs:
        msgs["speed_test_failed"] = "Speed test failed"
    if "degrading" not in msgs:
        msgs["degrading"] = "Network blocked, smart fallback..."
    if "repairing_network" not in msgs:
        msgs["repairing_network"] = "Resetting system network..."
    if "repair_failed" not in msgs:
        msgs["repair_failed"] = "Network self-repair failed. Startup will continue."
    lang_data["messages"] = msgs


def get_text(key):
    return lang_data.get(key, key)


def get_message(key):
    return lang_data.get("messages", {}).get(key, key)


load_language()


def acquire_single_instance_lock():
    global lock_file_handle
    lock_path = get_persistent_path("xiexievpn.lock")
    try:
        lock_file_handle = open(lock_path, "w")
        fcntl.lockf(lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file_handle.write(str(os.getpid()))
        lock_file_handle.flush()
        return True
    except (IOError, OSError):
        return False


def release_single_instance_lock():
    global lock_file_handle
    if lock_file_handle:
        try:
            fcntl.lockf(lock_file_handle, fcntl.LOCK_UN)
            lock_file_handle.close()
        except Exception:
            pass
        lock_file_handle = None


def compare_versions(version1, version2):
    try:
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))
        for i in range(max_len):
            if v1_parts[i] < v2_parts[i]:
                return -1
            elif v1_parts[i] > v2_parts[i]:
                return 1
        return 0
    except Exception:
        return 0


def _validate_zip_file(local_path, expected_size=None):
    try:
        if not os.path.exists(local_path):
            return False
        actual_size = os.path.getsize(local_path)
        if expected_size and actual_size != expected_size:
            return False
        if actual_size < 512 * 1024:
            return False
        with open(local_path, 'rb') as f:
            return f.read(4) == b'PK\x03\x04'
    except Exception:
        return False


def download_file(url, local_path, progress_callback=None):
    no_proxy = {"http": None, "https": None}
    chunk_span = 2 * 1024 * 1024
    read_block = 65536
    max_workers = 6

    session = requests.Session()
    session.trust_env = False
    adapter = HTTPAdapter(pool_connections=8, pool_maxsize=8)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    try:
        total_size = 0
        supports_range = False
        try:
            with session.get(
                url,
                headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"},
                stream=True,
                timeout=(8, 15),
                proxies=no_proxy
            ) as probe:
                if probe.status_code == 206:
                    cr = probe.headers.get("Content-Range", "")
                    if "/" in cr:
                        total_part = cr.split("/")[-1].strip()
                        if total_part.isdigit():
                            total_size = int(total_part)
                            supports_range = total_size > chunk_span
        except Exception:
            pass

        if supports_range and total_size > 0:
            try:
                if progress_callback:
                    progress_callback(0, total_size)
                ranges = [
                    (start, min(start + chunk_span - 1, total_size - 1))
                    for start in range(0, total_size, chunk_span)
                ]
                lock = threading.Lock()
                cancel_event = threading.Event()
                downloaded = [0]

                with open(local_path, 'wb') as out_f:
                    out_f.truncate(total_size)

                    def fetch_slice(byte_range):
                        start, end = byte_range
                        expected_len = end - start + 1
                        for attempt in range(3):
                            if cancel_event.is_set():
                                raise RuntimeError("Download cancelled")
                            attempt_bytes = 0
                            buf = bytearray()
                            try:
                                with session.get(
                                    url,
                                    headers={
                                        "Range": f"bytes={start}-{end}",
                                        "Accept-Encoding": "identity"
                                    },
                                    stream=True,
                                    timeout=(8, 25),
                                    proxies=no_proxy
                                ) as resp:
                                    if resp.status_code != 206:
                                        raise RuntimeError(f"HTTP {resp.status_code}")
                                    for piece in resp.iter_content(chunk_size=read_block):
                                        if cancel_event.is_set():
                                            raise RuntimeError("Download cancelled")
                                        if not piece:
                                            continue
                                        buf.extend(piece)
                                        n = len(piece)
                                        attempt_bytes += n
                                        with lock:
                                            downloaded[0] += n
                                            cur_dl = downloaded[0]
                                        if progress_callback:
                                            progress_callback(cur_dl, total_size)
                                if len(buf) != expected_len:
                                    raise RuntimeError("Incomplete slice")
                                with lock:
                                    out_f.seek(start)
                                    out_f.write(buf)
                                return True
                            except Exception:
                                if attempt_bytes:
                                    with lock:
                                        downloaded[0] = max(0, downloaded[0] - attempt_bytes)
                                        cur_dl = downloaded[0]
                                    if progress_callback:
                                        progress_callback(cur_dl, total_size)
                                if attempt == 2:
                                    cancel_event.set()
                                    raise
                                time.sleep(0.8 * (attempt + 1))

                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = [executor.submit(fetch_slice, r) for r in ranges]
                        for fut in futures:
                            fut.result()

                if _validate_zip_file(local_path, total_size):
                    return True
            except Exception:
                try:
                    if os.path.exists(local_path):
                        os.remove(local_path)
                except Exception:
                    pass

        for attempt in range(2):
            try:
                if progress_callback:
                    progress_callback(0, 0)
                with session.get(
                    url,
                    headers={"Accept-Encoding": "identity"},
                    stream=True,
                    timeout=(10, 30),
                    proxies=no_proxy
                ) as response:
                    response.raise_for_status()
                    expected_len = int(response.headers.get("Content-Length") or 0)
                    cur_dl = 0
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=read_block):
                            if not chunk:
                                continue
                            f.write(chunk)
                            cur_dl += len(chunk)
                            if progress_callback:
                                progress_callback(cur_dl, expected_len)
                if _validate_zip_file(local_path, expected_len if expected_len > 0 else None):
                    return True
            except Exception:
                try:
                    if os.path.exists(local_path):
                        os.remove(local_path)
                except Exception:
                    pass
                if attempt == 0:
                    time.sleep(1)
        return False
    finally:
        session.close()


def check_for_updates():
    session = requests.Session()
    session.trust_env = False
    try:
        no_proxy = {"http": None, "https": None}
        lang_dir = "cn" if get_system_language() == "zh" else "en"
        for check_url in (
            f"https://xiexievpn.com/{lang_dir}/macos/version.json",
            "https://xiexievpn.com/cn/macos/version.json"
        ):
            try:
                response = session.get(check_url, timeout=5, proxies=no_proxy)
                if response.status_code == 200:
                    update_info = response.json()
                    latest_version = update_info.get("version", "0.0.0")
                    min_version = update_info.get("minVersion", "0.0.0")
                    if compare_versions(CURRENT_VERSION, latest_version) < 0:
                        if compare_versions(CURRENT_VERSION, min_version) < 0:
                            update_info["updateType"] = "force"
                        return update_info
                    return None
            except Exception:
                continue
    except Exception:
        pass
    finally:
        session.close()
    return None


def download_and_replace(download_url=None):
    global is_updating
    is_updating = True
    target_url = download_url or "https://xiexievpn.com/cn/macos/XieXieVPN-mac.zip"
    candidate_urls = [target_url]
    for backup_url in (
        "https://xiexievpn.com/cn/macos/XieXieVPN-mac.zip",
        "https://xiexievpn.com/en/macos/XieXieVPN-mac.zip",
        "https://github.com/xiexievpn/macos/releases/latest/download/XieXieVPN-mac.zip"
    ):
        if backup_url not in candidate_urls:
            candidate_urls.append(backup_url)

    temp_dir = tempfile.mkdtemp(prefix="xiexievpn_mac_update_")
    temp_path = os.path.join(temp_dir, 'XieXieVPN-mac.zip')

    try:
        download_window = tk.Toplevel(window) if window else tk.Toplevel()
        download_window.title(get_text("app_title"))
        download_window.geometry("340x120")
        download_window.resizable(False, False)
        download_window.protocol("WM_DELETE_WINDOW", lambda: None)
        if window:
            download_window.transient(window)
            download_window.grab_set()

        tk.Label(download_window, text=get_message("updating"), font=("PingFang SC", 10, "bold")).pack(pady=(15, 5))
        progress = ttk.Progressbar(download_window, mode='determinate', maximum=100)
        progress.pack(pady=5, padx=20, fill='x')
        detail_label = tk.Label(download_window, text="0%", font=("PingFang SC", 8), fg="gray")
        detail_label.pack(pady=(2, 10))

        state = {
            "downloaded": 0,
            "total": 0,
            "done": False,
            "ok": False,
            "start_time": time.time()
        }

        def on_progress(dl_bytes, total_bytes):
            state["downloaded"] = dl_bytes
            state["total"] = total_bytes

        def worker():
            try:
                for u in candidate_urls:
                    state["downloaded"] = 0
                    state["total"] = 0
                    state["start_time"] = time.time()
                    if download_file(u, temp_path, progress_callback=on_progress):
                        state["ok"] = True
                        break
            except Exception:
                state["ok"] = False
            finally:
                state["done"] = True

        def finish_update():
            global is_updating
            try:
                if window:
                    download_window.grab_release()
                download_window.destroy()
            except Exception:
                pass

            if not state["ok"]:
                is_updating = False
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
                messagebox.showerror("Error", get_message("download_failed"))
                return

            try:
                if proxy_state == 1:
                    subprocess.run(
                        ["/bin/bash", resource_path("close.sh")],
                        capture_output=True,
                        timeout=5
                    )
            except Exception:
                pass

            try:
                extract_dir = os.path.join(temp_dir, "extracted")
                os.makedirs(extract_dir, exist_ok=True)
                res = subprocess.run(["ditto", "-x", "-k", temp_path, extract_dir], capture_output=True)
                if res.returncode != 0:
                    with zipfile.ZipFile(temp_path, 'r') as zf:
                        zf.extractall(extract_dir)

                new_app_path = None
                for root_dir, dirs, _ in os.walk(extract_dir):
                    for d in dirs:
                        if d.endswith(".app"):
                            new_app_path = os.path.join(root_dir, d)
                            break
                    if new_app_path:
                        break

                if not new_app_path:
                    raise RuntimeError("No .app bundle found in update archive")

                current_exe = sys.executable
                current_app_path = None
                if ".app/" in current_exe:
                    current_app_path = current_exe.split(".app/")[0] + ".app"
                if not current_app_path:
                    current_app_path = "/Applications/谢谢网络加速器.app"

                app_parent_dir = os.path.dirname(current_app_path)
                target_app_path = os.path.join(app_parent_dir, os.path.basename(new_app_path))

                update_script = os.path.join(temp_dir, "update_xiexievpn.sh")
                script_content = textwrap.dedent(f"""\
                    #!/bin/bash
                    sleep 2
                    rm -rf "{current_app_path}" 2>/dev/null || true
                    rm -rf "{target_app_path}" 2>/dev/null || true
                    mv "{new_app_path}" "{target_app_path}" 2>/dev/null || cp -R "{new_app_path}" "{target_app_path}"
                    xattr -cr "{target_app_path}" 2>/dev/null || true
                    open "{target_app_path}"
                    rm -rf "{temp_dir}"
                """)
                with open(update_script, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                os.chmod(update_script, 0o755)

                release_single_instance_lock()
                subprocess.Popen(["/bin/bash", update_script], start_new_session=True)
                sys.exit(0)
            except Exception as e:
                is_updating = False
                messagebox.showerror("Error", f"Update failed: {e}")

        def poll_progress():
            dl = state["downloaded"]
            total = state["total"]
            elapsed = max(0.1, time.time() - state["start_time"])
            speed = dl / elapsed
            speed_str = f"{speed / 1048576:.2f} MB/s" if speed >= 1048576 else f"{speed / 1024:.0f} KB/s"

            if total > 0:
                pct = min(100.0, dl * 100.0 / total)
                progress["value"] = pct
                detail_label.config(
                    text=f"{pct:.0f}%  ({dl / 1048576:.1f} / {total / 1048576:.1f} MB · {speed_str})"
                )
            elif dl > 0:
                detail_label.config(text=f"{dl / 1048576:.1f} MB · {speed_str}")

            if state["done"]:
                finish_update()
            else:
                download_window.after(150, poll_progress)

        threading.Thread(target=worker, daemon=True).start()
        download_window.after(150, poll_progress)
    except Exception as e:
        is_updating = False
        messagebox.showerror("Error", f"Update failed: {e}")


def show_update_dialog(update_info):
    global is_updating
    if is_updating:
        return
    update_type = update_info.get("updateType", "optional")
    version = update_info.get("version")
    notes = update_info.get("releaseNotes", "")
    download_url = (
        update_info.get("downloadUrl")
        or update_info.get("mac_url")
        or "https://xiexievpn.com/cn/macos/XieXieVPN-mac.zip"
    )
    if update_type == "force":
        messagebox.showinfo(get_message("update_required"), f"{get_message('force_update_msg')}\n\n{version}\n\n{notes}")
        download_and_replace(download_url)
    else:
        if messagebox.askyesno(get_message("update_available"), f"{get_message('optional_update_msg')}\n\n{version}\n\n{notes}"):
            download_and_replace(download_url)


AUTOSTART_FILE = get_persistent_path("autostart_state.txt")


def save_autostart_state(state: bool):
    with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
        f.write("1" if state else "0")


def load_autostart_state() -> bool:
    if os.path.exists(AUTOSTART_FILE):
        with open(AUTOSTART_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() == "1"
    return False


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


def test_tcp_ping(host, port):
    try:
        st = time.time()
        with socket.create_connection((host, int(port)), timeout=3):
            return (time.time() - st) * 1000
    except Exception:
        return float('inf')


def post_api_with_failover(path, payload, timeouts=(7, 10), stop_statuses=(), treat_read_timeout_as_sent=False):
    no_proxy = {"http": None, "https": None}
    last_err = None
    last_resp = None
    for idx, base_url in enumerate(API_ENDPOINTS):
        timeout_val = timeouts[idx] if idx < len(timeouts) else timeouts[-1]
        try:
            resp = requests.post(
                f"{base_url}{path}",
                json=payload,
                headers={"Content-Type": "application/json"},
                proxies=no_proxy,
                timeout=timeout_val
            )
            if (200 <= resp.status_code < 300) or (400 <= resp.status_code < 500) or (resp.status_code in stop_statuses):
                return resp
            last_resp = resp
        except requests.exceptions.ReadTimeout as e:
            if treat_read_timeout_as_sent:
                return None
            last_err = e
        except Exception as e:
            last_err = e
    if last_resp is not None:
        return last_resp
    raise last_err if last_err else RuntimeError("Network error")


def generate_singbox_config(proxy_outbound):
    ensure_runtime_rulesets()
    control_plane_domains = [
        "payapi.xiexievpn.com",
        "vvv.xiexievpn.com",
        "sub.xiexievpn.com",
        "xiexievpn.com"
    ]
    geoip_path = get_persistent_path("geoip-cn.srs")
    if not os.path.exists(geoip_path):
        geoip_path = os.path.abspath(resource_path("geoip-cn.srs"))
    geosite_path = get_persistent_path("geosite-cn.srs")
    if not os.path.exists(geosite_path):
        geosite_path = os.path.abspath(resource_path("geosite-cn.srs"))

    rule_sets = []
    route_rules = [
        {"protocol": "dns", "outbound": "dns-out"},
        {"port": 53, "outbound": "dns-out"},
        {"domain_suffix": control_plane_domains, "outbound": "direct"},
        {"protocol": "bittorrent", "outbound": "direct"},
        {"ip_is_private": True, "outbound": "direct"}
    ]
    dns_rules = [
        {"outbound": "any", "server": "dns-local"},
        {"domain_suffix": control_plane_domains, "server": "dns-local"}
    ]

    active_rule_set_tags = []
    if os.path.exists(geoip_path):
        rule_sets.append({"tag": "geoip-cn", "type": "local", "format": "binary", "path": geoip_path})
        active_rule_set_tags.append("geoip-cn")
    if os.path.exists(geosite_path):
        rule_sets.append({"tag": "geosite-cn", "type": "local", "format": "binary", "path": geosite_path})
        active_rule_set_tags.append("geosite-cn")
        dns_rules.append({"rule_set": ["geosite-cn"], "server": "dns-local"})

    if active_rule_set_tags:
        route_rules.append({"rule_set": active_rule_set_tags, "outbound": "direct"})

    config_data = {
        "log": {"level": "error"},
        "dns": {
            "servers": [
                {"tag": "dns-remote", "address": "https://1.1.1.1/dns-query", "address_resolver": "dns-local", "detour": "proxy"},
                {"tag": "dns-local", "address": "223.5.5.5", "detour": "direct"}
            ],
            "rules": dns_rules,
            "final": "dns-remote",
            "strategy": "ipv4_only"
        },
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": 10808,
                "sniff": True,
                "sniff_override_destination": True
            },
            {
                "type": "mixed",
                "tag": "mixed-in2",
                "listen": "127.0.0.1",
                "listen_port": 1080,
                "sniff": True,
                "sniff_override_destination": True
            }
        ],
        "outbounds": [
            proxy_outbound,
            {"type": "direct", "tag": "direct"},
            {"type": "block", "tag": "block"},
            {"type": "dns", "tag": "dns-out"}
        ],
        "route": {
            "rule_set": rule_sets,
            "rules": route_rules,
            "auto_detect_interface": True,
            "final": "proxy"
        }
    }
    with open(get_persistent_path("config.json"), "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4)
    return True


def test_hy2_url_test(node):
    singbox_bin = resource_path("sing-box")
    if not os.path.exists(singbox_bin):
        return test_tcp_ping(node["host"], node["port"])

    temp_port = random.randint(30000, 39999)
    config = {
        "log": {"level": "fatal"},
        "inbounds": [{"type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": temp_port}],
        "outbounds": [{
            "type": "hysteria2", "tag": "proxy", "server": node["host"], "server_port": node["port"],
            "password": node.get("uuid", ""), "tls": {"enabled": True, "server_name": node.get("sni", node["host"]), "insecure": False}
        }]
    }
    config_path = os.path.join(tempfile.gettempdir(), f"hy2_test_{temp_port}.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f)

    proc = None
    try:
        os.chmod(singbox_bin, 0o755)
        proc = subprocess.Popen(
            [singbox_bin, "run", "-c", config_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(2)
        if proc.poll() is not None:
            return float('inf')

        proxies = {
            'http': f'http://127.0.0.1:{temp_port}',
            'https': f'http://127.0.0.1:{temp_port}'
        }
        st = time.time()
        resp = requests.get(
            "http://cp.cloudflare.com/generate_204",
            proxies=proxies,
            timeout=5
        )
        if resp.status_code == 204:
            return (time.time() - st) * 1000
        return float('inf')
    except Exception:
        return float('inf')
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        try:
            os.remove(config_path)
        except Exception:
            pass


def extract_subscription_links(links_text):
    normalized_text = links_text or ""

    if "://" not in normalized_text:
        try:
            pad = len(normalized_text) % 4
            if pad:
                normalized_text += "=" * (4 - pad)
            normalized_text = base64.b64decode(normalized_text).decode("utf-8")
        except Exception:
            pass

    links = []
    for line in normalized_text.strip().splitlines():
        line = line.strip()
        if line.startswith("vless://") or line.startswith("hysteria2://") or line.startswith("hy2://"):
            links.append(line)
    return links


def get_single_vless_link(links_text):
    links = extract_subscription_links(links_text)
    if len(links) == 1 and links[0].startswith("vless://"):
        return links[0]
    return None


def extract_region_from_link(link):
    try:
        if "#" not in link:
            return None
        frag = urllib.parse.unquote(link.split("#", 1)[1]).strip().lower()
        if not frag:
            return None

        if frag.endswith("-hy2"):
            frag = frag[:-4]

        if frag in FLAG_TO_REGION:
            return frag

        if frag in REGION_TO_FLAG:
            return REGION_TO_FLAG[frag]

        for aws_region, flag_code in REGION_TO_FLAG.items():
            if frag.startswith(aws_region):
                return flag_code

        return None
    except Exception:
        return None


def speed_test_nodes(links_text):
    nodes = []

    for line in extract_subscription_links(links_text):
        try:
            protocol = "vless" if line.startswith("vless") else "hy2"
            main_part = line.split("://")[1]
            host_port = main_part.split("@")[1].split("?")[0].split("/")[0]
            host_parts = host_port.split(":")
            host = host_parts[0]
            port = int(host_parts[1]) if len(host_parts) > 1 else 443
            node_info = {"protocol": protocol, "url": line, "host": host, "port": port}
            if protocol == "hy2":
                node_info["uuid"] = main_part.split("@")[0]
                query_part = main_part.split("?")[1].split("#")[0] if "?" in main_part else ""
                node_info["sni"] = urllib.parse.parse_qs(query_part).get('sni', [host])[0]
            nodes.append(node_info)
        except Exception:
            pass

    if not nodes:
        return None

    def test_node(node):
        if node["protocol"] == "hy2":
            node["ping"] = test_hy2_url_test(node)
        else:
            tcp_ping = test_tcp_ping(node["host"], node["port"])
            node["ping"] = tcp_ping * 3 + 100 if tcp_ping != float('inf') else float('inf')
        if penalized_protocol == node["protocol"] and time.time() < penalty_until:
            if node["ping"] != float('inf'):
                node["ping"] += 5000
        return node

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, max(1, len(nodes)))) as executor:
        results = list(executor.map(test_node, nodes))

    valid = [r for r in results if r["ping"] != float('inf')]
    if not valid:
        nodes[0]["ping"] = float('inf')
        return nodes[0]

    valid.sort(key=lambda x: x["ping"])
    best = valid[0]

    for n in valid:
        if n["protocol"] == "hy2" and n["ping"] - best["ping"] <= 50:
            best = n
            break
    return best


def write_vless_config(url_string):
    try:
        if not url_string.startswith("vless://"):
            return False
        uuid = url_string.split("@")[0].split("://")[1]
        main_part = url_string.split("@")[1]
        domain_port_part = main_part.split("?")[0]
        host = domain_port_part.split(":")[0]
        port = int(domain_port_part.split(":")[1]) if ":" in domain_port_part else 443

        domain = host.split(".")[0]
        query_part = url_string.split("?")[1].split("#")[0] if "?" in main_part else ""
        params = urllib.parse.parse_qs(query_part)

        sni = params.get('sni', [f"{domain}.rocketchats.xyz"])[0].replace("www.", "")
        public_key = params.get('pbk', [''])[0] or "mUzqKeHBc-s1m03iD8Dh1JoL2B9JwG5mMbimEoJ523o"
        short_id = params.get('sid', [''])[0]

        proxy_outbound = {
            "type": "vless", "tag": "proxy", "server": host, "server_port": port, "uuid": uuid, "flow": "xtls-rprx-vision",
            "tls": {
                "enabled": True, "server_name": sni,
                "utls": {"enabled": True, "fingerprint": "chrome"},
                "reality": {"enabled": True, "public_key": public_key, "short_id": short_id}
            },
            "packet_encoding": "xudp"
        }
        return generate_singbox_config(proxy_outbound)
    except Exception:
        return False


def write_hy2_config(url_string):
    try:
        main_part = url_string.split("://")[1]
        uuid = main_part.split("@")[0]
        host_port = main_part.split("@")[1].split("?")[0].split("/")[0]
        host = host_port.split(":")[0]
        port = int(host_port.split(":")[1]) if ":" in host_port else 443
        query_part = main_part.split("?")[1].split("#")[0] if "?" in main_part else ""
        sni = urllib.parse.parse_qs(query_part).get('sni', [host])[0]

        proxy_outbound = {
            "type": "hysteria2", "tag": "proxy", "server": host, "server_port": port, "password": uuid,
            "tls": {"enabled": True, "server_name": sni, "insecure": False}
        }
        return generate_singbox_config(proxy_outbound)
    except Exception:
        return False


def run_mac_script(script_name):
    script_path = resource_path(script_name)
    res_dir = resource_path("")
    cfg_dir = os.path.dirname(get_persistent_path("config.json"))
    os.chmod(script_path, 0o755)
    return subprocess.run(
        ["/bin/bash", script_path, res_dir, cfg_dir],
        capture_output=True,
        text=True
    )


def parse_and_write_config_async(links_text, callback=None, skip_speed_test=False, force_restart=False):
    global current_protocol, config_ready, pending_autostart

    if not skip_speed_test and 'protocol_label' in globals() and protocol_label and window:
        window.after(0, lambda: protocol_label.config(text=get_message("speed_testing"), fg="orange"))

    def task():
        global current_protocol, config_ready, pending_autostart, current_node_url, current_region
        if skip_speed_test:
            single_vless_link = get_single_vless_link(links_text)
            if single_vless_link:
                best_node = {"protocol": "vless", "url": single_vless_link, "ping": float('inf')}
            else:
                best_node = None
        else:
            best_node = speed_test_nodes(links_text)
        if not best_node:
            if 'protocol_label' in globals() and protocol_label and window:
                window.after(0, lambda: protocol_label.config(text=get_message("speed_test_failed"), fg="red"))
            if callback and window:
                window.after(0, lambda: callback(False))
            return

        if not force_restart and best_node["url"] == current_node_url and config_ready:
            if callback and window:
                window.after(0, lambda: callback(True))
            return

        if best_node["protocol"] == "vless":
            success = write_vless_config(best_node["url"])
        else:
            success = write_hy2_config(best_node["url"])

        if success:
            current_protocol = best_node["protocol"]
            config_ready = True
            current_node_url = best_node["url"]
            selected_region = extract_region_from_link(best_node["url"])
            if selected_region:
                current_region = selected_region

            def update_ui():
                global pending_autostart
                if 'protocol_label' in globals() and protocol_label:
                    p_text = "VLESS ⚡" if current_protocol == "vless" else "HY2 🚀"
                    ping_text = f"{int(best_node['ping'])}ms" if best_node['ping'] != float('inf') else "Blind"
                    if penalized_protocol and time.time() < penalty_until and current_protocol != penalized_protocol:
                        p_text += " (↓ fallback)"
                    protocol_label.config(text=f"{get_text('protocol_label')}: {p_text} ({ping_text})", fg="green")
                update_region_display()

                if pending_autostart:
                    pending_autostart = False
                    set_general_proxy(show_success_msg=False)
                elif proxy_state == 1:
                    run_mac_script("close.sh")
                    time.sleep(0.5)
                    run_mac_script("internet.sh")
                elif 'btn_general_proxy' in globals() and btn_general_proxy and proxy_state == 0:
                    btn_general_proxy.config(state="normal")

                if callback:
                    callback(True)

            if window:
                window.after(0, update_ui)
        else:
            if callback and window:
                window.after(0, lambda: callback(False))

    threading.Thread(target=task, daemon=True).start()


def fetch_subscription(uuid, from_watchdog=False):
    global current_region
    no_proxy = {"http": None, "https": None}

    def task():
        global current_region, current_protocol, penalized_protocol, penalty_until
        links_text = ""
        prev_region = current_region
        region_changed = False

        try:
            resp = requests.get(f"https://{SUB_DOMAIN}/sub/{uuid}?t={int(time.time())}", timeout=5, proxies=no_proxy)
            if resp.status_code == 200:
                links_text = resp.text.strip()
        except Exception:
            pass

        try:
            response = post_api_with_failover("/getuserinfo", {"code": uuid}, timeouts=(7, 10))
            if response.status_code == 200:
                data = response.json()
                zone = data.get("zone", "")
                v2rayurl = data.get("v2rayurl", "")

                if zone:
                    mapped_region = REGION_TO_FLAG.get(zone, zone)
                    if prev_region and prev_region != mapped_region:
                        region_changed = True
                    current_region = mapped_region
                    if window:
                        window.after(0, update_region_display)

                if not links_text and v2rayurl:
                    links_text = v2rayurl

                if not v2rayurl and not zone:
                    try:
                        post_api_with_failover(
                            "/adduser",
                            {"code": uuid},
                            timeouts=((2, 2), (2, 2)),
                            treat_read_timeout_as_sent=True
                        )
                    except Exception:
                        pass
                    if window:
                        window.after(3000, lambda: fetch_subscription(uuid, from_watchdog=from_watchdog))
                    return

                if not v2rayurl and zone:
                    if window:
                        window.after(3000, lambda: fetch_subscription(uuid, from_watchdog=from_watchdog))
                    return
        except Exception:
            pass

        if links_text:
            if from_watchdog and get_single_vless_link(links_text):
                penalized_protocol = None
                penalty_until = 0
                parse_and_write_config_async(links_text, skip_speed_test=True, force_restart=True)
            else:
                if from_watchdog:
                    if region_changed:
                        penalized_protocol = None
                        penalty_until = 0
                    else:
                        penalized_protocol = current_protocol
                        penalty_until = time.time() + 300
                        if 'protocol_label' in globals() and protocol_label and window:
                            window.after(0, lambda: protocol_label.config(
                                text=get_message("degrading"), fg="red"))
                parse_and_write_config_async(links_text, force_restart=from_watchdog)

    threading.Thread(target=task, daemon=True).start()


REGION_TO_FLAG = {
    "us-west-2": "us",
    "ap-northeast-2": "jp",
    "ap-northeast-1": "jj",
    "ap-southeast-1": "si",
    "eu-central-1": "ge"
}
FLAG_TO_REGION = {v: k for k, v in REGION_TO_FLAG.items()}
REGIONS = [
    ("jp", "ap-northeast-2"), ("us", "us-west-2"), ("jj", "ap-northeast-1"),
    ("si", "ap-southeast-1"), ("ge", "eu-central-1")
]


class RegionSelector(tk.Toplevel):
    def __init__(self, parent, current_zone, uuid):
        super().__init__(parent)
        self.parent = parent
        self.current_zone = current_zone
        self.uuid = uuid
        self.selected_flag = None
        self.switching = False
        self.max_progress = 0
        self.target_flag_code = None

        self.title(get_message("select_region"))
        self.geometry("480x360")
        try:
            self.iconbitmap(resource_path("favicon.icns"))
        except Exception:
            pass
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_window)

        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.title_label = tk.Label(main_frame, text=get_message("select_region"), font=("PingFang SC", 14, "bold"))
        self.title_label.pack(pady=(0, 15))

        self.current_label = tk.Label(main_frame, font=("PingFang SC", 10), fg="blue")
        self.current_label.pack(pady=(0, 10))

        txt = f"{get_message('current_region')}: {get_message(f'region_{current_zone}')}" if current_zone else f"{get_message('current_region')}: {get_message('region_loading')}"
        self.current_label.config(text=txt)

        self.create_flag_grid(main_frame)

    def force_ui_refresh(self):
        self.update_idletasks()
        self.update()

    def create_flag_grid(self, parent):
        flag_frame = tk.Frame(parent)
        flag_frame.pack(fill=tk.BOTH, expand=True)
        self.flag_buttons = {}
        for idx, (flag_code, aws_region) in enumerate(REGIONS):
            row = idx // 4
            col = idx % 4
            btn_frame = tk.Frame(flag_frame, relief=tk.SOLID, bd=1)
            btn_frame.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            flag_frame.grid_rowconfigure(row, weight=1)
            flag_frame.grid_columnconfigure(col, weight=1)
            try:
                flag_path = resource_path(f"flags/{flag_code}.png")
                if PIL_AVAILABLE and os.path.exists(flag_path):
                    pil_image = Image.open(flag_path).resize((40, 30), Image.Resampling.LANCZOS)
                    flag_image = ImageTk.PhotoImage(pil_image)
                    flag_label = tk.Label(btn_frame, image=flag_image, cursor="pointinghand")
                    flag_label.image = flag_image
                    flag_label.pack(pady=2)
                else:
                    flag_label = tk.Label(btn_frame, text=flag_code.upper(), font=("PingFang SC", 12, "bold"), cursor="pointinghand")
                    flag_label.pack(pady=2)

                name_label = tk.Label(btn_frame, text=get_message(f"region_{flag_code}"), font=("PingFang SC", 9), cursor="pointinghand")
                name_label.pack()

                for w in [flag_label, name_label, btn_frame]:
                    w.bind("<Button-1>", lambda e, f=flag_code: self.on_flag_click(f))

                self.flag_buttons[flag_code] = btn_frame
                if flag_code == self.current_zone:
                    self.highlight_flag(flag_code)
            except Exception:
                pass

    def highlight_flag(self, flag_code):
        for code, btn in self.flag_buttons.items():
            if code == flag_code:
                btn.config(relief=tk.RIDGE, bd=3, bg="#e8f5e9")
            else:
                btn.config(relief=tk.SOLID, bd=1)

    def on_flag_click(self, flag_code):
        if self.switching or flag_code == self.current_zone:
            return
        self.selected_flag = flag_code
        self.highlight_flag(flag_code)
        self.switch_region(flag_code)

    def switch_region(self, flag_code):
        global proxy_state, is_manual_switching
        is_manual_switching = True

        self.switching = True
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.was_vpn_on = (proxy_state == 1)

        if self.was_vpn_on:
            try:
                run_mac_script("close.sh")
            except Exception:
                pass

        self.max_progress = 0
        self.target_flag_code = flag_code
        self._update_progress_display(get_message("switching_region"))
        self.force_ui_refresh()

        for btn in self.flag_buttons.values():
            for child in btn.winfo_children():
                child.config(state="disabled")

        self.after(200, lambda: self._start_switch_thread(flag_code))

    def _start_switch_thread(self, flag_code):
        thread = threading.Thread(target=self._switch_region_thread, args=(flag_code,), daemon=True)
        thread.start()

    def _switch_region_thread(self, flag_code):
        max_retries = 2

        for attempt in range(max_retries):
            try:
                response = post_api_with_failover(
                    "/switch",
                    {"code": self.uuid, "newZone": flag_code},
                    timeouts=((8, 10), (10, 10)),
                    stop_statuses=(504,),
                    treat_read_timeout_as_sent=True
                )
                if response is None or response.status_code in [202, 504]:
                    self._poll_switch_status(flag_code)
                    return
                elif response.status_code == 200:
                    try:
                        v2rayurl = (response.json() or {}).get("v2rayurl", "").strip()
                    except Exception:
                        v2rayurl = ""
                    if v2rayurl:
                        self.after(0, lambda url=v2rayurl: self._handle_poll_success(url))
                    else:
                        self._wait_for_config_update()
                    return
                elif response.status_code == 403:
                    try:
                        err_data = response.json()
                    except Exception:
                        err_data = {}
                    if err_data.get("code") == "TRIAL_SWITCH_LIMIT":
                        avail = err_data.get("availableZones") or []
                        names = [get_message(f"region_{z}") for z in avail if z]
                        if get_system_language() == 'zh':
                            if names:
                                msg = f"单机严限 8 人以保障带宽，该区试用席位已满。\n当前可秒切：【{'、'.join(names)}】，或升级会员解锁全区。"
                            else:
                                msg = "单机严限 8 人以保障带宽，各区试用席位暂满。\n请稍后再试，或升级会员解锁全区。"
                        else:
                            if names:
                                msg = f"Max 8 users/node for bandwidth — trial slots full here.\nInstant switch: [{', '.join(names)}], or upgrade to unlock all."
                            else:
                                msg = "Max 8 users/node for bandwidth — trial slots full.\nPlease try later, or upgrade to unlock all."
                        self.after(0, self._on_switch_failed, msg, True)
                        return
                    self.after(0, self._on_switch_failed, f"HTTP {response.status_code}")
                    return
                else:
                    if attempt < max_retries - 1:
                        time.sleep(3)
                        continue
                    else:
                        self.after(0, self._on_switch_failed, f"HTTP {response.status_code}")
                        return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                else:
                    self.after(0, self._on_switch_failed, str(e))
                    return

    def _poll_switch_status(self, flag_code):
        self.max_progress = 0

        for attempt in range(120):
            if not self.switching:
                return False
            try:
                response = post_api_with_failover("/getuserinfo", {"code": self.uuid}, timeouts=(7, 10))
                if response.status_code == 200:
                    data = response.json()
                    current_zone = data.get("zone", "")
                    vmname = data.get("vmname", "")

                    if current_zone and current_zone in REGION_TO_FLAG:
                        self.after(0, lambda z=current_zone: self._update_main_window_region(REGION_TO_FLAG.get(z, z), z))

                    if current_zone == self.target_flag_code and data.get("v2rayurl"):
                        self.after(0, lambda url=data.get("v2rayurl"): self._handle_poll_success(url))
                        return True

                    if not vmname and data.get("v2rayurl") and self.target_flag_code != 'us':
                        self.after(0, lambda url=data.get("v2rayurl"): self._handle_poll_success(url))
                        return True

                    vm_matches = (vmname.startswith("tt") and vmname[2:3].isdigit()) if self.target_flag_code == "jp" else vmname.startswith(f"{self.target_flag_code}tt")
                    if vmname and vm_matches:
                        try:
                            p_resp = post_api_with_failover("/createvmloading", {"vmname": vmname}, timeouts=(5, 7))
                            if p_resp.status_code == 200:
                                prog = p_resp.json().get("progress", 0)

                                if prog >= 100:
                                    self.max_progress = 100
                                    self.after(0, lambda: self._update_progress_display(get_message("switch_success")))
                                    time.sleep(3)
                                    continue

                                if prog > self.max_progress:
                                    self.max_progress = prog
                                    self.after(0, lambda p=prog: self._update_progress_display(f"{get_message('processing')}{p}%"))
                        except Exception:
                            pass

                    if attempt % 10 == 0:
                        est_prog = min(10 + attempt, 90)
                        if est_prog > self.max_progress:
                            self.max_progress = est_prog
                            self.after(0, lambda p=est_prog: self._update_progress_display(f"{get_message('processing')}{p}%"))
            except Exception:
                pass

            time.sleep(5)

        self.after(0, lambda: self._on_switch_failed("Timeout"))
        return False

    def _handle_poll_success(self, v2rayurl):
        self._update_progress_display(get_message("speed_testing"))
        links_text = v2rayurl
        try:
            sub_resp = requests.get(
                f"https://{SUB_DOMAIN}/sub/{self.uuid}?t={int(time.time())}",
                timeout=5,
                proxies={"http": None, "https": None}
            )
            if sub_resp.status_code == 200 and sub_resp.text.strip():
                links_text = sub_resp.text.strip()
        except Exception:
            pass
        parse_and_write_config_async(links_text, callback=self._on_config_ready, force_restart=True)

    def _on_config_ready(self, success):
        if success:
            self.max_progress = 100
            self._update_progress_display(get_message("switch_success"))
            self.after(1000, lambda: self._on_switch_success(self.target_flag_code))
        else:
            self._on_switch_failed("Config generation failed")

    def _update_progress_display(self, text):
        try:
            color = "black" if text == get_message("switch_success") else "red"
            self.title_label.config(text=text, fg=color)
        except Exception:
            pass

    def _wait_for_config_update(self):
        for _ in range(200):
            if not self.switching:
                return
            try:
                resp = post_api_with_failover("/getuserinfo", {"code": self.uuid}, timeouts=(7, 10))
                if resp.status_code == 200:
                    data = resp.json()
                    v2rayurl = data.get("v2rayurl", "")
                    zone = data.get("zone", "")
                    if zone:
                        self.after(0, lambda z=zone: self._update_main_window_region(REGION_TO_FLAG.get(z, z), z))
                    if v2rayurl:
                        self.after(0, lambda url=v2rayurl: self._handle_poll_success(url))
                        return
            except Exception:
                pass
            time.sleep(3)

    def _update_main_window_region(self, flag_code, zone):
        global current_region
        current_region = flag_code
        try:
            if 'region_label' in globals() and region_label:
                region_label.config(text=f"{get_message('current_region')}: {get_message(f'region_{flag_code}')}")
        except Exception:
            pass

    def _on_switch_success(self, flag_code):
        global current_region, proxy_state, btn_general_proxy, btn_close_proxy, is_manual_switching, penalized_protocol

        self.protocol("WM_DELETE_WINDOW", self.close_window)

        current_region = flag_code
        self.current_zone = flag_code
        self._update_progress_display(get_message("switch_success"))
        update_region_display()

        if hasattr(self, 'was_vpn_on') and self.was_vpn_on:
            try:
                run_mac_script("close.sh")
                time.sleep(0.5)
                run_mac_script("internet.sh")
                proxy_state = 1
                if 'btn_general_proxy' in globals() and btn_general_proxy:
                    btn_general_proxy.config(state="disabled")
                if 'btn_close_proxy' in globals() and btn_close_proxy:
                    btn_close_proxy.config(state="normal")
            except Exception:
                pass

        penalized_protocol = None
        is_manual_switching = False
        self.after(2000, self.close_window)

    def _on_switch_failed(self, error_msg, is_limit_tip=False):
        global is_manual_switching, proxy_state, btn_general_proxy, btn_close_proxy, current_node_url
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.title_label.config(text=get_message("select_region"), fg="black")
        for btn in self.flag_buttons.values():
            for child in btn.winfo_children():
                child.config(state="normal")
        self.highlight_flag(self.current_zone)
        if getattr(self, 'was_vpn_on', False):
            try:
                if is_limit_tip:
                    run_mac_script("close.sh")
                    time.sleep(0.5)
                    run_mac_script("internet.sh")
                    proxy_state = 1
                    if 'btn_general_proxy' in globals() and btn_general_proxy:
                        btn_general_proxy.config(state="disabled")
                    if 'btn_close_proxy' in globals() and btn_close_proxy:
                        btn_close_proxy.config(state="normal")
                else:
                    proxy_state = 1
                    current_node_url = None
                    if 'btn_general_proxy' in globals() and btn_general_proxy:
                        btn_general_proxy.config(state="disabled")
                    if 'btn_close_proxy' in globals() and btn_close_proxy:
                        btn_close_proxy.config(state="normal")
                    fetch_subscription(self.uuid)
            except Exception:
                pass
        self.switching = False
        is_manual_switching = False
        if is_limit_tip:
            messagebox.showinfo(get_text("app_title"), error_msg)
        else:
            messagebox.showerror("Error", f"{get_message('switch_failed')}: {error_msg}")

    def close_window(self):
        global is_manual_switching
        is_manual_switching = False
        self.grab_release()
        self.destroy()


def open_region_selector(uuid):
    RegionSelector(window, current_region, uuid)


def update_region_display():
    global region_label, current_region
    try:
        if 'region_label' in globals() and region_label:
            txt = f"{get_message('current_region')}: {get_message(f'region_{current_region}')}" if current_region else f"{get_message('current_region')}: {get_message('region_loading')}"
            region_label.config(text=txt)
    except Exception:
        pass


def toggle_autostart():
    try:
        should_enable = bool(chk_autostart.get())
        save_autostart_state(should_enable)
        launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        launch_agents_dir.mkdir(parents=True, exist_ok=True)
        plist_path = launch_agents_dir / "com.xiexievpn.launcher.plist"

        if should_enable:
            if getattr(sys, 'frozen', False):
                prog_args = f"        <string>{sys.executable}</string>\n        <string>1</string>"
            else:
                prog_args = f"        <string>{sys.executable}</string>\n        <string>{os.path.abspath(__file__)}</string>\n        <string>1</string>"

            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.xiexievpn.launcher</string>
    <key>ProgramArguments</key>
    <array>
{prog_args}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
            with open(plist_path, "w", encoding="utf-8") as f:
                f.write(plist_content)
        else:
            if plist_path.exists():
                try:
                    plist_path.unlink()
                except Exception:
                    pass
    except Exception as e:
        messagebox.showerror("Error", f"{get_message('failed_autostart')}: {e}")


def on_chk_change(*args):
    toggle_autostart()


def run_login_network_repair():
    script_path = resource_path("repair_on_login.sh")
    if not os.path.exists(script_path):
        return True, ""
    try:
        os.chmod(script_path, 0o755)
        result = subprocess.run(
            ["/bin/bash", script_path],
            capture_output=True,
            timeout=30,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        if result.returncode == 0:
            return True, ""
        detail = (result.stderr or result.stdout or "").strip()
        return False, detail or f"exit code {result.returncode}"
    except Exception as e:
        return False, str(e)


def set_general_proxy(show_success_msg=True):
    global proxy_state, config_ready
    if not config_ready and not os.path.exists(get_persistent_path("config.json")):
        messagebox.showinfo(get_text("app_title"), get_message("config_preparing"))
        return
    try:
        run_mac_script("close.sh")
        time.sleep(0.5)
        res = run_mac_script("internet.sh")
        if res.returncode != 0:
            raise RuntimeError((res.stderr or res.stdout or "sing-box startup failed").strip())

        if show_success_msg:
            messagebox.showinfo("Information", get_message("vpn_setup_success"))
        btn_general_proxy.config(state="disabled")
        btn_close_proxy.config(state="normal")
        proxy_state = 1
        toggle_autostart()
    except Exception as e:
        messagebox.showerror("Error", f"{get_message('failed_proxy')}: {e}")


def close_proxy():
    global proxy_state
    try:
        run_mac_script("close.sh")
        messagebox.showinfo("Information", get_message("vpn_closed"))
        btn_close_proxy.config(state="disabled")
        btn_general_proxy.config(state="normal")
        proxy_state = 0
        toggle_autostart()
    except Exception as e:
        messagebox.showerror("Error", f"{get_message('failed_close')}: {e}")


def on_closing():
    if 'btn_close_proxy' in globals() and btn_close_proxy["state"] == "normal":
        try:
            run_mac_script("close.sh")
            messagebox.showinfo("Information", get_message("vpn_temp_closed"))
        except Exception:
            pass
    release_single_instance_lock()
    window.destroy()


def check_proxy_connectivity():
    proxies = {'http': 'http://127.0.0.1:1080', 'https': 'http://127.0.0.1:1080'}
    try:
        if requests.get("http://cp.cloudflare.com/generate_204", proxies=proxies, timeout=5).status_code == 204:
            return True
        return False
    except Exception:
        return False


def connection_watchdog_thread(uuid):
    global proxy_state, window, is_manual_switching, current_protocol
    global penalized_protocol, penalty_until

    while True:
        time.sleep(10)

        if is_manual_switching:
            continue

        if proxy_state == 1:
            if not check_proxy_connectivity():
                time.sleep(1.5)
                if not check_proxy_connectivity():
                    fetch_subscription(uuid, from_watchdog=True)
                    time.sleep(15)


def show_main_window(uuid):
    global window, btn_general_proxy, btn_close_proxy, chk_autostart, current_uuid, region_label, protocol_label, login_repair_done
    current_uuid = uuid
    window = tk.Tk()
    window.title(get_text("app_title"))
    window.geometry("300x360")
    try:
        window.iconbitmap(resource_path("favicon.icns"))
    except Exception:
        pass
    window.protocol("WM_DELETE_WINDOW", on_closing)

    btn_general_proxy = tk.Button(window, text=get_text("open_vpn"), command=lambda: set_general_proxy(show_success_msg=True))
    btn_close_proxy = tk.Button(window, text=get_text("close_vpn"), command=close_proxy)

    if not config_ready and not os.path.exists(get_persistent_path("config.json")):
        btn_general_proxy.config(state="disabled")

    btn_close_proxy.config(state="disabled")

    btn_general_proxy.pack(pady=10)
    btn_close_proxy.pack(pady=10)

    chk_autostart = tk.BooleanVar()
    chk_autostart.set(load_autostart_state())
    chk_autostart.trace_add("write", on_chk_change)
    tk.Checkbutton(window, text=get_text("autostart"), variable=chk_autostart, command=toggle_autostart).pack(pady=5)

    tk.Button(window, text=get_text("switch_region"), command=lambda: open_region_selector(uuid)).pack(pady=5)
    region_label = tk.Label(window, text="", font=("PingFang SC", 9), fg="gray")
    region_label.pack(pady=2)

    protocol_label = tk.Label(window, text=f"{get_text('protocol_label')}: {get_text('protocol_auto')}", font=("PingFang SC", 9, "bold"), fg="gray")
    protocol_label.pack(pady=2)

    if not login_repair_done:
        btn_general_proxy.config(state="disabled")
        btn_close_proxy.config(state="disabled")
        protocol_label.config(text=get_message("repairing_network"), fg="orange")
        window.update_idletasks()

        repair_ok, repair_detail = run_login_network_repair()
        login_repair_done = True

        if not repair_ok:
            detail = f"\n{repair_detail}" if repair_detail else ""
            messagebox.showwarning(get_text("app_title"), f"{get_message('repair_failed')}{detail}")

        if os.path.exists(get_persistent_path("config.json")):
            btn_general_proxy.config(state="normal")
        protocol_label.config(text=f"{get_text('protocol_label')}: {get_text('protocol_auto')}", fg="gray")

    fetch_subscription(uuid)
    window.after(1000, update_region_display)

    def check_update_async():
        def update_check():
            update_info = check_for_updates()
            if update_info:
                window.after(0, lambda: show_update_dialog(update_info))
        threading.Thread(target=update_check, daemon=True).start()

    window.after(3000, check_update_async)

    monitor_thread = threading.Thread(target=connection_watchdog_thread, args=(uuid,), daemon=True)
    monitor_thread.start()

    if len(sys.argv) > 1:
        try:
            if int(sys.argv[1]) == 1:
                global pending_autostart
                if config_ready:
                    set_general_proxy(show_success_msg=False)
                else:
                    pending_autostart = True
        except Exception:
            pass

    window.deiconify()
    window.attributes('-topmost', True)
    window.attributes('-topmost', False)
    window.mainloop()


def on_remember_changed(*args):
    if not chk_remember.get():
        remove_uuid_file()


def check_login():
    entered_uuid = entry_uuid.get().strip()
    try:
        response = post_api_with_failover("/login", {"code": entered_uuid}, timeouts=(6, 8))
        if response.status_code == 200:
            if chk_remember.get():
                save_uuid(entered_uuid)
            login_window.destroy()
            show_main_window(entered_uuid)
        else:
            if response.status_code in (400, 401, 404):
                remove_uuid_file()
            msg = (
                get_message("invalid_code")
                if response.status_code in (400, 401, 404)
                else get_message("expired")
                if response.status_code == 403
                else get_message("server_error")
            )
            messagebox.showerror("Error", msg)
    except Exception as e:
        messagebox.showerror("Error", f"{get_message('connection_error')}: {e}")


def do_paste_entry():
    txt = None
    try:
        res = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout:
            txt = res.stdout
    except Exception:
        pass
    if not txt:
        try:
            txt = login_window.clipboard_get()
        except Exception:
            txt = ""
    if txt:
        try:
            if entry_uuid.selection_present():
                entry_uuid.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except Exception:
            pass
        entry_uuid.insert(tk.INSERT, txt.strip())


def do_copy_entry():
    try:
        if entry_uuid.selection_present():
            sel = entry_uuid.selection_get()
            try:
                subprocess.run(["pbcopy"], input=sel, text=True, timeout=2)
            except Exception:
                pass
            login_window.clipboard_clear()
            login_window.clipboard_append(sel)
    except Exception:
        pass


if __name__ == "__main__":
    login_window = tk.Tk()
    login_window.title(get_text("login_title"))
    login_window.geometry("300x200")
    try:
        login_window.iconbitmap(resource_path("favicon.icns"))
    except Exception:
        pass

    if not acquire_single_instance_lock():
        login_window.withdraw()
        messagebox.showwarning(get_text("login_title"), get_message("already_running"))
        sys.exit(0)

    tk.Label(login_window, text=get_text("login_prompt")).pack(pady=10)
    entry_uuid = tk.Entry(login_window)
    entry_uuid.pack(pady=5)

    for mod in ("Command", "Control"):
        entry_uuid.bind(f"<{mod}-Key-a>", lambda event: [entry_uuid.select_range(0, tk.END), "break"][1])
        entry_uuid.bind(f"<{mod}-Key-A>", lambda event: [entry_uuid.select_range(0, tk.END), "break"][1])
        entry_uuid.bind(f"<{mod}-Key-c>", lambda event: [do_copy_entry(), "break"][1])
        entry_uuid.bind(f"<{mod}-Key-C>", lambda event: [do_copy_entry(), "break"][1])
        entry_uuid.bind(f"<{mod}-Key-v>", lambda event: [do_paste_entry(), "break"][1])
        entry_uuid.bind(f"<{mod}-Key-V>", lambda event: [do_paste_entry(), "break"][1])

    menu = Menu(entry_uuid, tearoff=0)
    menu.add_command(label=get_text("copy"), command=do_copy_entry)
    menu.add_command(label=get_text("paste"), command=do_paste_entry)
    menu.add_command(label=get_text("select_all"), command=lambda: entry_uuid.select_range(0, tk.END))
    entry_uuid.bind("<Button-2>", lambda event: menu.post(event.x_root, event.y_root))
    entry_uuid.bind("<Button-3>", lambda event: menu.post(event.x_root, event.y_root))
    entry_uuid.bind("<Control-Button-1>", lambda event: menu.post(event.x_root, event.y_root))

    chk_remember = tk.BooleanVar()
    tk.Checkbutton(login_window, text=get_text("auto_login"), variable=chk_remember).pack(pady=5)
    chk_remember.trace_add("write", on_remember_changed)
    tk.Button(login_window, text=get_text("login_button"), command=check_login).pack(pady=10)

    if saved_uuid := load_uuid():
        chk_remember.set(True)
        entry_uuid.insert(0, saved_uuid)
        check_login()

    login_window.mainloop()
