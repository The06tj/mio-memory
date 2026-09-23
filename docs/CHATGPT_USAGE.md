# Use Mio Memory in ChatGPT / 在 ChatGPT 里使用记忆

[中文](#中文) · [English](#english) · [项目首页](../README.zh-CN.md) · [Project home](../README.md)

## 中文

**你可以在普通 ChatGPT 对话里调用这套记忆检索。** 作者已在 ChatGPT Mac 客户端实测：发出检索要求后，ChatGPT 调用 `search` 搜索本地笔记，再调用 `fetch` 读取命中段落，回答包含来源文件、行号和笔记中的确认日期。

这是本项目作者环境中的成功实测，不保证所有账号、客户端版本都具有相同入口。下面把官方 Web 流程与 Mac 的使用经验分开说明。

### 先安装一次，之后在 ChatGPT 里使用

把仓库交给能够操作你电脑的 Agent，并使用 [README 中的安装提示](../README.zh-CN.md#把仓库交给你的-agent)。Agent 按 [安装指南](AGENT_INSTALL.md) 准备环境、运行本机服务、连接私有隧道，并协助你添加 ChatGPT 应用。

你决定开放哪些笔记、何时允许读取，以及客户端的确认方式。**仅把本仓库的 GitHub 链接发进聊天，并不能让 ChatGPT 直接访问本地文件。** 需要先完成服务、隧道与应用的实际连接。

接通以后，日常检索直接在 ChatGPT 里进行，不需要每次返回 Codex 或安装用的 Agent。本机服务和隧道仍需运行；使用手动启停模式时，按安装 Agent 交付的方法启动即可。

### 第一次接入：网页端官方入口

这部分通常由安装 Agent 引导完成。已经连接好应用，可以直接看下一节。

1. 在 ChatGPT 的 **Settings / 设置 → Security and login / 安全与登录 → Developer mode / 开发者模式** 中开启应用开发者模式。
2. 打开 [ChatGPT 应用页面](https://chatgpt.com/plugins)，创建自定义应用，按安装指南选择已配置的官方 Secure MCP Tunnel。应用可命名为 **Mio Memory Read-only**。
3. 核对应用工具只有只读的 `search` 和 `fetch`。默认保留 **Always ask / 每次询问**。
4. 在网页对话的输入框点击 **＋ → Developer mode**，选择刚连接的应用，然后明确要求它进行检索。

以上菜单路径来自 [OpenAI 官方 Developer mode 使用说明](https://developers.openai.com/api/docs/guides/developer-mode#how-to-use)。账号是否提供功能、界面名称以及入口位置可能变化；若看不到，先核对当前账号、工作区及官方说明。

**浏览器设置中的「完整 CDP 访问权限」不是这里需要的开关。** 那是 Browser Use 的浏览器控制权限；本项目要找的是可添加自定义应用的 Developer mode，不需要为了检索笔记额外开启完整 CDP。

### 日常使用：Mac 客户端

1. **确认本机已启动。** Mac 在线，Mio Memory 服务和私有隧道运行正常，并已按你选择的方式开启读取。单纯运行一个默认锁定的服务，还不能读笔记。
2. **在 ChatGPT 里选应用。** 新建或打开普通对话，点击输入框旁的 **＋**，在 **应用 / Apps** 或 **Developer mode** 入口里选择 **Mio Memory Read-only**。名称以你实际安装时的设置为准。
3. **明确提出检索。** 指定应用名、短关键词，以及先 `search` 再 `fetch`。按照自己选择的权限策略处理客户端确认。
4. **检查证据。** 查看或展开工具调用记录，核对确实执行了 `search` 与 `fetch`，并查看回答给出的文件和行号。

Mac 的 **＋ → 应用** 入口和实际调用已在作者环境验证；它不是对所有版本 UI 的保证。如果 Mac 找不到应用，用**同一账号、同一工作区**登录网页端，先确认应用已连接，再按客户端实际提供的 Apps / Developer mode 入口选择。不要把另一个工作区里创建的应用当作本工作区已配置完成。

### 可以直接复制的第一次测试

当安装配置仍指向仓库的虚构示例库时，发送：

> 请实际调用 Mio Memory Read-only，先用 search 搜索“小禾 Python”，再用 fetch 读取相关结果；区分当前与历史记录，引用文件与行号。如果未实际调用，请说明，不要凭印象回答。

「小禾」来自仓库内的**虚构测试笔记**，不是作者或使用者的真实记忆。这里故意不提供预期答案：正确复述一段提前给出的答案，并不能证明工具真的工作。

改接自己的笔记后，把“小禾 Python”换成批准范围内确实存在的一两个关键词。例如，可以要求：

> 请使用 Mio Memory Read-only 检索“这里换成我的关键词”，先 search，再 fetch 必要的命中片段。根据原文回答，注明文件名、行号、确认日期和状态；找不到就说找不到，不要把历史记录当作当前事实。

运行前把引号里的占位文字换掉。关键词按 AND 匹配：多个词必须同时出现，中文短语按原文匹配；过长的问句可能没有结果。

### 怎样才算真的接通

一次有效的验收应同时包含：

- 工具记录显示应用实际执行了 `search`，并对必要结果执行了 `fetch`。
- 读取结果对应你允许的文件，回答给出能核对的来源与行号。
- 回答保留笔记的日期、状态和不确定性；文件更新时间不冒充事实确认时间。

只有“我查到了”的文字、只有模型复述已知答案，或只有工具列表里出现应用，都不足以证明读取成功。服务不会写回笔记，也不会因为一次成功就扩大开放范围。

### 常见情况

| 看到的情况 | 下一步 |
| --- | --- |
| 没有 Mio Memory 应用 | 核对账号、工作区和应用连接；在网页端确认创建完成。单独打开 GitHub 仓库不会完成接入。 |
| 回答了，但没有工具调用 | 重新明确要求使用该应用，并查看调用记录。未调用就记录为未完成，不把自然语言声明当作成功。 |
| 返回 `READS_LOCKED` | 本地读取未启用或窗口已结束。用安装 Agent 交付的启动方法启用你已选择的读窗或手动模式；远端工具不能自行解锁。 |
| 工具无法连接 | 查看本机服务与隧道状态，确认 Mac 在线，并检查凭据是否过期；不要把服务改成公开无认证入口来绕过问题。 |
| 搜索没有结果 | 检查笔记是否在开放范围内，使用更短、原文中确实出现的关键词。先不修改范围，也不凭空补答案。 |
| fetch 的旧结果 ID 不可用 | 结果 ID 十分钟后过期，另一个会话的搜索也可能替换结果集。在没有待确认、拒绝或锁定状态时，重新明确发起搜索。 |
| 回答后还留着确认卡 | 先不要反复点击。参见下面的确认卡说明与已知问题。 |

### 确认卡：默认询问，兼容办法由你选择

默认设置是 **Always ask / 每次询问**。作者的初代实测经验是：第一张卡选择 **Always allow / 始终允许** 比 **Allow once / 允许一次** 更可用；后者出现过读取失败、卡片残留或重复回答。

这是**可选的临时兼容办法**，会减少之后的确认，并非所有人的通用修复。Agent 不应静默替你更改。工具仍然只读，范围与本地读窗仍有效；但“只在我要求时检索”不是服务端能够独立证明的自然语言意图检查。[完整已知问题与官方反馈状态](KNOWN_ISSUES.md)

### 用完之后

按安装 Agent 交付的停止入口关闭服务和隧道即可。连续读取模式不会在十分钟后自动关闭；短时窗口到期会锁定读取。两种模式下，已发送到 ChatGPT 的片段都不会因停止服务而从旧对话中消失。详细边界见 [隐私说明](PRIVACY.md)。

## English

**You can call this memory retrieval service from an ordinary ChatGPT conversation.** In the author's ChatGPT Mac setup, an explicit request successfully triggered `search` against local notes, followed by `fetch` for the matching section. The answer included the source file, line numbers, and the confirmation date recorded in the note.

That is a verified result in the author's environment, not a guarantee that every account or client version exposes the same menus. The official web flow and the project's Mac experience are described separately below.

### Install once; use ChatGPT day to day

Give the repository to an agent that can work on your computer and use the [README installation prompt](../README.md#give-it-to-your-agent). The agent follows [AGENT_INSTALL.md](AGENT_INSTALL.md) to prepare the environment, local service, private tunnel, and ChatGPT app connection.

You choose the notes, access mode, and client confirmation policy. **Pasting this repository's GitHub URL into a chat does not connect ChatGPT to your local files.** The actual service, tunnel, and app connection must be set up first.

Once connected, request everyday lookups directly in ChatGPT; you do not need to return to Codex or the installing agent for every search. The local service and tunnel must remain running. In manual start/stop mode, use the start instructions your installing agent delivered.

### First connection: the official web flow

Your installation agent normally guides this part. If the app is already connected, skip to daily use.

1. In ChatGPT, open **Settings → Security and login → Developer mode** and enable app Developer mode.
2. Open the [ChatGPT apps page](https://chatgpt.com/plugins), create a custom app, and select the official Secure MCP Tunnel configured during installation. A suitable app name is **Mio Memory Read-only**.
3. Confirm that the app exposes only read-only `search` and `fetch`. Keep **Always ask** as the default.
4. In a web conversation, open **＋ → Developer mode** in the input box, select the connected app, and explicitly ask it to retrieve information.

These menu paths come from the [official OpenAI Developer mode instructions](https://developers.openai.com/api/docs/guides/developer-mode#how-to-use). Feature availability, labels, and menu locations can change. If an option is absent, check the current account, workspace, and official instructions.

**The browser setting for full CDP access is a different option.** It controls Browser Use capabilities. This project needs the Developer mode that adds custom apps; enabling full browser CDP access is not required for note retrieval.

### Daily use in the Mac app

1. **Check that the local installation is running.** The Mac is online, the service and private tunnel are healthy, and reads are enabled in your selected mode. A running but default-locked server cannot read notes.
2. **Select the app in ChatGPT.** Open an ordinary conversation, click **＋**, then select **Mio Memory Read-only** through the available **Apps / Developer mode** entry. Use the actual app name from your installation.
3. **Explicitly request retrieval.** Name the app, give narrow keywords, and ask for `search` followed by `fetch`. Handle confirmation according to the permission policy you chose.
4. **Check the evidence.** View or expand tool activity to confirm that `search` and `fetch` ran, then check the answer's source file and line numbers.

The Mac **＋ → Apps** entry and successful tool calls were observed in the author's setup; this is not a promise about all client versions. If you cannot find the app on Mac, check the web interface using the **same account and workspace**, confirm the app is connected, then use the Apps / Developer mode entry your client provides. An app created in a different workspace does not establish a connection in the current one.

### Copyable first test

While the installation points to the repository's fictional sample vault, send:

> Please actually call Mio Memory Read-only: first use search for “小禾 Python”, then use fetch to read the relevant result. Distinguish current and historical records, and cite the file and line numbers. If you did not call the tools, say so rather than answering from memory.

“小禾” is a **fictional test character** in the sample notes, not a real memory about the author or user. The expected answer is deliberately not supplied here: repeating an answer already in the prompt would not prove retrieval worked.

After connecting your own notes, replace “小禾 Python” with one or two distinctive keywords that actually exist in the approved files. For example:

> Please use Mio Memory Read-only to search for “REPLACE WITH MY KEYWORDS”, then fetch only the necessary matching sections. Answer from the source text and include the file name, line numbers, confirmation date, and status. Say when nothing matches; do not present historical records as current facts.

Replace the placeholder before sending. Keywords use AND matching: every term must match. Chinese phrases are matched literally. A long conversational question can produce no results.

### What counts as a successful connection

A useful acceptance test shows all of the following:

- Tool activity records a real `search` and a `fetch` of the needed result.
- The retrieved source belongs to your approved scope, with a checkable file and line range.
- The answer preserves dates, status, and uncertainty. A file modification date is not presented as the fact's confirmation date.

An “I searched” sentence, a correct repeated answer, or an app merely appearing in the tool list is not enough. The service does not write to your notes or expand its scope after a successful lookup.

### Common situations

| What you see | Next step |
| --- | --- |
| No Mio Memory app | Check the account, workspace, and connection in the web app. Opening the GitHub repository alone does not configure it. |
| An answer with no tool calls | Explicitly request the app and check its activity. Treat the test as incomplete if tools did not run. |
| `READS_LOCKED` | Reads are disabled or the local window expired. Use the delivered startup instructions for your chosen mode; remote tools cannot unlock the service. |
| A connection error | Check the local service, tunnel, Mac connectivity, and credential expiration. Do not bypass the problem with a public unauthenticated endpoint. |
| No matching results | Check the approved scope and use shorter keywords that appear in the source. Do not silently expand scope or invent an answer. |
| An old fetch ID is unavailable | IDs expire after ten minutes; another conversation's search can also replace the result set. Request a fresh search when there is no pending/denied approval or locked-read state. |
| An approval card remains after the answer | Avoid repeatedly clicking it. Read the approval-card note below. |

### Approval cards: default confirmation, optional workaround

The default is **Always ask**. In the author's first-version tests, selecting **Always allow on the first card** was more usable than **Allow once**, which was associated with failed reading, residual cards, or repeated output.

This is an **optional compatibility workaround** that reduces future confirmations, not a universal fix. An installing agent must not silently apply it. Tools remain read-only and subject to the configured scope and local read gate, but the server cannot independently verify the natural-language intent behind a call. See [known issues and the support-report status](KNOWN_ISSUES.md).

### When you are finished

Use the delivered stop command or launcher to stop the service and tunnel. Continuous mode does not automatically close after ten minutes; a timed window locks reads when it expires. In either mode, stopping the service does not remove sections already sent to earlier ChatGPT conversations. See [the privacy boundary](PRIVACY.md).
