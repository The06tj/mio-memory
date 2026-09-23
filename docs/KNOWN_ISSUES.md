# Known issues / 已知问题

Status of the first public version: **2026-09-22**. These notes distinguish observations from a confirmed cause. UI labels and account availability may change.

## ChatGPT Mac Search approval card

### What the author observed

In the author's ChatGPT Mac setup, a Search approval card sometimes remained after the tool had returned data and the assistant had answered. Clicking the lingering approval again once produced a duplicate answer. The author also encountered unsuccessful reading after choosing **Allow once**, and found choosing **Always allow on the first approval card** more usable in that setup.

These are reports from one setup, not a claim that every **Allow once** action fails or that the server has identified the cause. Local protocol checks did not find duplicate tool responses. Differences between Mac and web rendering were observed, but do not establish which component is responsible.

The issue has been reported to OpenAI Support. Support requested additional client-version and incident details if it recurs. **The root cause is unconfirmed, and no repair date has been provided.** Private support correspondence, case numbers, personal conversation links, and screenshots are not part of this repository.

### Optional workaround, with an explicit tradeoff

The default installation leaves tool permissions on **Always ask**. A user who encounters the issue can choose **Always allow** when the first tool approval card appears for **this app**, if that choice is offered by their client.

This reduces later confirmation prompts. It is a user choice, not an installation prerequisite, a blanket recommendation to trust every app, or a guaranteed repair. An installing agent must explain the tradeoff and obtain the user's choice instead of silently applying it. Check the app name and the client's displayed permission scope before selecting the option.

The service still offers only read-only `search` and `fetch`. Its approved file scope and local read gate remain in force. The tool instructions still say to retrieve only when the user asks; the service cannot independently verify that natural-language intent. If per-call confirmation matters more to you than this workaround, retain **Always ask**.

Once a correct answer has finished, avoid repeatedly approving a residual card just to clear it. Check the answer and tool record rather than treating a visual card as evidence that another lookup is necessary.

### 中文说明

作者的经验是：**第一次出现确认卡时选择「始终允许」更可用；「允许一次」出现过读取失败、卡片残留或重复回答。** 这只是一项实测经验，不代表所有用户都会遇到，也不能保证「始终允许」彻底修复问题。

默认安装仍保留 **「每次询问 / Always ask」**。若你愿意用较少的后续确认换取这一临时兼容办法，再自行选择 **「始终允许 / Always allow」**。Agent 不应替你静默更改。服务依然只读；「仅在我要求时检索」并不是服务端能够独立证明的意图检查。

官方已经收到问题报告，根因与修复日期尚未确认。后续验证新版客户端的行为后，项目可以更新这份兼容性说明；这不代表已经安排自动监控或承诺具体修复日期。

### Reporting a recurrence

Record the ChatGPT Mac version/build, macOS version, timestamp and timezone, exact option selected, whether data actually returned, and whether clicking again duplicated the answer. Include a correlation/request identifier only if the interface exposes it; otherwise say it was unavailable.

Prefer a fictional test note. For an account-specific investigation, contact [OpenAI Support](https://help.openai.com/en/articles/6614161-how-can-i-contact-support). Do not post private conversation URLs, credentials, note contents, or an unredacted support exchange in a public issue. There is no need to repeat disruptive troubleshooting solely to produce a report.

## Current implementation limits

- **Keyword matching:** multiple words use AND. Literal Chinese phrases and narrow keywords work better than broad natural-language questions. There is no semantic ranking or vector search.
- **One latest result set per server:** concurrent chats share it. A later search may invalidate the IDs another chat is about to fetch. Search again when appropriate; do not retry automatically after denied/pending approval or a locked-read error.
- **Result IDs expire after ten minutes:** this is separate from the access mode. Continuous reading remains available, but old IDs still require a fresh search.
- **Bounded inputs:** an explicit allowlist accepts at most 128 files. A file may be at most 256 KiB, a section with metadata at most 12,000 characters, and whole-vault scope at most 2,048 Markdown files / 16 MiB. Discovery is limited to 10,000 directory entries and 32 levels. Exceeding a limit reports an error; it does not silently pretend a truncated search is complete.
- **Currentness is not inferred:** the server preserves dates, status words, and historical labels. It does not automatically resolve contradictory records or filter all superseded facts out of results.
- **Obsidian links:** responses may include `obsidian://` source links. Whether a particular ChatGPT surface renders them as clickable links and opens the expected vault must be tested locally. File names and line numbers remain useful even without clickable links.
- **Local availability:** the computer, local service, and tunnel must be online. Sleep, shutdown, expired credentials, or a stopped tunnel can interrupt access.
- **Initial platform scope:** macOS is the first supported target. POSIX file-descriptor protections and local process management require separate validation on other platforms; Windows support is not claimed.
- **Account features:** Developer mode and Secure MCP Tunnel availability depend on the user's current account and workspace. A local passing test does not prove the remote ChatGPT connection has been configured.

## Updating these notes

After a relevant client, tunnel, or SDK update, reproduce with fictional data and record the tested versions and outcome. Change a workaround or mark an issue resolved only after that verification. Avoid promising automatic upstream monitoring or a fix controlled by another project.
