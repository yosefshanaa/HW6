# PRD — Gmail OAuth Reporting (JSON-only email)

**Mechanism PRD** (per submission guidelines §2.3). **Version:** 1.00.
**Parent:** [`PRD.md` §13](PRD.md#13-reporting--email-requirements) · **Design:**
[`PLAN.md` §13](PLAN.md#13-gmail-reporting-flow).
**Source:** `main-google-api-installtion-guid.pdf` (Gmail/Calendar OAuth setup).

---

## 1. Description & Theoretical Background

At the end of a clean 6-sub-game series, the system **automatically** emails a single report to
`rmisegal+uoh26b@gmail.com`. The **email body contains only the JSON report** (no surrounding text),
so the course's automated parser can ingest it. Delivery uses the **Gmail API** with OAuth 2.0 — more
reliable and auditable than SMTP, and (per the assignment) token-based auth is preferred over a
stored password: an OAuth token is short-lived and scoped, so a leak is far less damaging.

---

## 2. Specific Requirements

### 2.1 Google Cloud / OAuth setup (from the install guide)
- Create/select a Google Cloud project; keep the **same** project throughout.
- **Enable the Gmail API** (under *APIs & Services → Library*).
- The guide also enables the **Calendar API** for its own test script; for **this** project Calendar
  is **optional** — mark it not-needed unless a feature requires it.
- Use an **OAuth Client ID** (*not* an API key). **Application type: Desktop app.**
- **Audience: External**; add the sending Gmail account as a **Test user** (Testing mode).
- Download `credentials.json`; the first authorized run produces `token.json`.
- **`credentials.json` and `token.json` are never committed** (`.gitignore` already lists them).

### 2.2 Scopes & least privilege
- The install guide configures two scopes: `gmail.modify` and `calendar`.
- For this project the report only needs to **send** mail. Document least-privilege reasoning and use
  the **minimum Gmail scope** that lets the chosen send method work:
  - Preferred minimal: `https://www.googleapis.com/auth/gmail.send` (send-only), **or**
  - If we keep the guide's flow as-is: `https://www.googleapis.com/auth/gmail.modify` (broader; used
    by the guide's draft example).
- **Do not** request the `calendar` scope for this project unless a Calendar feature is actually
  added (it is not).

> The chosen scope is recorded in config/docs; the test suite asserts the scope list matches the
> documented least-privilege choice.

### 2.3 Report content
- **Internal game:** body = the §9.1 JSON (`group_name`, `students`, `github_repo`, `cop_mcp_url`,
  `thief_mcp_url`, `timezone`, `sub_games`, `totals`).
- **Bonus game:** body = the §9.2 JSON (`report_type: "bonus_game"`, both groups' repos + 4 MCP URLs,
  `students_group_*`, `sub_games`, `totals_by_group`, `bonus_claim`, `mutual_agreement: true`).
- Body is **JSON only** — no subject text leaking into the body, no signature, no Markdown fences.
- Sent through the **API Gatekeeper** (retries/rate limits/logging).

### 2.4 Trigger
- Fires exactly once, after the orchestrator confirms **6 clean sub-games** (Technical Losses don't
  count). Idempotent per series.

---

## 3. Input / Output / Performance

| | Spec |
|---|---|
| **Input** | `MatchReport` dict (schema-valid) + recipient from config |
| **Output** | A sent Gmail message id; the email body is the serialized JSON |
| **Auth** | OAuth via `credentials.json` → `token.json` (refresh handled) |
| **Failure handling** | Gatekeeper retries transient errors; hard failure logged + surfaced |
| **Performance** | One API call per series; negligible |

### 3.1 Minimal send flow (illustrative)

```python
creds  = load_or_refresh(credentials="credentials.json", token="token.json", scopes=SCOPES)
service = build("gmail", "v1", credentials=creds)
raw    = base64.urlsafe_b64encode(EmailMessage_with_json_body.as_bytes()).decode()
service.users().messages().send(userId="me", body={"raw": raw}).execute()
```

The body of `EmailMessage_with_json_body` is `json.dumps(report)` and **nothing else**.

---

## 4. Constraints, Alternatives & Decisions

- **Decision (ADR-005):** Gmail API + OAuth (Desktop app, External + Test user), JSON-only body.
- **Alternative — SMTP + app password:** rejected; the spec prefers token auth (safer than a stored
  password) and the Gmail API is more auditable.
- **Alternative — include human-readable text + JSON:** rejected; the body must be **only** JSON for
  automated parsing.
- **Constraint:** least-privilege scope; Calendar scope omitted for this project; secrets never
  committed.

---

## 5. Success Criteria & Test Scenarios

**Success:** a mocked test proves a JSON-only body is sent to the recipient via the Gmail API; one
live smoke test delivers a real report; secrets are git-ignored; scope matches the documented
least-privilege choice.

| # | Scenario | Expected |
|---|---|---|
| T1 | Build internal report | Validates against §9.1 schema |
| T2 | Build bonus report | Validates against §9.2 schema; `mutual_agreement: true` |
| T3 | Send (mocked Gmail) | One `messages.send` call; body == `json.dumps(report)` |
| T4 | Body content | Parses as JSON; no extra text/fences |
| T5 | Token expired | Refresh path used; send still succeeds (mocked) |
| T6 | `credentials.json`/`token.json` | Present locally, absent from git |
| T7 | Scope assertion | Equals the documented minimal scope; no `calendar` scope |
| T8 | Live smoke (manual) | Real email arrives at `rmisegal+uoh26b@gmail.com`, body JSON-only |
