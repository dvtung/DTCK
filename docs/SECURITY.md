# SECURITY

## AI Investment Research & Decision Intelligence Platform

**Version:** 1.0
**Status:** Baseline — derived from SYSTEM_SPECIFICATION.md v1.0 (§32, §41)

---

# 1. Policy

- **No API keys, passwords, or secrets** in source code, Git history, or Docker images (§32).
- All secrets come from environment variables / secret manager only.
- Application roles have the **least privilege** necessary; connections use isolated database credentials.

---

# 2. Secret Management

| Layer | Rule |
|---|---|
| Source code | no secrets; variables via pydantic-settings + `.env` (not committed) |
| Repo | `.env`, `*.pem`, `*.key` git-ignored; `.env.example` documents names only |
| Docker | secrets injected via Compose `env_file`/`secrets` or environment, never baked into images |
| Production | secret manager (e.g. env-based or cloud secret store) |

---

# 3. API Security

- **Authentication:** JWT (access/refresh) for users; hashed API keys for programmatic access — store **only** `key_hash`, never raw keys.
- **Authorization:** RBAC — `ADMIN`, `ANALYST`, `VIEWER`; route-level dependencies enforced in FastAPI.
- **Rate limiting:** per key/user, stricter on LLM-backed endpoints (§47 cost control).
- **Input validation:** Pydantic schemas at the boundary; reject unknown fields; strict types.

---

# 4. Database Security

- Separate DB users: `api_ro` (read-only), `api_rw` (app write), `migration` (DDL only), isolated credentials via env.
- `audit_logs` is **append-only**: API/migration roles get `INSERT/SELECT`, no `UPDATE/DELETE` (§31, §41 agents forbidden to delete audit logs).
- TLS for DB connections in non-local environments.
- TimescaleDB/Postgres runs in a private Docker network (not published to host in prod).

---

# 5. Agent / LLM Security (§41 Agent Governance)

Agents are explicitly forbidden from:
- Changing database schema
- Changing models / scoring weights
- Executing trades
- Deleting audit logs

Tool layer is the only DB access path — LLM has no direct connection (§22). Tool outputs are validated/schema-checked before being returned to the LLM or persisted (ADR-006).

---

# 6. Audit (§31)

Every agent run persists: user request, agent, model + versions, prompt version, tools called, tool inputs/outputs, evidence, final output, timestamp, latency, token usage. Audit data supports reproducibility, debugging, evaluation, and compliance.

---

# 7. Data Protection

- Credentials and tokens are never transmitted to external services; egress proxies/whitelists govern LLM & data-source connections.
- Vector/DB backups (WAL + nightly dumps) are part of the Production definition (§52).
- Raw secrets discovered in logs/code are masked immediately (global rule 0.4).