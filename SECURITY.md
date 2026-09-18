# Security

Agent sessions are sensitive by nature: they can contain source code,
credentials, customer data, and internal URLs.

## Local by default

- Agent Failure Lab never uploads sessions, never enables telemetry, and
  makes no network calls in the analyze → benchmark path.
- The SQLite store under `~/.agentlab/` keeps run *metadata* only
  (benchmark names, verdicts, timestamps) — never session bodies.

## Before sharing

Scrub sessions before attaching them to issues or PRs:

```bash
agentlab redact session.jsonl --output session.redacted.jsonl
```

Redaction covers private keys, common API-key shapes (`sk-…`, `ghp_…`,
`AKIA…`), bearer tokens, `password = …` assignments, and known secret
environment variables. It is conservative on purpose — review the diff,
because no pattern list catches everything (custom secret formats,
secrets split across lines, screenshots in HTML reports).

Generated Markdown/HTML reports embed session excerpts: treat them with
the same care as the session itself.

## Reporting vulnerabilities

Open a private security advisory on GitHub (or email the maintainers
listed there) rather than filing a public issue. Include steps to
reproduce and the affected version.
