# Nimbrift 技術說明

本文描述目前程式碼實際使用的套件、語言機制、建置工具與測試邊界。版本範圍以 `pyproject.toml` 為準，CI 的 Python 版本與 runner 以 `.github/workflows/desktop.yml` 為準。

## 直接依賴

| 套件／工具 | 使用位置 | 技術與用途 |
| --- | --- | --- |
| Python 3.10+ | 全專案 | 型別註記、`dataclass`、context manager、路徑與執行緒標準函式庫 |
| [Paramiko](https://docs.paramiko.org/en/stable/api/client.html) | `nimbrift/sftp.py` | SSH 用戶端與認證、已知主機驗證、SFTP 檔案操作；底層依賴加密函式庫處理 SSH 協定 |
| [PySide6 Essentials](https://doc.qt.io/qtforpython-6/package_details.html) | `nimbrift/gui.py` | Qt for Python 的核心、圖形與 Widgets 模組；建立桌面表單、圖示、執行緒、Signal/Slot 與事件迴圈 |
| [PyInstaller](https://pyinstaller.org/en/stable/usage.html) | `scripts/build_app.py` | 建置時將 Python 程式、直譯器、依賴與 Qt 插件凍結成可雙擊的 macOS `.app` |
| setuptools | `pyproject.toml` | PEP 517 建置後端，定義安裝套件與 `nimbrift`、`nimbrift-gui` 命令入口 |
| GitHub Actions | `.github/workflows/desktop.yml` | push、PR 或手動觸發的測試與 macOS 建置工作流程，保留 zip artifact |

`PySide6-Essentials` 只安裝這個 GUI 所需的 Qt 基礎模組；完整 `PySide6` 套件還會帶入 Addons 等額外模組。PySide6 會透過 `shiboken6` 提供 Python 與 Qt C++ 的綁定。Paramiko 的加密、金鑰與相關功能所需的間接套件由 pip 依其套件宣告解析；本專案不直接呼叫那些套件的 API。

## 標準函式庫與程式機制

- `argparse` 定義 CLI 的 `upload`、`download`、`gui` 子命令；`getpass` 在終端機讀取密碼，避免把密碼放在命令列參數。
- `dataclasses.dataclass(frozen=True)` 表達不可變的連線與傳輸請求；`Enum` 限定傳輸方向；`typing.Protocol` 定義 transport 能力。
- `pathlib.Path` 處理本地檔案路徑，`posixpath` 處理遠端 Unix 路徑，避免混淆兩種路徑語意。
- `threading.Event` 提供跨執行緒取消旗標；Qt 的 `QThread` 承接阻塞網路工作，`Signal` 與 `Slot` 將結果送回 GUI 主執行緒。[Qt 的執行緒文件](https://doc.qt.io/qtforpython-6/overviews/qtdoc-threads-qobject.html) 說明了跨執行緒訊號的排隊傳遞。
- `stat` 判斷一般檔案、資料夾與符號連結；`uuid` 產生暫存檔名稱；`os.replace` 在本地完成單檔替換。
- `unittest`、`unittest.mock` 與 `tempfile` 驗證核心、CLI 與 GUI 的邊界，不需要在測試中連線到真實 SSH 主機。

## 套件邊界

- `nimbrift/model.py`：`Connection`、`Transfer`、`Progress` 與公開錯誤類型。
- `nimbrift/service.py`：`TransferService` 與可注入的 `Transport` protocol。UI 呼叫此層，不直接操作 Paramiko。
- `nimbrift/sftp.py`：唯一直接使用 Paramiko 的 adapter。SSH/SFTP 的建立、檔案走訪、暫存檔和覆寫策略集中於此。
- `nimbrift/cli.py`：命令列參數、終端機進度與結束碼。
- `nimbrift/gui.py`：Qt Widgets 視窗、表單、背景工作與狀態呈現；樣式用 Qt Style Sheet 設定。
- `main.py`、`gui_main.py`、`nimbrift/__main__.py`：薄入口。GUI app 使用 `gui_main.py`，開啟時直接進 GUI，不經過 CLI 畫面。

這些邊界遵守關注點分離、單一職責與依賴反轉：共用用例在 service，協定細節在 adapter，介面只處理人機互動。進度與取消使用 callback／事件傳遞，不讓核心依賴 Qt。

## 測試與建置流程

```text
push / pull request / 手動觸發
             │
             ▼
Ubuntu: 安裝 .[gui] → 執行 tests/ 中的 unittest
             │ 全數通過
             ▼
macOS arm64: 安裝 .[build] → 繪製 .icns → PyInstaller .app
             │
             ▼
檢查 app 可執行檔與 Info.plist → 啟動 smoke test → zip → Actions artifact
```

本地 `python scripts/build_app.py` 也先跑同一組測試；`--skip-tests` 只供已完成獨立測試 job 的 CI 建置使用。PyInstaller 在 macOS 使用 `--onedir --windowed`，讓 bundle 內含依賴且啟動時沒有終端機視窗。[PyInstaller 文件](https://pyinstaller.org/en/stable/usage.html) 不建議 macOS `.app` 使用 `--onefile --windowed` 組合。`scripts/make_icon.py` 以 Qt 畫出多尺寸圖示，再由 macOS `iconutil` 組成 `.icns`。

目前工作流程只建置 **Apple silicon (arm64) macOS** 版本。GitHub artifact 是測試後的建置成果，不等於已做 Apple Developer ID 簽署、公證或自動發布 Release。由於沒有可供 CI 使用的 SSH 測試伺服器，測試使用假 SFTP／transport；真實主機認證、主機金鑰與網路中斷行為仍需端到端測試。
