# EdwardAI Threads 實作助手

一問一步，使用你自己的 Meta App、Threads 帳號及憑證，從設定走到單篇與多篇串文發布及讀回。

## Claude Code plugin

先加入集合：

```text
/plugin marketplace add edwardaitechhk-lang/edwardai-plugins
/plugin install threads-api@edwardai
```

重開對話後使用 `/threads-api:edwardai-threads`。若集合已安裝，先執行 `/plugin marketplace update edwardai`。

## Codex／手動下載

- [下載 skill ZIP](../../downloads/threads-api/edwardai-threads.zip?raw=true)
- [下載圖解 PDF](../../downloads/threads-api/guide.pdf?raw=true)
- [完整圖解及 AI 安裝入口](https://edwardai-packs.edwardai-tech-hk.workers.dev/threads-api/)

ZIP 解壓後包含 `install.py`；執行 `python3 install.py --target codex` 或 `--target claude`。需 Python 3.9+，已有同名 skill 會先備份；不包含任何 token。

v1.1.0：已在老師自己的帳號完成 API 身份、單篇發布，以及三則回覆串的全部正文與回覆關係讀回。17 頁 PDF 的第 14、15 頁新增整組預覽、串接與中斷續做。發布及防重送有 7 項隔離測試；學生須自己逐關驗收，Windows 真機、圖片及排程未驗收。不要把安裝成功當成帳號已連線或已授權發布。

多篇串文使用 `preview-thread thread.json` 及 `publish-thread thread.json --approve-hash <整組sha256>`。JSON 格式為 `{"posts":["主文全文","第二則全文","第三則全文"]}`。每一則接續回覆上一則，不是引用貼文；逐則保存 Post ID，結果不明不重送。

已用 ZIP 安裝舊版的使用者，可下載同一網址的新版 ZIP，再執行安裝器；已有 skill 會先備份。帳號憑證另存，安裝器不會接觸憑證。

本版由 EdwardAI 重新編寫，方向參考 [madebypan/threads-api-skill](https://github.com/madebypan/threads-api-skill)，並以 [Meta 官方 API 範例](https://www.postman.com/meta/threads/collection/dht3nzz/threads-api) 核對。
