---
name: edwardai-threads
description: 逐步連接使用者自己的 Threads API、核對身份、預覽與發布純文字貼文，並保存收據防止重複發布。適用於 Threads 新手設定、第一篇試發及自己的舊文索引。
---

# EdwardAI Threads 實作助手

先讀本包的 [圖解教學](https://edwardai-packs.edwardai-tech-hk.workers.dev/threads-api/)。本 skill 由 EdwardAI 的實際帳號設定流程整理，參考 madebypan/threads-api-skill 的工具方向，重新編寫；沒有捆綁老師的帳號、token 或第三方發文腳本。

## 從已完成的位置接續

先核對使用者目前畫面及已完成證據，再列出：登入 → 開發者帳戶 → Threads 連線 → 預覽 → 單次發布及讀回 → 舊文整理／排程。新手每次只交一個具體動作。畫面不同時讀畫面，不猜按鈕或要求重做整套。

設定 App 時選「存取 Threads API」。基本讀取是 threads_basic，發布需要 threads_content_publish。不要因為可見就加入刪文、全站搜尋等額外權限。自己的測試流程與提供他人使用的公開服務、商家驗證及應用程式審查分開處理。

使用者可以沿用自己的商家組合，也可以依 live UI 選擇稍後連結；不要代選他人的商家。應用程式一般編號與 Threads 應用程式編號可能不同，依 Threads 設定頁識別。

## 連線的三個重要細節

- 角色選「Threads 測試人員」，不是一般「測試人員」。若清單空白，檢查是否套用了「開發人員」篩選。
- 「審理中」的測試邀請，在正確 Threads 帳號的「設定 → 網站權限 → 邀請」接受。已有邀請就接續接受，不重新新增。
- 在「使用案例 → 設定 → 用戶憑證產生器」為自己的已接受測試帳號產生 token。授權時確認帳號與範圍，由使用者閱讀條款及決定授權。不要要求把 token、密碼或 App Secret 貼到聊天或教材。

## 本包工具

Python 3.9+，無第三方套件。入口 `scripts/threads.py`，所有操作先看 `--help`。

1. `python3 scripts/threads.py init`：在本機互動輸入用戶名稱與 token；私有設定存在使用者自己的家目錄。輸入不回顯。
2. `python3 scripts/threads.py me`：只讀查詢；返回的 username 必須等於設定中的使用者。
3. 將最終文字寫入 UTF-8 檔，再執行 `python3 scripts/threads.py preview post.txt`。只輸出預覽和 sha256，不建立貼文容器。
4. 先展示帳號、全文、圖片／回覆順序（本工具只支援單篇純文字）、發布時間。取得這個版本的明確發布批准，才執行 `python3 scripts/threads.py publish post.txt --approve-hash <預覽的sha256>`。
5. 完成須有真實 post ID、permalink、帳號與全文讀回。工具保存私有收據；同一帳號同一內容的再次執行只讀回，不再次發布。

工具內的 hash 檢查不是使用者批准的替代品。不要在沒有批准時自己計算 hash 然後發布。

## 失敗及中斷

發布前保存 intent；每次外部寫入前保存階段。timeout、失聯或結果不明都不盲目重送。工具會保留鎖定收據；先用 `receipt <hash>` 及 `me` / `list --pages 1` 查現況。已有 post ID 時可用 `verify <post-id>` 讀回。若失敗發生在建立容器後，先查容器 `status <container-id>`；沒有足夠證據就保留不確定狀態，不能刪收據重新跑。

## 舊文與排程

使用 `list --pages N` 讀自己的舊文，交代頁數與有沒有後續頁，再在已讀範圍內找指定主題。產生導讀主文＋每篇舊文簡介與原文連結的預覽。不要把全站 keyword search 當成自己的舊文搜尋。本版工具不直接發布多篇回覆串。

單次發布讀回後才設定排程。先查現有執行器，確認日期、時區、執行機器及核准內容，保存 job ID、下一次執行與停用方式。真的部署、dry-run 及定時驗收後才說已完成；本包沒有預設排程或自動生成發文權。

## 參考

- https://developers.facebook.com/docs/threads/
- https://www.postman.com/meta/threads/collection/dht3nzz/threads-api
- https://github.com/madebypan/threads-api-skill
