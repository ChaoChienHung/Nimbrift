# Nimbrift

Nimbrift 是一個 SSH 檔案傳輸工具，提供命令列與桌面視窗。兩個介面共用同一套傳輸核心，目前支援 SFTP 上傳、下載檔案及資料夾。

## 安裝

需要 Python 3.10 或更新版本。GUI 另外需要 Python 的 Tkinter 支援。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

macOS 如果目前的 Python 缺少 Tkinter，請使用附帶 Tkinter 的 Python 安裝版本建立虛擬環境。CLI 不需要 Tkinter。

## 使用

SSH 主機必須先存在於 `~/.ssh/known_hosts`，或用 `--known-hosts` 指定已驗證的檔案。第一次連線時，請先用 `ssh user@host` 核對並加入主機金鑰。Nimbrift 不會自動接受未知主機。

```bash
nimbrift upload ./report.csv /home/me/report.csv --host example.com --user me
nimbrift download /home/me/results ./results --host example.com --user me --key-file ~/.ssh/id_ed25519
nimbrift upload ./photos /home/me/photos --host example.com --user me --overwrite
nimbrift gui
```

也可使用 `nimbrift-gui` 開啟視窗。預設使用 SSH agent 和標準 SSH 金鑰；密碼登入可在 CLI 加 `--ask-password`，或在 GUI 的 Password 欄位輸入。密碼不會儲存。舊的 `uploadSCP.py` 與 `downloadSCP.py` 仍可當作命令列入口，但需要傳入相同參數。

當來源是資料夾時，目標路徑就是要建立或更新的資料夾；當來源是檔案而目標是既有資料夾時，會保留來源檔名。預設拒絕覆寫既有檔案，指定 `--overwrite` 才會取代。符號連結不會跟隨。傳輸中斷時，暫存檔會清除；已完成的其他檔案會保留。進度以單一檔案為單位顯示。

## 開發

```bash
python -m unittest discover -s tests -v
python -m compileall -q nimbrift
```

架構與擴充方式見 [docs/system-design.md](docs/system-design.md)，後續工作見 [TODO.md](TODO.md)。
