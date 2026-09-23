# Install Mio Memory for a user

This guide is addressed to the user's AI agent. Carry out the routine setup and verification yourself; ask the user only for choices or actions that need them. An installation request authorizes local preparation with fictional data. It does not establish which private files may become retrievable by an external AI service.

Read [AGENTS.md](../AGENTS.md), [the privacy boundary](PRIVACY.md), and [known issues](KNOWN_ISSUES.md) first. Respect choices already explicitly made in the conversation. Do not repeatedly ask for the same permission.

The user-facing handoff is [Using Mio Memory in ChatGPT](CHATGPT_USAGE.md). Installation and local process management are the agent's setup work; once connected, the user can request lookups in ordinary ChatGPT conversations without returning to their installation agent each time. Include this guide when delivering the installation.

## 1. Establish the environment

Confirm macOS and a working Python 3.10 or newer. This release uses MCP Python SDK 2.2.0 and is intended for a personal, locally managed installation. Review the repository and its dependency declarations before executing it, as with any downloaded code.

From the repository root:

```sh
python3 scripts/bootstrap.py --check
python3 scripts/bootstrap.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m mio_memory.cli --help
```

The bootstrap creates this checkout's `.venv` and installs the package there. Dependency installation may access the package registry. It does not start a server, open a tunnel, read a real vault, or upload notes. Do not install globally, replace the system Python, create a login item, or modify an existing vault.

If a check fails, diagnose the actual failure and report it accurately. Do not continue to real data while relevant source-boundary or read-only checks fail.

## 2. Prepare a locked fictional installation

Private state must live **outside both this repository and the source vault**. Use a dedicated directory in the user's Application Support folder or another user-approved location. The following example is fictional-data setup only:

```sh
DEMO_STATE="$HOME/Library/Application Support/Mio Memory Demo"
.venv/bin/python -m mio_memory.cli init \
  --state-dir "$DEMO_STATE" \
  --vault "$PWD/examples/demo-vault" \
  --vault-name "Mio Memory Demo" \
  --scope vault_markdown
.venv/bin/python -m mio_memory.cli inspect --state-dir "$DEMO_STATE"
.venv/bin/python -m mio_memory.cli start --state-dir "$DEMO_STATE"
.venv/bin/python -m mio_memory.cli status --state-dir "$DEMO_STATE"
.venv/bin/python -m mio_memory.cli doctor --state-dir "$DEMO_STATE"
```

`init` writes a private `config.json` and refuses to overwrite an existing configuration. If the directory is already initialized, inspect it and reuse it only when it is the intended installation; do not erase it to make the command succeed. All management commands above report structured JSON.

`start` defaults to locked reading and local port **8789**. `--port 0` selects an available port for a local test; use the reported endpoint. Starting the server is not permission to read real notes. Tool discovery must work while `search` and `fetch` refuse reads.

Verify with the official MCP client facilities already installed in `.venv`:

1. The server exposes only `search` and `fetch` and marks both read-only.
2. A read attempt against the default locked server returns `READS_LOCKED`.
3. Stopping the installation removes its server endpoint.

Then reopen the **fictional** scope for a short local test:

```sh
.venv/bin/python -m mio_memory.cli stop --state-dir "$DEMO_STATE"
.venv/bin/python -m mio_memory.cli start --state-dir "$DEMO_STATE" --open-seconds 120
```

Search a distinctive keyword actually present in the supplied fictional notes, fetch a returned ID, and compare the response to its source file and line range. Do not invent the expected answer. The test suite covers source-boundary cases; also confirm source checksums did not change during this smoke test. Stop after the test:

```sh
.venv/bin/python -m mio_memory.cli stop --state-dir "$DEMO_STATE"
```

Do not mistake a passing local test for a working ChatGPT integration.

## 3. Resolve the user's real-data choices

Before exposing real notes, make the scope reviewable. The decision should include:

