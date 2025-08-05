谢谢网络加速器 – https://cn.xiexievpn.com


在 macOS 下使用的客户端。

## 打包方法

可以使用 [PyInstaller](https://pyinstaller.org/) 在 macOS 上将 `main_macos.py` 打包成可执行的 `.app` 文件：

```bash
pip install pyinstaller
pyinstaller \
  --windowed \
  --name "谢谢网络加速器" \
  --icon "favicon.icns" \
  --add-data "internet.sh:." \
  --add-data "close.sh:." \
  --add-data "favicon.icns:." \
  --add-data "geosite.dat:." \
  --add-data "geoip.dat:." \
  --add-data "xray:." \
  main_macos.py
```

打包完成后，在 `dist/XieXieVPN` 目录下会生成 `谢谢网络加速器.app`。
