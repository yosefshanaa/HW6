# Provider-agnostic image for one Cop & Thief MCP server.
# Deploy it TWICE — once per role — each with its own MCP_AUTH_TOKEN:
#   docker build -t cop-thief-mcp .
#   docker run -e ROLE=cop   -e MCP_AUTH_TOKEN=$(openssl rand -hex 32) -e PORT=8080 -p 8080:8080 cop-thief-mcp
#   docker run -e ROLE=thief -e MCP_AUTH_TOKEN=$(openssl rand -hex 32) -e PORT=8081 -p 8081:8081 cop-thief-mcp
# On Cloud Run / Fly / Render the platform injects $PORT and terminates HTTPS for you.
# See docs/DEPLOY.md for the full runbook.
FROM python:3.12-slim

# uv is the only package manager used in this project.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    ROLE=cop \
    PORT=8080

WORKDIR /app

# Dependencies first (cache-friendly), then the project — with the `mcp` (FastMCP) extra.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config
RUN uv sync --frozen --no-dev --extra mcp

EXPOSE 8080

# Provide MCP_AUTH_TOKEN at run time — without it the server logs "auth disabled" and accepts
# unauthenticated calls (intended only for local dev). resolve_bind() binds 0.0.0.0:$PORT.
# TCP health probe needs no token: is the server accepting connections?
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
  CMD python -c "import os,socket; socket.create_connection(('127.0.0.1', int(os.environ['PORT'])), 2).close()"

CMD ["sh", "-c", "uv run --extra mcp cop-thief-${ROLE}-server"]
