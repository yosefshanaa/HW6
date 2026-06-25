# Cloud deployment — public HTTPS MCP servers

This is the runbook for putting the **Cop** and **Thief** MCP servers behind public, **HTTPS +
token-authenticated** URLs so a partner team can reach them for the bonus inter-group match
(assignment MUST: *token-auth + HTTPS-only + revoke*).

## Status (honest)

| Piece | State |
|---|---|
| HTTP MCP servers (FastMCP, six tools) | ✅ implemented (`uv run cop-thief-cop-server` / `…-thief-server`) |
| Bearer-token **enforcement** on every request | ✅ implemented + tested end-to-end (`mcp/asgi_auth.py`, `tests/unit/test_asgi_auth.py`) — unauthenticated calls get **HTTP 401** |
| Cloud-friendly binding (`0.0.0.0:$PORT`) | ✅ `mcp/serve.py::resolve_bind` (unit-tested) |
| Container image | ✅ provider-agnostic `Dockerfile` (role-parameterised) |
| **A live public HTTPS URL** | ⛔ **external** — needs *your* cloud account; not run in this repo |
| Real `MCP_AUTH_TOKEN` value, real partner URLs | ⛔ **external** — generated/exchanged out of band, kept out of git |

Nothing here fakes a deployment. The image + enforcement are verifiable locally today; the live
host, the real token value, and the public HTTPS URL are the external stage.

## 1. Token

Each server reads its expected token from the `MCP_AUTH_TOKEN` environment variable (name is
configurable via `auth.token_env_var`). Generate a strong one per role:

```bash
openssl rand -hex 32        # one for the Cop server, another for the Thief server
```

If `MCP_AUTH_TOKEN` is **unset**, the server logs `auth disabled` and accepts unauthenticated
calls — intended only for local development. In the cloud, always set it.

**Revoke / rotate:** the token lives only in the platform's secret store and the server's env.
To revoke, set a new secret value and redeploy (or restart) the service — the old token stops
working immediately because the server only knows the new one. Share the new token with the
partner out of band.

## 2. Build & smoke-test locally (Docker)

```bash
docker build -t cop-thief-mcp .

# Run the Cop server with auth on:
docker run --rm -e ROLE=cop -e MCP_AUTH_TOKEN=s3cret -e PORT=8080 -p 8080:8080 cop-thief-mcp

# In another shell — the gate, proven:
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8080/mcp/                       # 401
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8080/mcp/ \
     -H 'Authorization: Bearer s3cret'                                                            # not 401 (reaches MCP)
```

Run the Thief server the same way with `-e ROLE=thief -e PORT=8081 -p 8081:8081`.

## 3. Deploy (pick one platform — all give managed HTTPS)

The image binds `0.0.0.0:$PORT`; every platform below injects `$PORT` and terminates TLS, so you
get an `https://…` URL automatically. Deploy **once per role** (two services).

**Google Cloud Run** (verified working — used for the live deploy)
```bash
gcloud run deploy cop-thief-cop   --source . --region <r> --allow-unauthenticated \
  --min-instances=1 --max-instances=1 \
  --set-env-vars="ROLE=cop,MCP_AUTH_TOKEN=<cop-token>"   --quiet
gcloud run deploy cop-thief-thief --source . --region <r> --allow-unauthenticated \
  --min-instances=1 --max-instances=1 \
  --set-env-vars="ROLE=thief,MCP_AUTH_TOKEN=<thief-token>" --quiet
```
> `--allow-unauthenticated` opens the *network* path; our **bearer token** is the real gate.
>
> **Gotchas (learned in the live deploy):**
> - **Pin to one instance** (`--min-instances=1 --max-instances=1`): the referee state lives
>   in memory, so a second autoscaled instance would fork the game. One instance, always warm.
> - Pass env vars as **one comma-separated `--set-env-vars`** — repeating the flag overwrites.
> - Use the endpoint **without a trailing slash** (`…run.app/mcp`). `/mcp/` 307-redirects and the
>   HTTP client drops the bearer header on the hop → a misleading 401. (`HttpTransport` now strips it.)

**Fly.io**
```bash
fly launch --dockerfile Dockerfile --name cop-thief-cop --no-deploy
fly secrets set ROLE=cop MCP_AUTH_TOKEN=<cop-token> -a cop-thief-cop
fly deploy -a cop-thief-cop
# repeat for the thief role with a second app + token
```

**Render** — New → Web Service → from this repo, Docker runtime; set env `ROLE` + `MCP_AUTH_TOKEN`
(repeat for the second service). **Railway** — New → Deploy from repo (Dockerfile); add the same
two env vars per service.

## 4. Wire the URLs into config

Once the two services are live, put the **https** URLs into `config/config.yaml`. They stay
`TODO:` placeholders until you have real endpoints — never commit real tokens (those go in the
platform secret store / `.env`, both git-ignored).

```yaml
mcp:
  cop_url:   "https://cop-thief-cop-….run.app/mcp/"
  thief_url: "https://cop-thief-thief-….run.app/mcp/"

# For the bonus match, also fill the match.* URLs (yours + the partner's, exchanged out of band):
match:
  mcp_url_group_1_cop:   "https://…/mcp/"
  mcp_url_group_1_thief: "https://…/mcp/"
  mcp_url_group_2_cop:   "https://…partner…/mcp/"
  mcp_url_group_2_thief: "https://…partner…/mcp/"
```

The bonus match swaps the loopback `InProcessTransport` for these HTTPS endpoints without changing
the match logic (`agents/agent_client.py::HttpTransport`, the FastMCP client with bearer auth — see
[`PRD_bonus_match.md`](PRD_bonus_match.md) and [`../SHARED_MATCH_RULES.md`](../SHARED_MATCH_RULES.md)).

## 5. Match-day runbook

1. **Deploy** both roles (§3), each with its **own** `MCP_AUTH_TOKEN` (cop token ≠ thief token).
2. **Smoke-test every URL** with the built-in checker (preferred over raw `curl` — it speaks MCP and
   verifies the token *and* that the absence of one is rejected):
   ```bash
   uv run cop-thief-smoke https://…cop…/mcp/   --token <cop-token>   --check-auth
   uv run cop-thief-smoke https://…thief…/mcp/ --token <thief-token> --check-auth
   ```
   Expect `[ok] health={…}` **and** `unauthenticated call rejected — bearer auth enforced`.
3. **Exchange** the four URLs + tokens and the **shared seed** with the partner out of band; fill
   `match.*` URLs and team metadata (`match.group_*`, `match.students_*`) in config.
4. **Play.** Each team derives identical sub-game start cells from the shared seed; the orchestrator
   begins each of the 6 sub-games with the `reset` tool (`AgentClient.reset(cop, thief)`), then runs
   the thief-first turn loop. A network drop mid-sub-game = Technical Loss → rerun (shared rules §3).
5. **Reconcile & report**: compare per-sub-game outcomes (the mirror engines flag any divergence),
   then each team emails its identical §9.2 JSON.
6. **Revoke** the tokens (rotate the secret + redeploy) once the match is done.
