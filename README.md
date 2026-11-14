# Nimbrift

Nimbrift 是一個透過 SSH 傳輸檔案的 Python 工具，提供命令列（CLI）與桌面視窗（GUI）。兩種介面共用同一套 SFTP 傳輸核心，適合手動搬移檔案，也可從 shell 腳本呼叫 CLI。

## 目前狀態

目前版本是 **0.1.0**，已提供：

- 上傳及下載單一檔案或整個資料夾。
- 單一檔案進度、取消傳輸與明確的錯誤訊息。
- SSH agent、預設 SSH 金鑰、指定私鑰或執行時輸入密碼。
- 已知主機金鑰驗證；未知主機不會被自動信任。
- 預設拒絕覆寫；傳輸時先寫暫存檔，完成後再改名。

目前尚未提供遠端目錄瀏覽、斷點續傳、重試、資料夾同步或多工作佇列，規劃見 [TODO.md](TODO.md)。核心傳輸邏輯已有自動化測試；目前尚未在實際 SSH 伺服器上完成端到端驗證。

## 安裝

需要 **Python 3.10+**。CLI 依賴 Paramiko；GUI 另外需要 Python 的 Tkinter 支援。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Windows 的虛擬環境啟用指令是 `.venv\Scripts\activate`。如果執行 GUI 時顯示 Tkinter 不可用，請改用附帶 Tkinter 的 Python 安裝版本建立虛擬環境。安裝後可執行 `nimbrift --help` 確認 CLI 入口。

## 連線準備

先確認 SSH 帳號可登入，並核對伺服器的主機金鑰。主機金鑰需要記錄在 `~/.ssh/known_hosts`，或透過 `--known-hosts`／GUI 的 **Known hosts** 欄位指定。Nimbrift 不會自動接受未知或已變更的主機金鑰。

```bash
ssh me@example.com
```

預設會嘗試 SSH agent 與標準 SSH 金鑰；也可以指定私鑰，或在執行時輸入密碼。密碼不會寫入設定檔。

## 使用 CLI

指令格式：

```text
nimbrift upload   <本地來源> <遠端目標> --host <主機> --user <帳號> [選項]
nimbrift download <遠端來源> <本地目標> --host <主機> --user <帳號> [選項]
```

範例：

```bash
# 上傳單一檔案
nimbrift upload ./report.csv /home/me/report.csv --host example.com --user me

# 下載資料夾，使用指定私鑰
nimbrift download /home/me/results ./results --host example.com --user me --key-file ~/.ssh/id_ed25519

# 上傳資料夾並允許覆寫既有檔案
nimbrift upload ./photos /home/me/photos --host example.com --user me --overwrite

# 使用密碼登入；密碼會在終端機中提示輸入
nimbrift upload ./report.csv /home/me/report.csv --host example.com --user me --ask-password
```

常用選項：

| 選項 | 用途 |
| --- | --- |
| `--host`、`--user` | 必填的 SSH 主機與帳號 |
| `--port` | SSH 連接埠，預設 `22` |
| `--key-file` | 指定私鑰路徑 |
| `--known-hosts` | 指定額外的主機金鑰檔案 |
| `--ask-password` | 在執行時提示輸入密碼 |
| `--overwrite` | 允許取代既有檔案 |

更多參數可用 `nimbrift upload --help` 或 `nimbrift download --help` 查看。

## 使用 GUI

執行 `nimbrift gui` 或 `nimbrift-gui` 開啟視窗：

1. 選擇 **upload** 或 **download**，填入 **Host**、**Username**，必要時修改 **Port**。
2. 如需指定私鑰或主機金鑰檔案，填入 **Private key** 或 **Known hosts**；使用密碼登入時填入 **Password**。
3. 填入 **Source** 與 **Destination**。上傳時 Source 是本地路徑、Destination 是遠端路徑；下載時則相反。上傳可用 **Browse** 選檔，或用 **Upload folder** 選資料夾；下載可用 **Browse** 選本地目標資料夾。遠端路徑目前需手動輸入。
4. 如需取代既有檔案，勾選 **Overwrite existing files**，然後按 **Start transfer**。視窗會顯示目前檔案的進度；按 **Cancel** 可停止傳輸。

## 傳輸行為與限制

資料夾傳輸會遞迴處理內容，目標路徑視為該資料夾的位置。傳輸單一檔案到既有目錄時，會沿用來源檔名。符號連結不會跟隨。若取消或發生錯誤，未完成檔案的暫存檔會清除；已傳完的其他檔案不會回滾。GUI 的進度條顯示目前檔案，尚未計算整批檔案的總進度。

## 開發與設計

```bash
python -m unittest discover -s tests -v
python -m compileall -q nimbrift
```

CLI 與 GUI 共用 `TransferService`，由 SFTP adapter 執行傳輸。模組邊界、資料流及擴充方向見 [系統設計文件](docs/system-design.md)。