| Choice | What to establish |
| --- | --- |
| Source | The exact local vault/root directory; keep it outside the checkout |
| Scope | Specific relative `.md` files, or all eligible Markdown recursively under the root |
| Whole-vault implications | Includes future Markdown, diaries, inbox entries, archives, system notes, and Markdown in attachment folders; excludes hidden paths, symlinks, hard links, and non-Markdown attachments |
| Read mode | Short local read window, or continuous availability until manual stop |
| Destination | For ChatGPT, returned titles, source metadata, and fetched sections go to ChatGPT/OpenAI |
| Client permissions | Always ask by default; explain any user-selected workaround separately |

If the user has already approved these in the current conversation, apply that approval. Otherwise ask one concise question that identifies the missing scope or mode. Do not read every personal note simply to prepare a permission question. Do not turn “install this” into approval to expose a whole home directory, unrelated agent memories, or every vault you find.

Selected files are approved as whole files. A requested section does not make the rest of that same file inaccessible. Explain this when a file contains mixed sensitivity.

Initialize real data in a **different private state directory** from the demo. Replace the placeholders with the user's actual approved paths; the following is a template, not a command to run unchanged:

```sh
STATE_DIR="$HOME/Library/Application Support/Mio Memory"
.venv/bin/python -m mio_memory.cli init \
  --state-dir "$STATE_DIR" \
  --vault "/absolute/path/to/approved-vault" \
  --vault-name "My Memory" \
  --scope files \
  --file "An approved note.md"
```

Repeat `--file` for multiple approved files. For an approved whole vault use `--scope vault_markdown` without `--file`. Do not broaden the selected configuration just because another note looks useful. Run `inspect` and review its reported scope before enabling reads.

## 4. Connect ChatGPT using the official private tunnel

Account UI and feature availability can change. Consult the current [official Secure MCP Tunnels guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) and use the account controls actually available. Do not guess API endpoints, invent account IDs, or install an unrelated connector as a substitute.

1. Confirm that the user can enable Developer mode and create a custom app/tunnel connection. If unavailable, retain the tested local installation and explain the missing account feature.
2. Let the user sign in or complete account verification themselves. Never request a password, one-time login code, or API key in chat. Use a secure local input surface for secrets.
3. With the user's chosen Platform organization and ChatGPT workspace, create or select an appropriate Secure MCP Tunnel. Check who else can access that organization/workspace. Reuse an existing tunnel only when its destination and access scope are already understood and approved.
4. Locate or install the official tunnel client as required by the current official guide. Ask for a system-level installation decision if the user has not authorized one; prefer a user-local location where practical. Verify its path and version.
5. Use a dedicated runtime key limited to **Tunnels Read + Use**. Do not run with an administrator key. The user places the key in a local secret file outside the repository and vault, with permissions **0600**. Do not print or include its contents in a command line.
6. Start the real local server **locked**, with the tunnel settings below. Inspect health/readiness before connecting the custom ChatGPT app.
7. Create/connect a custom app such as **Mio Memory Read-only**, selecting the intended private tunnel. Verify only `search` and `fetch` are exposed as read operations. Set the app to **Always ask** by default.

The CLI accepts tunnel settings only as a complete set. The key is read from a protected file; its value must never be substituted into shell arguments:

```sh
.venv/bin/python -m mio_memory.cli start \
  --state-dir "$STATE_DIR" \
  --tunnel-id "YOUR_TUNNEL_ID" \
  --tunnel-client "/absolute/path/to/tunnel-client" \
  --key-file "/absolute/path/to/private-runtime-key"
.venv/bin/python -m mio_memory.cli status --state-dir "$STATE_DIR"
.venv/bin/python -m mio_memory.cli doctor --state-dir "$STATE_DIR"
```

Replace these placeholders locally. Do not paste real account IDs, secret paths, or runtime output into a public issue. The credential file accepts one raw key on a single line, or a single `OPENAI_API_KEY=` assignment; it is not a general shell script or multi-key environment file. Have the user enter the value locally without echoing it, then set the file permissions to `0600`. Never make the file broadly readable to bypass a validation error.

