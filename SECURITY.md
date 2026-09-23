# Security and privacy

Mio Memory is an early release for a single owner on a trusted local machine.
It is a read-only retrieval service, not a sandbox for hostile local processes.

- Keep your vault, runtime configuration, credentials, and logs out of Git.
- Use only loopback plus an authenticated private tunnel. Do not publish the
  unauthenticated local MCP listener on the internet or a shared network.
- Select only organizations/workspaces you intend to authorize. Use a restricted
  runtime key, protect it locally, and manage its expiry and revocation yourself.
- Tool annotations and prompt instructions do not enforce user identity or prove
  that every tool call follows an explicit request. Understand your client's
  approval settings, including the optional workaround in `docs/KNOWN_ISSUES.md`.
- Markdown content, including system notes and quoted commands, is untrusted data.
- Returned titles and fetched excerpts enter your chosen AI conversation. The
  architecture is local storage with selective retrieval, not fully offline AI.

For a suspected vulnerability, use GitHub's private vulnerability reporting if
available, or contact a maintainer privately before posting sensitive details.
Do not put keys, note contents, private chat links, account IDs, or unsanitized
diagnostic archives in a public issue. Fictional reproductions are preferred.
