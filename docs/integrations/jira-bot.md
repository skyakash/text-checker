# Integration: Jira Bot

Automate release-note and description grooming on Jira tickets by wiring
a small webhook bot to text-checker's MCP HTTP transport (or the plain
HTTP API, if you prefer). This document describes the pattern — the bot
itself is left to your team, because it depends on how you host webhook
receivers, your Jira automation setup, and which Jira Cloud/Server
version you run.

## What the bot does

```
Jira ticket transitions to "Ready for Release"
        │
        ▼
Jira webhook → your bot endpoint (e.g. AWS Lambda, Cloud Run, k8s pod)
        │
        ▼
Bot calls MCP `correct_text` (or POST /v1/correct)
  {
    "text": <ticket description>,
    "mode": "release-note"
  }
        │
        ▼
text-checker pipeline: mask → RAG (product docs) → LLM → guard
        │
        ▼
Bot posts corrected text as a comment,
   or updates the description field,
   or both.
```

Because text-checker's release-note mode pulls in product-doc context via
RAG, corrections respect your team's terminology automatically — no
per-repo config needed.

## Two integration surfaces

You can talk to text-checker either way:

| Surface | When to use |
|---|---|
| **MCP HTTP** on port 8081 | If your bot already talks MCP (e.g. it's itself an LLM agent). Uses the streamable-HTTP MCP transport; requires `X-API-Key`. |
| **Plain HTTP** `POST /v1/correct` on port 8080 | If your bot is straight code (webhook handler, Lambda). Simpler — one JSON POST. |

For most Jira bots the plain HTTP path is easier. Reserve MCP for
Copilot/Codex-style consumers.

## Minimal bot (plain HTTP)

```python
# jira_bot.py — Flask example. Adapt to your framework.
import os
import httpx
from flask import Flask, request

app = Flask(__name__)
CHECKER_URL = os.environ["TEXT_CHECKER_URL"]
CHECKER_KEY = os.environ["TEXT_CHECKER_API_KEY"]
JIRA_BASE = os.environ["JIRA_BASE_URL"]
JIRA_AUTH = (os.environ["JIRA_USER"], os.environ["JIRA_TOKEN"])


@app.post("/webhook/jira")
def on_transition():
    event = request.json
    issue = event["issue"]
    new_status = event["changelog"]["items"][0]["toString"]
    if new_status != "Ready for Release":
        return "", 204

    original = issue["fields"]["description"] or ""
    if not original.strip():
        return "", 204

    r = httpx.post(
        f"{CHECKER_URL}/v1/correct",
        json={"text": original, "mode": "release-note"},
        headers={"X-API-Key": CHECKER_KEY},
        timeout=90,
    )
    r.raise_for_status()
    resp = r.json()

    if resp["flagged"]:
        # Guard rejected — leave the ticket alone, post an advisory comment.
        _comment(issue["key"], f"text-checker flagged this note: {resp['flag_reason']}")
        return "", 204

    corrected = resp["corrected_text"]
    if corrected == original:
        return "", 204  # nothing changed

    # Two options; pick one policy for your team:
    #   (a) Post the correction as a comment for the ticket owner to review.
    #   (b) PATCH the description directly.

    _comment(
        issue["key"],
        f"**text-checker suggested edit:**\n\n{corrected}\n\n"
        f"Model: `{resp['model_used']}`. "
        f"RAG chunks used: {len(resp['rag_context_used'])}.",
    )
    return "", 204


def _comment(issue_key: str, body: str) -> None:
    httpx.post(
        f"{JIRA_BASE}/rest/api/3/issue/{issue_key}/comment",
        json={"body": {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": body}]}
        ]}},
        auth=JIRA_AUTH,
        timeout=30,
    )
```

## Configuring the Jira webhook

- **Jira Cloud:** *Settings → System → Webhooks*. Point at your bot's `/webhook/jira` endpoint. Filter to the "Issue updated" event, optionally scoped to a JQL like `project = REL AND status = "Ready for Release"`.
- **Jira Data Center:** same as Cloud but under *Advanced → Webhooks*.
- **Jira Automation:** as an alternative, use *Project Settings → Automation → Send web request* to POST to your bot on the transition — no webhook registration needed.

## Security notes

- Terminate TLS in front of your bot. The webhook payload contains ticket bodies.
- Verify Jira's webhook secret / signature if your Jira version supports it.
- The bot needs a text-checker API key. Rotate it out of band; don't paste it into ticket bodies.
- text-checker's `/v1/correct` is rate-limited per API key (60/min by default) — give the bot its own key so it doesn't share a bucket with humans.

## Alternative: MCP HTTP

If you'd rather have the bot speak MCP (for example, because it also
talks to other MCP servers), point it at `http://text-checker-host:8081/mcp`
with the same `X-API-Key` and call the `correct_text` tool. The behaviour
is identical — the MCP server is a thin proxy of the plain HTTP API.
