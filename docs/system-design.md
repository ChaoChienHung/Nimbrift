# Nimbrift 系統設計

## 目標與範圍

第一版提供安全、可預期的 SSH 檔案與資料夾傳輸，讓 CLI、GUI 的行為一致。單次執行處理一項傳輸工作。未包含排程、雙向同步、雲端儲存或分散式佇列。

## 架構

```text
CLI (argparse) ─┐
                ├─> TransferService ─> Transport protocol ─> SFTPTransport ─> SSH server
GUI (Tkinter) ──┘          │
                          └─> Progress / cancellation / errors
```

`model.py` 定義不可變的連線設定、傳輸請求與進度事件。`service.py` 是應用層入口，透過可注入的 transport factory 執行工作。`sftp.py` 負責 SSH 認證、遠端檔案操作及暫存檔處理。`cli.py` 和 `gui.py` 只負責輸入與呈現，不複製傳輸邏輯。GUI 的網路工作在背景執行緒執行，使用 queue 將進度交回主執行緒更新視窗。

## 主要流程

1. 介面建立並驗證 `Connection` 與 `Transfer`。
2. `TransferService` 建立 transport，開啟 SSH/SFTP 連線。
3. transport 遞迴走訪來源，逐檔傳輸；每個進度 callback 檢查取消旗標。
4. 檔案先寫入目標旁的暫存檔，傳輸完成後才改名為正式檔案。失敗時清除暫存檔。
5. 關閉 SFTP/SSH，回報完成、取消或失敗。

## 安全與失敗語義

- 採用已知主機驗證；未知或變更的主機金鑰會使連線失敗。
- 不在程式碼、設定檔或命令列參數中儲存密碼。CLI 的密碼由提示讀入；GUI 密碼只保留在目前視窗記憶體。
- 遞迴傳輸拒絕符號連結與不安全的遠端檔名，避免意外跨越目錄邊界。
- 預設拒絕覆寫。單一檔案使用暫存檔降低中斷造成的半成品風險。資料夾傳輸不是整體交易；部分檔案成功後若失敗，不會回滾已完成檔案。
- GUI 的取消是合作式取消，正在進行的檔案會在下一次進度 callback 停止。

## 擴充方向

`Transport` protocol 是替換傳輸方式的邊界；可新增 SCP 或其他 adapter，而不更動 UI。若加入同步，應新增獨立的「比較與計畫」層，先產生傳輸清單，再由 service 執行。若加入佇列或並行工作，應在 service 上方建立 job manager，控制併發數、重試與持久化；不要讓 GUI 或 transport 自行管理全域工作狀態。連線設定檔可另設 repository 層，但敏感資訊應交給系統金鑰圈，且仍需維持主機金鑰驗證。

## 已知限制

目前每次傳輸建立一條連線，不支援續傳與跨檔案總進度。覆寫遠端檔案優先使用 SFTP `posix_rename` 擴充；不支援的伺服器改用備份後改名，這段時間目標檔案可能短暫不存在。這些限制可在後續版本透過 transport capability 檢測與 job manifest 改進。
