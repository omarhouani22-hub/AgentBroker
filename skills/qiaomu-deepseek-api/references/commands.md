# 命令手册

以下命令在 skill 目录运行。Agent 应使用本 skill 的脚本绝对路径。

| 目的 | Python 入口的参数 | 主要返回值 |
|---|---|---|
| 检查配置 | `status` / `setup` / `verify-key` | `status` 只检查本地；后两者通过官方模型目录验证 Key |
| 找来源 | `search 'DeepSeek site:api-docs.deepseek.com' --count 5` | `results`（URL、标题、摘要及日期）、`empty`；加 `--content` 请求站点正文 |
| 提取网页 | `fetch https://api-docs.deepseek.com/guides/ocr/` | `title`、`content`（Markdown） |
| 对话联网 | `chat --web search --prompt '查官方公告并给出链接'` | `answer`、`tool_calls`、`tool_results`、`citations` |
| 深度搜索 | `chat --web deep --prompt '对照官方 ASR 和 TTS 文档，注明出处'` | 同上，开启模型思考 |
| 读指定链接 | `chat --web read --url https://example.com --prompt '总结这个网页'` | 同上，查 `read_link` 调用与结果 |
| 看图 | `chat --image figure.png --prompt '描述这张图'` | 模型对图像的回答 |
| 以图搜图 | `chat --image photo.jpg --web image --prompt '用这张图反向搜图并找原始出处'` | `image_search` 工具结果含可用的 `image_url` |
| 图片/文档识字 | `ocr invoice.png` | 逐页 `pages`、`complete`；可能含布局坐标标记 |
| 文档问答 | `ask-file report.pdf --prompt '文件里的总金额是多少？'` | `answer`、`purpose`、`cleanup.deleted` |
| 图文问答 | `ask-file report.pdf --purpose rich_layout_recognition --prompt '解释图 1'` | 按文档排版提供模型能识别及裁出的图和文字 |
| 转写 | `asr recording.wav` | `text`、`duration_ms`、`empty` |
| 列音色 | `voices` | 离线返回 `stella`、`tide` |
| 配音 | `tts --text-file script.txt --voice stella --output narration.wav` | WAV 路径、格式与秒数；也可用 `--text`；`tide` 为男声 |
| 审核、标题、元信息 | `chat --safety --title --reminder '2026-11-13,星期五,北京,Web,中文' --prompt '给我三个秋季散步建议'` | 结束原因、标题、用量；元信息仅填用户提供的值 |

- 搜索长度为 1–128 Unicode 字符，返回条数 1–50。查询与文件内容会发送给 DeepSeek。抓取使用用户指定的公开 HTTP(S) 地址，避免带登录令牌的链接。
- `chat` 及 `ask-file` 采用单轮、非流式 Messages，模型为 `deepseek-flash`。工具是否被实际调用由服务端决定。核对关键值与原始来源。工具只能在做完后检查，开启深度搜索可能产生多次付费工具调用。
- `ok` 表示 CLI 收到了可解析结果。回答另有 `status: complete|incomplete|refused`。访问失败也可能只出现在 `tool_results[].entries[].error_code`。安全审核开关以官方机制处理，并不验证拒答覆盖率。
- ASR 接受 16 位 PCM WAV 或 Ogg Opus，≤ 8 MiB、≤ 120 秒。需要时先本地转换，例如 `ffmpeg -i input.mp3 -ac 1 -ar 16000 -c:a pcm_s16le recording.wav`，超长材料先分段。
- TTS 使用官方 HTTP PCM 输出并封装为 24 kHz 单声道 16 位 WAV，输出目录须已存在，文件不可重名。官方单次限 10,000 个计费字符（汉字计 2）及 64 KiB JSON；长文按段提交。此版使用 HTTP 整段输入，未封装 WebSocket。
- 独立 OCR 和 ASR 的文件不通过 Files API。文档问答默认按后缀选文本解析或 `user_data`，支持 PDF、DOCX、PPTX、图片、文本和表格等官方格式。上传会消耗配额，成功取得文件 ID 后无论问答结果如何都会尝试清理。上传附一小时有效期，如果删除失败，输出会保留本次文件 ID 以便从 Files API 清理。提供方的数据处理以其条款为准。
- `--timeout` 放在子命令前，单位秒。工具不自动重发请求。常见错误有 401（Key）、402（余额）、429（限速）。已返回的 OCR 文本如果显示 `complete: false`，按页核对或缩小样本。

官方参考：[联网与聊天](https://api-docs.deepseek.com/zh-cn/guides/build_a_chatbot/) · [独立 Search / Fetch](https://api-docs.deepseek.com/guides/search/) · [文件](https://api-docs.deepseek.com/zh-cn/guides/document_parsing/) · [OCR](https://api-docs.deepseek.com/zh-cn/guides/ocr/) · [ASR](https://api-docs.deepseek.com/guides/asr/) · [TTS](https://api-docs.deepseek.com/guides/tts/) · [计费](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)
