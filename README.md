在 macOS 下使用的客户端。

## 打包方法

可以使用 [PyInstaller](https://pyinstaller.org/) 在 macOS 上将 `main_macos.py` 打包成可执行的 `.app` 文件：

```bash
pip install pyinstaller
pyinstaller \
  --windowed \
  --name XieXieVPN \
  --add-data "internet.sh:." \
  --add-data "close.sh:." \
  main_macos.py
```

打包完成后，在 `dist/XieXieVPN` 目录下会生成 `XieXieVPN.app`。