This server has no independent public-server authentication. Do not change its listener to `0.0.0.0`, open an inbound firewall rule, or attach a public unauthenticated forwarding URL. Another transport requires its own reviewed authentication design.

### Login and other manual handoffs

Leave the user at the exact official screen that needs them. Explain the single action needed, let them complete it, and continue from the verified new state. Do not ask them to narrate secret values. If the agent cannot operate the relevant UI, provide a short, current set of account-specific steps and continue local work while the user handles that screen.

## 5. Enable the agreed mode and verify end to end

Stop the locked installation before changing its mode. Rerun `start` with the same state and tunnel arguments, plus **one** approved access option:

- `--open-seconds 600` opens a ten-minute example window; valid windows are 1–600 seconds.
- `--continuous-read` allows reads until the user stops the service. There is no automatic ten-minute stop in this mode.
- Neither option means reads stay locked.

Do not choose continuous mode merely to avoid explaining a timed lock. Equally, do not impose a timed window after the user has explicitly chosen manual start/stop. Result IDs still expire after ten minutes independently of these access modes.

For the first ChatGPT test, select a low-sensitivity passage that is within scope and let the user ask to search for a distinctive keyword and fetch that section. Require a real tool call and a response that includes the source file, line range, and confirmation date where the note provides one. Do not supply the expected personal answer in advance and then count a repeated answer as proof of retrieval.

Acceptance checklist:

- [ ] The reported scope matches the user's choice, and sources are outside the repository.
- [ ] Default locked reads fail; only the agreed local option opens them.
- [ ] Only `search` and `fetch` are discoverable and marked read-only.
- [ ] A local search/fetch returns the expected fictional source with accurate provenance.
- [ ] Relevant tests reject traversal, symlinks, hard links, and out-of-scope access.
- [ ] Source checksums remain unchanged.
- [ ] The real tunnel and local endpoint are healthy, if ChatGPT integration is requested.
- [ ] The user confirms an actual ChatGPT lookup of the approved real passage, or this step is explicitly recorded as pending.
- [ ] `stop` shuts down only the managed processes; a restart with the chosen mode works.
- [ ] No real notes, secrets, configuration, or runtime files entered the repository, and no automatic startup was configured.

The agent can complete local checks independently. A user statement confirming their Mac test is evidence for that test; local checks alone are not. If a test exposes private text in output, keep it local and avoid needlessly echoing it back into logs or a public report.

### Approval-card workaround

Read [KNOWN_ISSUES.md](KNOWN_ISSUES.md). The author's first-version experience was that **Always allow on the first card** worked better than **Allow once**, which sometimes coincided with reading failures, a residual card, or repeated answers. The cause is unconfirmed.

Leave **Always ask** in place unless the user knowingly chooses the optional workaround. Explain that **Always allow reduces later confirmations**; the source access remains read-only, but user intent is not enforced by the server. Do not repeatedly approve a card left after a completed answer or trigger repeated tool calls to make the card disappear.

## 6. Give the user a usable handoff

Provide the actual installation folder, private state location, selected scope, selected read mode, and verified management commands. Use the user's paths in their private handoff only. You may create convenient local launchers outside version control if useful and authorized by the installation request; keep keys out of their command text.

The daily commands are:

```sh
.venv/bin/python -m mio_memory.cli status --state-dir "$STATE_DIR"
.venv/bin/python -m mio_memory.cli stop --state-dir "$STATE_DIR"
```

For restart, provide the **complete tested start command**, including the agreed access option and any required tunnel arguments. Do not hand over a bare `start` command that would silently return the user to locked mode or omit the tunnel.

Explain that the Mac, service, and tunnel must remain online; sleep, offline status, or credential expiration can interrupt availability. Include how to revoke the app/tunnel/key if desired. Stopping retrieval does not remove text already sent to earlier ChatGPT conversations. No source-note rollback is needed because the service has not modified them.

End with a short result summary that clearly separates verified local behavior, verified ChatGPT behavior, and anything still pending. Do not claim automatic maintenance, future support follow-up, or background monitoring unless the user separately asked for and configured it.
