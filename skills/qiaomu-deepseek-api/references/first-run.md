# 首次使用与音色选择

## 首次使用

1. 安装 skill 不需要填写钥匙，也不会自动联网。第一次执行真实任务前运行 `python3 scripts/deepseek_api.py status`。已有宿主注入的 `DEEPSEEK_API_KEY` 或本 skill 配置时继续。无需在每次处理前额外验证。
2. 遇到 `missing_key` 或 401，先告诉用户原任务会在配置后继续。给出 [官方 API Keys 页面](https://platform.deepseek.com/api_keys)，请用户登录、创建自己的 API Key。提供从所在 skill 目录运行的命令 `python3 scripts/deepseek_api.py setup`，或者给出带引号的脚本绝对路径，方便在自己的终端复制运行。
3. 输入只在用户终端隐藏显示。不要在对话卡、聊天、命令参数、日志或录屏中索要或显示 Key。也可由宿主安全注入 `DEEPSEEK_API_KEY`，随后用 `verify-key` 检查。环境变量优先。
4. `setup` 先调用官方 `GET /models` 验证 Key，再保存到独立配置目录。验证失败保留原配置。模型目录返回只证明身份可用，付费工具还可能受余额和限流影响。用户确认配置完后，继续原任务，不只回复“已配置”。

## TTS 音色

- 用户明确给了音色、男声、女声或选择默认时，直接映射并执行。海星 `stella` 为女声和官方默认音色，暗潮 `tide` 为男声。
- 没有指定音色时，优先用宿主提供的单选卡工具展示「海星 Stella · 女声（推荐）」和「暗潮 Tide · 男声」，等待用户提交。宿主没有选择卡工具时，在聊天中列出相同两个选项并等待回复。用户可在 [试听目录](../assets/voices/) 比较同一句话。
- 无人值守场景由调用方显式传 `--voice stella` 或 `--voice tide`。用 `voices` 离线读取本版音色清单。官方新增音色需要先核对 [当前规格](https://api-docs.deepseek.com/zh-cn/guides/tts/) 再更新清单。
