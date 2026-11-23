# 谢谢网络加速器 (XieXie VPN macOS Client)

## 本地打包命令
```bash
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "谢谢网络加速器" \
  --icon "favicon.icns" \
  --add-data "favicon.icns:." \
  --add-data "favicon.ico:." \
  --add-data "internet.sh:." \
  --add-data "close.sh:." \
  --add-data "repair_on_login.sh:." \
  --add-data "sing-box:." \
  --add-data "geoip-cn.srs:." \
  --add-data "geosite-cn.srs:." \
  --add-data "languages.json:." \
  --add-data "flags:flags" \
  main_macos.py
```
