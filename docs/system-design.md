# Nimbrift 系統設計

## 目標與範圍

Nimbrift 目前是單機桌面／CLI 檔案傳輸工具。一次處理一項傳輸工作，使用 SSH 的 SFTP 子系統上傳或下載檔案與資料夾。設計目標是讓兩種介面行為一致、傳輸失敗有可預期的結果，並保留擴充其他傳輸 adapter、同步計畫與工作佇列的邊界。尚未提供排程、續傳或分散式執行。

## 架構與依賴方向

```text
CLI (argparse) ───┐
                  ├─> TransferService ─> Transport protocol ─> SFTPTransport ─> SSH server
GUI (PySide6) ────┘          │
                            └─> Progress / cancellation / errors

GitHub Actions (macOS): tests ──pass──> build ──> Nimbrift.app artifact
```

`model.py` 定義不可變的 `Connection`、`Transfer` 與 `Progress` 資料。`service.py` 是介面共同呼叫的應用層入口，透過可注入的 transport factory 建立實作。`sftp.py` 是基礎設施 adapter，負責 SSH 認證、遠端路徑、逐檔傳輸與暫存檔。`cli.py` 與 `gui.py` 僅負責輸入、驗證後建立請求，以及回報結果。`main.py`、`gui_main.py` 和 `__main__.py` 是薄入口，不包含傳輸邏輯。

### 主要設計原則

| 原則 | 在程式中的做法 | 效益 |
| --- | --- | --- |
| 關注點分離與單一職責 | UI、應用服務、SFTP adapter 各自處理不同工作 | 修改 GUI 不必重寫傳輸協定 |
| 依賴反轉 | `TransferService` 只要求 `Transport` protocol，工廠可注入 | 測試可用假 transport，未來可新增 adapter |
| 單一真實來源 | CLI 與 GUI 都呼叫同一個 service | 避免兩套傳輸規則逐漸分歧 |
| 明確狀態與資料 | `dataclass(frozen=True)` 表達請求，`Direction` enum 限制方向 | 邊界資料容易驗證與測試 |
| 安全預設 | `RejectPolicy`、預設不覆寫、不跟隨符號連結 | 減少意外信任主機或改寫資料 |
| 資源生命週期 | transport context manager 關閉 SSH/SFTP；GUI 等工作執行緒結束後再收尾 | 連線與視窗狀態可預期 |
| 漸進式擴充 | 傳輸 adapter 與未來的同步／佇列層分開 | 避免把未來功能堆進 UI 或協定層 |

## 傳輸資料流

1. CLI 或 GUI 收集連線與路徑，建立 `Connection` 和 `Transfer`。
2. `TransferService.run()` 建立 transport，開啟 SSH 與 SFTP。
3. adapter 檢查來源類型，遞迴走訪目錄並逐檔處理；進度 callback 回傳目前檔案位元組數。
4. 目標旁先建立 `.part` 暫存檔；確認傳輸完成後改名。若取消或失敗，清除該暫存檔。
5. context manager 關閉連線；介面顯示成功、取消或錯誤。

下載檔案透過本地 `os.replace` 完成替換。上傳覆寫優先用 SFTP `posix_rename`；伺服器不支援時先將舊檔改名為備份，再將新檔改名。資料夾整體不是交易：前面已完成的檔案不會因後續失敗而回滾。

## GUI 執行緒模型

Qt 主執行緒只建立與更新視窗。`TransferWorker(QThread)` 執行阻塞的 SFTP 工作，透過 Qt Signal 將進度、成功、取消與錯誤送回 `MainWindow` 的 Slot。視窗只在工作執行緒結束後恢復開始按鈕；關閉視窗時先發送取消旗標，避免執行緒仍在工作時銷毀 UI。取消使用 `threading.Event`，在每次進度 callback 和每個檔案間檢查，屬於合作式取消。

## 安全與邊界

- 透過 Paramiko 載入已知主機，使用 `RejectPolicy` 拒絕未知主機金鑰。
- SSH agent、標準金鑰、指定私鑰或執行時密碼由 Paramiko 認證流程處理；專案不儲存密碼。
- 上傳的本地來源與下載的遠端來源拒絕符號連結；遠端目錄項目檢查 `.`、`..` 和路徑分隔符。
- 預設拒絕覆寫。暫存檔與逐檔改名降低不完整檔案暴露，但資料夾不是原子操作。
- GUI 進度只描述目前檔案；不同檔案的大小沒有先被掃描成總進度。

## 擴充路徑

若加入同步，先在 service 上方建立 **計畫層**：比較兩端目錄，產生可預覽的傳輸清單，再交給現有 service 執行。若加入重試與續傳，需要定義錯誤類型、部分檔案狀態與 job manifest。若加入多工作佇列，新增 job manager 控制併發、取消與持久化；不要在 GUI 或 SFTP adapter 中維護全域工作狀態。新增傳輸方式時實作 `Transport` protocol，並透過工廠切換。

## 建置與發布邊界

`tests/` 在 GitHub Actions 的 macOS job 先執行；只有測試步驟成功才會進入打包步驟。PyInstaller 把 Python 執行環境與依賴凍結為 macOS `.app`，zip 由 Actions artifact 提供下載。artifact 並非已簽署／公證的正式發行版。完整套件與工具資訊見 [技術說明](technical-stack.md)。
