# Architecture & Deep Dive

This is the in-depth reference for `opensource_deployment3`. For a quick start, see
the top-level [`README.md`](../README.md). For the `CMD_STRING_FORMAT` templating
syntax, see [`Configuration.md`](./Configuration.md).

## Table of Contents

1. [System Overview](#system-overview)
2. [Two-Server Topology](#two-server-topology)
3. [Component Map](#component-map)
4. [Tooling Layer](#tooling-layer)
5. [Instance Lifecycle](#instance-lifecycle)
6. [Configuration System](#configuration-system)
7. [Docker Compose Layering](#docker-compose-layering)
8. [Networking Model](#networking-model)
9. [Secrets & Security Model](#secrets--security-model)
10. [Image Build & Tagging](#image-build--tagging)
11. [Read Replica / Analytics Sync](#read-replica--analytics-sync)
12. [Extending the System](#extending-the-system)
13. [Design Rationale](#design-rationale)

---

## System Overview

`opensource_deployment3` is a self-contained, Python-based deployment tool for
Ingenium. It has no dependency on a CI server or an external container
registry: images are built directly on the target server VM and consumed
locally by `docker compose`.

The tool is split into two concerns:

- **Bootstrap tooling** (`clone_repos.py`, `build_images.py`, `setup_instance.py`,
  `ingenium.py`) — Python scripts that clone source, build images, generate
  instance configuration, and orchestrate deployment.
- **Runtime definitions** (`docker-compose*.yml`, `project_instance_template/`) —
  the actual service topology and per-instance configuration that gets
  generated from the template.

`ingenium.py` is the single entry point (`./run.sh` → `./ingenium.py`) that
wraps all of the above into one interactive, menu-driven wizard. Every
capability is also available as a standalone CLI script for scripting/CI use.

## Two-Server Topology

Ingenium is deployed across exactly two logical machines:

| Server | Role | Compose file | Services |
|---|---|---|---|
| **Main Server** | Core application: auth, execution, archive, UI | `docker-compose.yml` | `auth_service`, `archive_ing`, `exec_server`, `execution_monitor`, `core_server`, `dict_service`, `ui`, `ui_nginx` (+ supporting DB/redis/minio containers) |
| **Analytics Server** | Search, reporting, and data sync | `docker-compose-analytics.yml` | `search_server`, `report_server`, `data_sync_service` (+ supporting Elasticsearch/Redis/ArangoDB-replica containers) |

Both servers run **independent Docker Compose stacks** on **independent
Docker networks** named `ingenium`. They communicate over the network via
`extra_hosts` entries (`ING_HOST`/`ING_IP`, `ING_ANALYTICS_HOST`/`ING_ANALYTICS_IP`)
rather than a shared overlay network, since they are expected to live on
separate VMs.

## Component Map

```
Main Server VM                          Analytics Server VM
────────────────                        ────────────────────
ui_nginx  (TLS terminator, :443)        analytics_nginx (TLS terminator, :443)
  ├─ ui                                   ├─ search_server
  ├─ core_server                          ├─ report_server
  ├─ auth_service ─ auth_service_mysql     └─ data_sync_service
  │               └ auth_service_redis         └─ arangodb_archive_replica
  ├─ archive_ing ─ arangodb_archive            └─ elasticsearch_analytics
  ├─ exec_server ─ exec_redis              report_service_redis
  ├─ execution_monitor
  ├─ dict_service ─ arangodb_dict_service
  └─ fileservering (Minio, S3-compatible)
```

Every container carries the label `io.ingenium.deployment=true`, which is how
the wizard's cleanup/status/restart operations discover "which containers
belong to this system" without hardcoding a container name list.

## Tooling Layer

| Script | Purpose | Typical invocation |
|---|---|---|
| `run.sh` | Bootstraps the Python venv, installs deps, launches the wizard | `./run.sh` |
| `ingenium.py` | Interactive menu wrapping every other script | `./ingenium.py` |
| `clone_repos.py` | Clones/updates service repos into `git_repos/` | `./clone_repos.py --repo all --tag r14_3_1` |
| `build_images.py` | Builds Docker images locally from `git_repos/` via `docker-compose-build.yml` | `./build_images.py --repo all --tag r14_3_1` |
| `setup_instance.py` | Creates/updates a deployment instance from `project_instance_template/` | `./setup_instance.py --create my_project` |
| `run_ing.sh` / `run_ing_analytics.sh` | Sources an instance's env/secrets and runs `docker compose up` for the relevant server | `./run_ing.sh -i my_project -l splunk ui_nginx` |

Each script is independently runnable via CLI flags — the wizard (`ingenium.py`)
is a convenience layer, not a requirement.

## Instance Lifecycle

An **instance** is a named deployment configuration (e.g. `my_project`),
represented as a directory containing `ing_envs.sh`, `ing_secrets.sh`, and
SSL/nginx assets. Multiple instances can coexist side-by-side in the same
`opensource_deployment3/` directory (e.g. `staging/`, `production/`).

```
project_instance_template/   (source of truth, never edited directly)
        │
        │  setup_instance.py --create <name>
        ▼
<instance_name>/
  ├── ing_envs.sh            # non-secret configuration (generated from template)
  ├── ing_secrets.sh         # generated secrets (RSA keys, DB passwords, AWS creds)
  ├── ssl/                  # user-supplied cert + key for Main Server nginx
  ├── ssl_analytics/         # user-supplied cert + key for Analytics Server nginx
  └── nginx_analytics_conf/  # nginx reverse-proxy config for Analytics Server
```

Steps performed by `setup_instance.py --create`:

1. Copy `project_instance_template/` → `<instance_name>/`.
2. Prompt for every `{{PLACEHOLDER}}` used in `ing_envs.sh` (server URLs, AWS
   region, LDAP/SMTP/RSA config, PDF/UI branding, command string format, etc.)
   and perform a literal string substitution.
3. Auto-generate all secrets in `ing_secrets.sh` (RSA keypairs, random DB
   passwords, CSRF secret, AWS placeholder creds) via `generate_secrets()`.
4. Validate infrastructure prerequisites (Docker network, `/data` directories,
   SSL certs, built images) and print a readiness summary.

**Both servers must have byte-identical copies** of `ing_envs.sh` and
`ing_secrets.sh` for the given instance — the same instance directory is
expected to be `scp`'d to both VMs.

## Configuration System

Configuration flows through three layers, from most to least sensitive:

1. **`ing_secrets.sh`** — auto-generated, gitignored, never templated with
   placeholders that need manual editing (values are randomly generated at
   creation time). Contains RSA keys, DB passwords, AWS credentials, CSRF
   secret, Splunk token.
2. **`ing_envs.sh`** — non-secret but instance-specific configuration
   (hostnames, IPs, feature flags, branding strings, image tags). Generated
   from `project_instance_template/ing_envs.sh` by literal `{{KEY}}` →
   `value` substitution in `setup_instance.py`.
3. **`docker-compose*.yml`** — static service topology; reads all runtime
   values via `${VAR}` interpolation from the two files above (sourced by
   `run_ing.sh`/`run_ing_analytics.sh` before invoking `docker compose`).

Any `{{PLACEHOLDER}}` present in `ing_envs.sh` **must** have a corresponding
prompt in `setup_instance.py`'s `prompt_for_config()`, otherwise it will be
left un-substituted in generated instances. See [`Configuration.md`](./Configuration.md)
for the `CMD_STRING_FORMAT` mini-language specifically.

## Docker Compose Layering

Compose files are combined via `-f` flags rather than duplicated:

| Base file | Overlay (choose one) | Purpose |
|---|---|---|
| `docker-compose.yml` | `docker-compose-splunk.yml` | Production logging (Splunk HEC via `${SPLUNK_URL}`) |
| `docker-compose.yml` | `docker-compose-local.yml` | Development logging (bounded local log files) |
| `docker-compose-analytics.yml` | `docker-compose-splunk-analytics.yml` | Production logging for Analytics Server |
| `docker-compose-analytics.yml` | `docker-compose-local-analytics.yml` | Development logging for Analytics Server |
| `docker-compose-build.yml` | *(build only, not deployed)* | Build contexts consumed by `build_images.py` |

`run_ing.sh -l splunk|local` and `run_ing_analytics.sh -l splunk|local` select
the overlay automatically.

## Networking Model

- Each server runs its own bridge network named `ingenium` (MTU configurable
  via `${MTU}`, default `1400` for OpenShift-style environments).
- Cross-server name resolution is handled by static `extra_hosts` entries —
  **not** DNS — because the two servers do not share a network.
- `ui_nginx` (Main) and `analytics_nginx` (Analytics) are the only containers
  with published host ports (`443`); every other service is reachable only
  from within its own compose network. Deploying the nginx service starts
  every dependency automatically via `depends_on`.

## Secrets & Security Model

- `ing_secrets.sh` is **never** committed — it's generated per-instance and
  excluded via `.gitignore` at the instance-directory level (the file itself
  ships only as `ing_secrets.sh.template` with empty values).
- RSA keypairs (`PRIVATE_PEM`/`PUBLIC_PEM`, `EXEC_VENUE_PRIVATE_PEM`/`EXEC_VENUE_PUBLIC_PEM`)
  are generated locally via `openssl` — no key material ever leaves the host
  running the wizard.
- Random secrets (DB root passwords, CSRF secret, test user credentials) use
  Python's `secrets` module (cryptographically secure), not `random`.
- LDAP/RSA-MFA integration is optional — leaving those fields blank during
  setup disables that auth path without breaking the rest of the stack
  (`AUTH_METHOD=password` is the default).

## Image Build & Tagging

Images are tagged using one of three patterns (see `build_images.py`):

- **Release tag**: `--tag r14_3_1` → `ingenium/<service>:r14_3_1`
- **Branch build**: `--branch devel` → `ingenium/<service>:devel-<short-hash>`
  (commit hash appended automatically so every build is traceable)
- **Namespaced build**: `--namespace hotfix --tag r14_3_1` →
  `ingenium/<service>:hotfix-r14_3_1` (useful for parallel test builds)

All Ingenium-authored services share a **single `RTAG`** value in
`ing_envs.sh` (as opposed to per-service tags) — bumping the version for a
deployment instance is a one-line change.

Third-party images (MySQL, Redis, ArangoDB, Elasticsearch, Minio, Nginx) are
pinned to specific upstream versions in `project_instance_template/ing_envs.sh`
and pulled directly from their public registries — they are never built
locally.

## Read Replica / Analytics Sync

The Analytics Server does not talk to the Main Server's primary database
directly for search/report queries. Instead:

1. `arangodb_archive_replica` on the Analytics Server replicates the Main
   Server's `arangodb_archive` database using ArangoDB's built-in
   master/replica replication (see the "Setting up the Read Replica" section
   of the main `README.md` for the exact `arangosh` commands).
2. `data_sync_service` watches the replica and pushes documents into
   `elasticsearch_analytics` for full-text search.
3. `search_server` and `report_server` query Elasticsearch/the replica —
   never the Main Server's primary DB — keeping analytics workloads isolated
   from transactional load.

This must be set up **once per instance**, before deploying the rest of the
Analytics stack, and the initial full sync should complete before deploying
`search_server`/`report_server`/`data_sync_service`.

## Extending the System

- **Adding a new microservice**: add an entry to `config.py`'s `GIT_REPOS`,
  add a build stage in `docker-compose-build.yml`, add a runtime service
  block in the relevant `docker-compose*.yml`, and add its image name to the
  `REQUIRED_SERVICES`-style list in `setup_instance.py`'s readiness checks.
- **Adding a new configuration field**: add `{{FIELD}}` to
  `project_instance_template/ing_envs.sh`, add a matching prompt (and, if the
  wizard supports editing existing instances, a regex pattern in
  `load_instance_config()`) in `setup_instance.py`.
- **Changing the container label**: the label used for bulk
  status/cleanup/restart operations (`io.ingenium.deployment`) is defined in
  every `docker-compose*.yml` service block and referenced by `ingenium.py`'s
  `docker ps --filter label=...` calls — both must be kept in sync if changed.

## Design Rationale

| Decision | Rationale |
|---|---|
| Build images on the target VM, not in CI | Removes the CI/registry as a dependency and a security surface — no credentials to push/pull images |
| Single `RTAG` for all services | Simplifies version bumps and avoids "which service is on which tag" drift |
| Template + placeholder substitution instead of a templating engine | Zero extra dependencies; trivially auditable (`grep '{{' ing_envs.sh`) |
| Docker label for container discovery | Decouples tooling from a hardcoded container name list; new services are automatically covered |
| Two independent compose stacks instead of one combined stack | Matches the real two-VM physical topology; avoids a single point of failure spanning both roles |
