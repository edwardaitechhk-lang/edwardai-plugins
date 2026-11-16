# EdwardAI Threads 實作助手

一問一步，使用你自己的 Meta App、Threads 帳號及憑證，從設定走到第一篇發布及讀回。

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

已在老師自己的帳號完成 API 身份及單篇純文字發布讀回。學生須自己逐關驗收；Windows 真機、圖片、多篇回覆串及排程未驗收。工具的單篇發布與防重送有隔離測試；不要把安裝成功當成帳號已連線。

本版由 EdwardAI 重新編寫，方向參考 [madebypan/threads-api-skill](https://github.com/madebypan/threads-api-skill)，並以 [Meta 官方 API 範例](https://www.postman.com/meta/threads/collection/dht3nzz/threads-api) 核對。
