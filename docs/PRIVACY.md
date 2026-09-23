# Privacy and access / 隐私与权限

**Publishing this architecture does not publish a user's memory.** A real vault, private configuration, runtime credentials, logs, account identifiers, and diagnostic captures belong outside the public repository.

## What is local, and what is sent

The Markdown files stay on the user's computer. Searching reads approved files locally. There is no embedding service, background index, model API call, or whole-vault upload in the retrieval code.

Search returns matching titles, result IDs, and source links. Fetch returns a selected section and its source metadata, including relevant original frontmatter. Those results are sent through the configured transport to the calling AI. With ChatGPT, they enter ChatGPT/OpenAI and the conversation. A section may contain more context than the single sentence the user asked about.

Relative note paths, titles, source links, and vault names can themselves reveal information. Do not treat search metadata as anonymous. The user's applicable ChatGPT account settings and service terms govern handling after the data reaches that service; this repository does not alter them.

## What may be read

Installation starts with fictional data. The user then chooses one approved root and either:

- **Selected files:** an exact Markdown allowlist. Permission applies to the whole selected file; a section is a retrieval unit, not a separate privacy boundary.
- **Whole vault:** eligible non-hidden Markdown recursively within the approved root, including future files. This can include diaries, inbox material, system notes, archives, and attachment captions stored as Markdown. Review that scope before choosing it.

The server does not follow note links to add permissions. It rejects or skips symlinks, hard links, special files, hidden paths, traversal, non-Markdown attachments, and reads outside the approved root. Obsidian is not required. Images and PDFs are not parsed by this release.

The source directory is pinned while a process runs to reduce the risk of a renamed or replaced path redirecting reads. All source file opens are read-only. Source notes are not rewritten, moved, indexed on disk, or automatically curated.

## What “private tunnel” means

The server binds to `127.0.0.1`. With the official Secure MCP Tunnel it establishes an outbound connection; no public HTTP endpoint on the Mac or inbound firewall opening is needed. The tunnel is associated with a Platform organization and ChatGPT workspace, whose permissions the installing user should verify. See [the official transport documentation](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

This is not a guarantee that nobody else can ever access the data. Relevant risks include account compromise, overly broad organization/workspace access, leaked credentials, and software already running on the same Mac. Loopback is not authentication against other local programs. The MCP service has no standalone public-server authentication; never bind it publicly or attach an unauthenticated public forwarding service.

Use a dedicated runtime credential restricted to **Tunnels Read + Use**. Management operations require separate management authority; do not keep an administrator credential as the runtime key. Credentials belong in a local protected secret file or suitable secret storage, with restrictive permissions, never in command arguments, chat messages, screenshots, logs, commits, or issue attachments. Rotate or revoke them through the official account controls when appropriate.

## Controls and their limits

| Control | What it does | What it does not do |
| --- | --- | --- |
| File or vault scope | Restricts readable sources | Redact sensitive passages inside an allowed file |
| Read-only implementation | Provides no source-write or delete operation | Make disclosure of readable material harmless |
| Locked default | Refuses reads until locally enabled | Prevent a user from deliberately opening access |
| Timed window | Automatically closes the read gate | Remove text already returned to a conversation |
| Manual start/stop | Lets the user keep access available while wanted | Automatically stop at a short deadline in continuous mode |
| Client Always ask | Requests client confirmation according to its policy | Prove server-side intent or guarantee bug-free client UI |
| Tool instructions | Ask the AI to retrieve only on explicit request | Cryptographically enforce natural-language intent |
| Private tunnel | Avoids an unauthenticated public Mac endpoint | Replace account, workspace, key, or local-machine security |

The installer defaults to **Always ask**. The optional **Always allow** workaround described in [known issues](KNOWN_ISSUES.md) deliberately reduces confirmations. It does not add write capabilities, but it makes the tool instructions and local access controls more important. Do not silently select it for another user.

## Stop and revoke

Stopping the managed installation stops its server and tunnel. Verify the processes are stopped and the configured local endpoint no longer serves tools. There is no automatic startup unless the user separately requests and configures it.

For a more lasting disconnection, disconnect the app in ChatGPT and revoke its dedicated runtime credential or tunnel through the official controls. Removing a connector or stopping a process does not delete passages already present in earlier conversations.

The source vault needs no rollback because this service does not modify it. If changing scope, stop the service first, update only the private configuration with the user's approved choice, then repeat relevant checks before reconnecting.

## Sharing reports or changes

Use a minimal fictional reproduction. Share the client version/build, operating system, approximate or exact incident time with timezone, observed behavior, and sanitized error text. Inspect attachments before sending them anywhere. Full HAR files, terminal logs, screenshots, and copied conversation pages can contain tokens, note contents, or personal identifiers.

The repository's ignore rules are an accident-prevention aid, not a secret scanner or access-control mechanism. Review the actual files staged for publication. Never copy a working personal installation wholesale into a public repository.
