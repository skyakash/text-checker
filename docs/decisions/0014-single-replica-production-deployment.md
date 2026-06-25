# 0014. Single-replica production deployment recipe

Date: 2026-06-25
Status: Accepted

## Context

After Stage 1 + Stage 2 + Phase 1 hardening (Redis-backed state, active /readyz probe), the service is operationally ready for a single-replica production deployment. Two paths exist: Docker Compose (recommended for most operators) and bare-metal systemd (for RHEL environments without Docker). Multi-replica / k8s deployment is explicitly deferred — the infrastructure for it (Postgres request log, Helm chart) is tracked but not yet built.

## Decision

### Docker Compose path (recommended)

A `docker-compose.prod.yml` overlay adds production concerns on top of the existing `docker-compose.yml`:

- `restart: unless-stopped` on all services
- `image: text-checker:latest` replaces the `build:` directive (image is built once, not on every up)
- `./data:/app/data:Z` bind-mount makes the knowledge base (glossary + Chroma) persistent across container restarts
- Named volumes for Redis (RDB snapshot enabled: `save 3600 1`) and Prometheus
- JSON file logging with `max-size: 50m / max-file: 5` — no external log driver needed
- `env_file: .env.prod` separates secrets from the compose file

Usage:
```bash
docker build -t text-checker:latest .
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Bare-metal systemd path (RHEL / Ubuntu without Docker)

`deploy/text-checker.service` runs uvicorn directly under a dedicated `text-checker` system user. Security hardening: `NoNewPrivileges`, `PrivateTmp`, restricted `ReadWritePaths`. Reads secrets from `.env.prod` via `EnvironmentFile`. Depends on `ollama.service` and `redis.service`.

### Scripts

- `scripts/backup.sh` — tarballs `./data/` to a timestamped archive, prunes backups older than 30 days
- `scripts/update.sh` — backs up, pulls latest code, rebuilds the image, restarts the service container, polls `/readyz` for up to 60s, exits non-zero if it doesn't come up

### Log rotation

- Docker path: handled by the `json-file` driver options in `docker-compose.prod.yml`
- Bare-metal path: `deploy/logrotate.conf` (daily, 14-day retention, compress)

## Consequences

- Operators can go from dev (`make dev`) to unattended production (`docker compose ... up -d`) with a single page of instructions
- The knowledge base (`./data/`) survives service restarts and updates via the bind-mount / backup scripts
- `scripts/update.sh` makes the update procedure explicit and auditable — no manual steps that can be forgotten
- Multi-replica deployment is not addressed here; that path requires the Postgres request log (#21) and Helm chart (#23) which are deferred
