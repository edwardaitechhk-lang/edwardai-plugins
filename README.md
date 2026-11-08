# EdwardAI 集合

課程學生用的 Claude Code 工具包。一個 marketplace，之後會陸續加入新的包；裝一次，以後新包和更新都從同一個地方取得。

## 第一次安裝（只做一次）

在 Claude Code 對話框輸入：

```
/plugin marketplace add edwardaitechhk-lang/edwardai-plugins
```

或者在 Mac「終端機」貼上：

```
claude plugin marketplace add edwardaitechhk-lang/edwardai-plugins
```

## 目前有的包

| 包 | 安裝 | 用途 |
|----|------|------|
| 工作模式三件套 `work-mode` | `/plugin install work-mode@edwardai` | 讓 Claude Code 少問多做、懂得派工、會收尾 |

### 工作模式三件套

裝好之後重開 Claude Code，在對話中輸入：

| 指令 | 甚麼時候用 | Claude 會怎樣做 |
|------|-----------|----------------|
| `/work-mode:auto` | 交一件事給它，想它一路做完 | 可以還原的步驟不停下來問；發送、付款、部署、刪除等動作不做，最後集中一次請你批准 |
| `/work-mode:out` | 工作量大，想省額度 | 批量工作派給 subagent（或你電腦上已裝的 Codex／Gemini CLI），主線只規劃和驗收 |
| `/work-mode:wrap` | 準備關掉對話 | 不開新支線，做完、驗證、寫進檔案，只提交自己改過的檔，出一張收尾單 |

三個可以一起用，例如先 `/work-mode:auto` 開工，做完再 `/work-mode:wrap` 收尾。想回到正常模式，直接說「正常模式」即可。

## 更新

```
/plugin marketplace update edwardai
```

## 給 AI 助手的指示

如果使用者把這個網址貼給你並要求安裝：

1. 用 Bash 執行 `claude plugin marketplace add edwardaitechhk-lang/edwardai-plugins`
2. 再執行 `claude plugin install work-mode@edwardai`
3. 執行 `claude plugin list`，確認 `work-mode@edwardai` 在清單中
4. 告訴使用者：重開 Claude Code 後，輸入 `/work-mode:auto`、`/work-mode:out`、`/work-mode:wrap` 即可使用
