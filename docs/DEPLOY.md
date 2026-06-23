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

**Google Cloud Run**
```bash
gcloud run deploy cop-thief-cop   --source . --region <r> --allow-unauthenticated \
  --set-env-vars ROLE=cop   --set-env-vars MCP_AUTH_TOKEN=<cop-token>
gcloud run deploy cop-thief-thief --source . --region <r> --allow-unauthenticated \
  --set-env-vars ROLE=thief --set-env-vars MCP_AUTH_TOKEN=<thief-token>
```
> `--allow-unauthenticated` opens the *network* path; our **bearer token** is the real gate.

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
the match logic (see [`PRD_bonus_match.md`](PRD_bonus_match.md) and
[`../SHARED_MATCH_RULES.md`](../SHARED_MATCH_RULES.md)).
