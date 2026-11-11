# Ingenium Deployment Toolkit (Open Source Edition)

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.6+](https://img.shields.io/badge/python-3.6%2B-blue.svg)](https://www.python.org/downloads/)
[![Docker Compose](https://img.shields.io/badge/docker-compose-2496ED.svg?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#contributing)
[![Docs](https://img.shields.io/badge/docs-Architecture.md-informational.svg)](docs/Architecture.md)

A self-contained, Python-based deployment system for Ingenium.

> **⚠️ Important:** This system does **NOT** require a CI server or a container image registry. All builds happen on your server VMs (Main/Analytics), and images stay on those VMs. No pushing, no external dependencies!
> 
> **💡 Deployment Model:** This wizard runs ON your Main and Analytics server VMs, not on a local development machine. SSH into each server to run the wizard.

> **📖 Deep dive:** For system architecture, the instance lifecycle, networking model, and design rationale, see [`docs/Architecture.md`](docs/Architecture.md).

## Overview

This system allows you to:
1. **Clone repositories** - Get source code for all Ingenium services on server VM
2. **Build Docker images** - Build images on server VM using docker-compose (no CI server or image registry required)
3. **Setup deployment instances** - Create project-specific configurations with auto-generated secrets
4. **Create data directories** - Interactive guide for setting up /data directories on each server VM
5. **Check setup status** - Verify instance readiness (configs, SSL, images) before deployment
6. **Deploy services** - Start Ingenium services with Splunk or local logging
7. **Restart services** - Quick restart (cleanup + redeploy) in one step
8. **Stop/Cleanup services** - Stop running services and clean up containers
9. **Store images on server** - Images stay on your server VM (no pushing to registries)

## Quick Start

### 1. Setup Environment

```bash
# SSH into your Main or Analytics Server VM first
ssh user@main-server-vm

# Navigate to opensource_deployment3 directory
cd /path/to/ingenium-dep/opensource_deployment3

# Run the setup script (creates venv, installs dependencies, makes scripts executable)
./run.sh
```

### 2. Clone Repositories

**Interactive Mode:**
```bash
./run.sh
# Main menu options (grouped):
#
# ─── BUILD & DEPLOY ───
#   📥 Clone/Update Repositories  — fetch code & tags
#   🔨 Build Docker Images        — build from source
#   ⚙️  Configure Instance         — new instance or update RTAG
#   🚀 Deploy Services            — start containers
#
# ─── INSTANCE SETUP (one-time) ───
#   📂 Create Data Directories    — /data dirs on server VMs
#   🔍 Check Setup Status         — verify instance config
#
# ─── OPERATIONS ───
#   🔄 Restart Services           — stop + redeploy
#   🛑 Stop/Cleanup Services      — remove containers
#   📊 Show Repository Status     — branches & tags info
#   ❌ Exit
```

**Command Line Mode:**
```bash
# Clone all repositories at a specific release tag
./clone_repos.py --repo all --tag r14_3_1

# Clone single repository
./clone_repos.py --repo ui --branch main

# Clone to custom location
./clone_repos.py --repo all --tag r14_3_1 --repos-path /path/to/repos
```

### 3. Build Docker Images

**Interactive Mode (Recommended):**
```bash
./run.sh
# Choose "Build Docker Images"
# Select repositories:
#   - All repositories
#   - Main Server (8 services: auth, archive, exec, monitor, core, dict, ui, ui_nginx)
#   - Analytics Server (3 services: search, report, data_sync)
#   - Individual repositories
# Select tag/branch and options
# Wizard guides you through the process
```

**Command Line Mode:**
```bash
./build_images.py --repo all --tag r14_3_1
```

**Build single service:**
```bash
./build_images.py --repo ui --tag r14_3_1
./build_images.py --repo core_server --branch main
```

**Build with custom options:**
```bash
# Standard build (default: clears cache for clean build)
./build_images.py --repo all --tag r14_3_1

# Use cache to speed up builds (not recommended for releases)
./build_images.py --repo all --tag r14_3_1 --use-cache

# Build with namespace prefix (for testing/dev)
./build_images.py --repo ui --tag r14_3_1 --namespace feature-xyz

# Custom repos path
./build_images.py --repo all --tag r14_3_1 --repos-path /custom/path/git_repos

# Note: Default behavior clears cache for clean, reproducible builds
# Note: Images stay local on VM - no pushing to registry
```

### 4. Setup Deployment Instance

**Interactive Mode (Recommended):**
```bash
./run.sh
# Choose "⚙️  Configure Instance"
# Or run directly:
./setup_instance.py
```

**The wizard will:**
1. Create new instance or update existing one
2. Prompt for configuration (RTAG, URLs, project details, AWS config, etc.)
3. Copy `project_instance_template/` to `<instance_name>/`
4. Replace placeholders in `ing_envs.sh` with your values
5. Create directory structure (ssl/, ssl_analytics/, nginx_analytics_conf/)
6. Validate infrastructure (Docker network, /data directories, SSL, images)
7. Display summary and next steps

**Command Line Mode:**
```bash
# Create new instance
./setup_instance.py --create my_project

# Update existing instance
./setup_instance.py --update my_project
```

**What gets created:**
```
opensource_deployment3/
└── my_project/
    ├── ing_envs.sh                      # Generated config (uses local images)
    ├── ing_secrets.sh                   # Auto-generated secrets (RSA keys, passwords, AWS)
    ├── ssl/
    │   ├── README.md
    │   ├── ing_https.crt                # User provides
    │   └── ing_https.key                # User provides
    ├── ssl_analytics/
    │   ├── README.md
    │   ├── ing_https.crt                # User provides
    │   └── ing_https.key                # User provides
    └── nginx_analytics_conf/
        └── ingenium-analytics-https.conf
```

**Next Steps After Setup:**
1. Review `<instance>/ing_secrets.sh` (auto-generated - replace AWS credentials if using real S3)
2. **⚠️ CRITICAL: Copy configuration files to BOTH servers**
   - Both `ing_envs.sh` and `ing_secrets.sh` must be IDENTICAL on Main and Analytics VMs
   - `scp <instance>/ing_envs.sh <server>:<instance>/`
   - `scp <instance>/ing_secrets.sh <server>:<instance>/`
3. **Create data directories on target servers** (see section 5 below)
4. Add SSL certificates to `<instance>/ssl/` and `<instance>/ssl_analytics/`
5. Build Docker images if not already built (see section 3 below)
6. Deploy services (see section 7 below)
7. Use Restart (section 8) to quickly redeploy after changes
8. Use Stop/Cleanup (section 9) before upgrading versions

**Key Design Points:**
- Uses **local images** (`ingenium/ui:r14_3_1`) built directly on the server VM
- Single `RTAG` for all services (all Ingenium images share one version tag)
- Template-based approach (copy + customize, not manual creation)
- Automated validation and infrastructure setup

### 5. Create Data Directories on Server VMs

**Interactive Mode (Recommended - run on each server VM):**
```bash
# SSH into Main or Analytics Server VM, then:
./run.sh
# Choose "📂 Create Data Directories"
# Select: Main Server, Analytics Server, or Both (show all) — pick your current VM
# View the commands needed
# Optional: Let wizard create them automatically (requires sudo)
```

**What it does:**
- Shows server-specific directory creation commands
- Provides verification steps
- Explains directory purposes
- **Optional: Create directories automatically with sudo** (only when a single server is selected, not "Both")
- Note: Run this wizard ON each server VM, not locally

**Main Server directories:**
```bash
# SSH into Main Server VM, then:
mkdir -p /data && cd /data
mkdir auth && chmod 777 auth
mkdir arangodb && chmod 777 arangodb
mkdir arangodb_dict_service && chmod 777 arangodb_dict_service
mkdir file_server && chmod 777 file_server
```

**Analytics Server directories:**
```bash
# SSH into Analytics Server VM, then:
mkdir -p /data && cd /data
mkdir arangodb && chmod 777 arangodb
mkdir -p elasticsearch/data && chmod 777 elasticsearch elasticsearch/data
```

**Important:**
- These directories must be created on the **target server VMs**, not your local machine
- Both servers need `/data/arangodb` (Main=archive, Analytics=replica)
- All directories require 777 permissions for Docker containers
- Elasticsearch needs a nested `data/` subdirectory

### 6. Check Setup Status

**Interactive Mode (run on each server VM):**
```bash
# SSH into Main or Analytics Server VM, then:
./run.sh
# Choose "🔍 Check Setup Status"
# Select instance to check
# Select: Main Server VM or Analytics Server VM (based on which VM you're on)
# View comprehensive readiness report
```

**What it checks:**
- ✓ Configuration files (`ing_envs.sh`, `ing_secrets.sh`)
- ✓ SSL certificates (only checks relevant server: Main SSL on Main Server, Analytics SSL on Analytics Server)
- ✓ Data directories (checked based on server type: Main Server or Analytics Server)
- ✓ Docker images (only checks images needed for that server: 8 images for Main, 3 images for Analytics)

**Example Output (from Main Server VM):**
```
🔍 CHECK SETUP STATUS
======================================================================

Instance: my_project
RTAG: r14_3_1
Location: /path/to/opensource_deployment3/my_project
Machine: Main Server VM

📄 Configuration Files:
  ✓ ing_envs.sh exists
  ✓ ing_secrets.sh exists and appears configured

  ⚠️  IMPORTANT: ing_envs.sh and ing_secrets.sh must be identical on both servers

🔐 SSL Certificates:
  ✓ Main Server SSL (crt + key)

� Data Directories:
  Checking Main Server directories...
  ✓ /data/auth
  ✓ /data/arangodb
  ✓ /data/arangodb_dict_service
  ✓ /data/file_server
  ✓ All Main Server directories exist

🐳 Docker Images:
  Checking Main Server images...
  Found: 8/8 required images
  ✓ All required images built for Main Server VM

======================================================================
📊 SETUP COMPLETION SUMMARY:
======================================================================

✅ Overall: 6/6 checks passed (100%)

Checklist:
  [✓] Configuration files
  [✓] Secrets configured
  [✓] SSL certificates (Main Server)
  [✓] Data directories (Main Server VM)
  [✓] Docker images built

🎉 Instance 'my_project' is ready for deployment!
```

**Server Types:**
- **Main Server VM**: 
  - Data directories: auth, arangodb, arangodb_dict_service, file_server
  - Docker images: auth_service, archive_ing, exec_server, execution_monitor, core_server, dict_service, ui, ui_nginx (8 images)
- **Analytics Server VM**: 
  - Data directories: arangodb, elasticsearch, elasticsearch/data
  - Docker images: search_server, report_server, data_sync_service (3 images)

**Important Notes:**
- ⚠️ **Configuration files (`ing_envs.sh` and `ing_secrets.sh`) must be IDENTICAL on both Main and Analytics servers**
- Only SSL certificates and data directories differ between servers

**Use this to:**
- Verify setup completion before deployment
- Check data directories on the correct server
- Identify what's missing
- Get clear next steps for incomplete items
- Confirm configuration file consistency

### 7. Deploy Services

**Interactive Mode (Recommended - run on each server VM):**
```bash
# SSH into Main or Analytics Server VM, then:
./run.sh
# Choose "🚀 Deploy Services"
# Select instance
# Select: Main Server or Analytics Server
# Select log driver: Splunk (production) or Local (development)
# Select services:
#   - All services (deploys nginx which starts everything via dependencies)
#   - Individual services (for specific service restart/deployment)
# Confirm deployment
```

**Command Line Mode:**

**Main Server:**
```bash
# Deploy all Main Server services with Splunk logging
# Note: ui_nginx starts ALL services via docker-compose dependencies
./run_ing.sh -i my_project -l splunk ui_nginx

# Deploy specific service
./run_ing.sh -i my_project -l splunk core_server

# Deploy with local logging (development)
./run_ing.sh -i my_project -l local ui_nginx
```

**Analytics Server:**
```bash
# Deploy all Analytics services with Splunk logging
# Note: analytics_nginx starts ALL services via docker-compose dependencies
./run_ing_analytics.sh -i my_project -l splunk analytics_nginx

# Deploy specific service
./run_ing_analytics.sh -i my_project -l splunk search_server

# Deploy with local logging (development)
./run_ing_analytics.sh -i my_project -l local analytics_nginx
```

**What it does:**
- **Safety Check**: Warns if containers are already running (prevents conflicts)
- Sources instance configuration (`ing_envs.sh`, `ing_secrets.sh`)
- Sets up SSL directories
- Runs docker-compose with appropriate compose files
- Starts selected services in detached mode
- Server-aware: Main uses `docker-compose.yml`, Analytics uses `docker-compose-analytics.yml`
- Log driver options: Splunk (production) or Local (development)
- **Dependency Magic**: Deploy `ui_nginx` or `analytics_nginx` to start ALL services automatically
  - Docker Compose `depends_on` ensures all required services start in correct order
  - No need to list every service name - the nginx service pulls them all in

**Safety Features:**
- Checks for running Ingenium containers before deployment
- Warns about potential conflicts (container names, ports)
- Recommends using "🔄 Restart Services" or "🛑 Stop/Cleanup" first
- Allows override if you really want to proceed (not recommended)

**Main Server Services:**
- `ui_nginx` - **⭐ Deploy this to start ALL Main Server services** (NGINX proxy + dependencies)
- `auth_service` - Authentication service
- `archive_ing` - Archive ingestion
- `exec_server` - Execution server
- `execution_monitor` - Monitors executions
- `core_server` - Core API server
- `dict_service` - Dictionary service
- `ui` - User interface

**Analytics Server Services:**
- `analytics_nginx` - **⭐ Deploy this to start ALL Analytics services** (NGINX proxy + dependencies)
- `search_server` - Search API
- `report_server` - Reporting service
- `data_sync_service` - Data synchronization

**Example with running container warning:**
```
🚀 DEPLOY INGENIUM SERVICES
======================================================================

✓ Instance: my_project
  Location: /path/to/opensource_deployment3/my_project

======================================================================
CHECKING FOR RUNNING SERVICES...
======================================================================

⚠️  WARNING: Ingenium containers are already running!

NAMES           STATUS
ui_nginx        Up 10 minutes
ui              Up 10 minutes
core_server     Up 10 minutes
...

======================================================================
⚠️  DEPLOYMENT CONFLICT WARNING
======================================================================

Running containers detected. Deploying now may cause:
  • Container name conflicts
  • Port conflicts
  • Deployment failures

💡 RECOMMENDED ACTION:
   Use '🔄 Restart Services' to cleanly restart
   OR use '🛑 Stop/Cleanup Services' before deploying
======================================================================

? Do you want to proceed with deployment anyway? (Not recommended) (y/N) n

✓ Deployment cancelled. Use Restart or Stop/Cleanup first.
```

**Check Deployment Status:**
```bash
# View running containers
docker ps

# View logs
docker logs <container_name>

# Follow logs in real-time
docker logs -f <container_name>

# Stop services
docker-compose down

# Restart specific service
docker-compose restart <service_name>
```

### 8. Restart Services

**Interactive Mode (Recommended - run on each server VM):**
```bash
# SSH into Main or Analytics Server VM, then:
./run.sh
# Choose "🔄 Restart Services"
# Select instance
# Select: Main Server or Analytics Server
# Select log driver: Splunk (production) or Local (development)
# Select services: All or individual
# Confirm restart
```

**What it does:**
1. **Shows current status**
   - Lists all running Ingenium containers

2. **Service selection**
   - **All services**: Full restart - stops ALL containers, then redeploys
   - **Individual service**: Restarts only that service, others keep running

3. **Smart restart behavior**:
   - **All services selected**:
     - Step 1: Runs `docker stop ... && docker rm -f ...` (cleans ALL containers)
     - Step 2: Redeploys all services via nginx
   - **Individual service selected**:
     - Runs deployment script for just that service (e.g., `./run_ing.sh -i <instance> -l splunk core_server`)
     - Other services remain untouched and running

4. **Why use this**:
   - **All services**: Apply configuration changes, version upgrades, clean state
   - **Individual service**: Quick restart after rebuilding one service image
   - Restart specific service without disrupting others
   - Faster than Stop → Deploy for single service updates

**Example flow (All services):**
```
🔄 RESTART INGENIUM SERVICES
======================================================================

This will:
  1. Stop and remove all running Ingenium containers
  2. Redeploy services with your selected configuration
======================================================================

📊 Currently Running Containers:

NAMES           STATUS
ui_nginx        Up 10 minutes
ui              Up 10 minutes
core_server     Up 10 minutes
...

======================================================================
? Select instance to restart: my_project
? Which server are you restarting? Main Server
? Select log driver: Splunk (production)
? Which service(s) to restart? 🌟 All services

======================================================================
RESTART SUMMARY:
======================================================================
  Instance:    my_project
  Server:      Main Server
  Log Driver:  splunk
  Service:     ui_nginx (starts all services via dependencies)

  ⚠️  Will stop and remove all running containers before redeploying
======================================================================

? Proceed with restart? (Y/n) y

======================================================================
STEP 1: CLEANING UP ALL CONTAINERS...
======================================================================

Running: docker stop ... && docker rm -f ...

✓ Cleanup complete

======================================================================
STEP 2: DEPLOYING SERVICES...
======================================================================

Running: ./run_ing.sh -i my_project -l splunk ui_nginx

[deployment output...]

======================================================================
✅ RESTART SUCCESSFUL!
======================================================================

Services have been restarted for instance 'my_project'
======================================================================
```

**Example flow (Individual service):**
```
🔄 RESTART INGENIUM SERVICES
======================================================================

📊 Currently Running Containers:

NAMES           STATUS
ui_nginx        Up 10 minutes
ui              Up 10 minutes
core_server     Up 10 minutes
dict_service    Up 10 minutes
...

======================================================================
? Select instance to restart: my_project
? Which server are you restarting? Main Server
? Select log driver: Splunk (production)
? Which service(s) to restart?   dict_service

======================================================================
RESTART SUMMARY:
======================================================================
  Instance:    my_project
  Server:      Main Server
  Log Driver:  splunk
  Service:     dict_service

  ℹ️  Will restart only this service (others remain running)
======================================================================

? Proceed with restart? (Y/n) y

======================================================================
RESTARTING SERVICE...
======================================================================

Running: ./run_ing.sh -i my_project -l splunk dict_service

[deployment output...]

======================================================================
✅ RESTART SUCCESSFUL!
======================================================================

Service 'dict_service' has been restarted
Other services remain running
======================================================================
```

**When to use:**
- **After code changes**: Rebuild images → Restart all services
- **Configuration updates**: Modified ing_envs.sh → Restart to apply
- **Troubleshooting**: Quick way to get clean state and redeploy
- **Individual service restart**: Updated one service → Restart just that service
- **Daily operations**: Faster than separate stop + deploy

**Manual equivalent:**
```bash
# What "Restart All" does automatically:
docker stop $(docker ps -a -q --filter label=io.ingenium.deployment=true) && \
docker rm -f $(docker ps -a -q --filter label=io.ingenium.deployment=true) && \
./run_ing.sh -i my_project -l splunk ui_nginx

# What "Restart Individual" does (e.g., core_server):
# Note: No cleanup - just redeploys the single service while others keep running
./run_ing.sh -i my_project -l splunk core_server
```

### 9. Stop and Cleanup Services

**Interactive Mode (Recommended - run on each server VM):**
```bash
# SSH into Main or Analytics Server VM, then:
./run.sh
# Choose "🛑 Stop/Cleanup Services"
# View currently running containers
# View stopped containers
# Review cleanup actions
# Confirm cleanup (optionally remove volumes)
```

**What it does:**
1. **Shows current status**
   - Lists all running Ingenium containers
   - Lists all stopped Ingenium containers
   - Shows what will be cleaned

2. **Cleanup action** (after confirmation):
   - Stops all running Ingenium containers
   - Removes all Ingenium containers (running and stopped)
   - Uses single command: `docker stop $(docker ps -a -q --filter label=io.ingenium.deployment=true) && docker rm -f $(docker ps -a -q --filter label=io.ingenium.deployment=true)`

3. **Safety features**:
   - Shows exactly what's running before cleanup
   - Requires confirmation before proceeding
   - Only affects containers with `io.ingenium.deployment=true` label

**When to use:**
- **Before redeployment**: Clean up old containers to avoid conflicts
- **Version upgrades**: Remove old version containers before deploying new version
- **Troubleshooting**: Clean state to fix deployment issues
- **Server maintenance**: Stop all services for maintenance window

**Example output:**
```
🛑 STOP AND CLEANUP SERVICES
======================================================================

📊 Currently Running Containers:

NAMES                STATUS              IMAGE
ui_nginx            Up 5 minutes        ingenium/ui_nginx:r14_3_1
ui                  Up 5 minutes        ingenium/ui:r14_3_1
core_server         Up 5 minutes        ingenium/core_server:r14_3_1
auth_service        Up 5 minutes        ingenium/auth_service:r14_3_1
...

✓ Found 8 running Ingenium container(s)

📦 Stopped Ingenium Containers:

  No stopped Ingenium containers found.

======================================================================
🧹 CLEANUP ACTION:
======================================================================

This will:
  • Stop all running Ingenium containers
  • Remove all Ingenium containers (running and stopped)

⚠️  This will stop ALL Ingenium services on this server!
======================================================================

? Proceed with cleanup? (y/N) y

======================================================================
CLEANING UP...
======================================================================

Running: docker stop $(docker ps -a -q --filter label=io.ingenium.deployment=true) && docker rm -f $(docker ps -a -q --filter label=io.ingenium.deployment=true)

======================================================================
✅ CLEANUP COMPLETE!
======================================================================

All Ingenium services have been stopped and removed.

To verify:
  $ docker ps
  $ docker ps -a

To redeploy:
  Use '🚀 Deploy Services' from main menu
======================================================================
```

**Manual cleanup command** (if needed):
```bash
# Stop and remove all Ingenium containers
docker stop $(docker ps -a -q --filter label=io.ingenium.deployment=true) && docker rm -f $(docker ps -a -q --filter label=io.ingenium.deployment=true)
```

## Setting up the Read Replica of ArangoDB

The Analytics Server runs a read replica of the Main Server's ArangoDB archive database (`arangodb_archive_replica`). This replica must be initialized **before** deploying the rest of the Analytics services (ElasticSearch, DataSyncService, SearchService).

> **⚠️ Order matters:** Complete these steps first. During replication ArangoDB performs an initial full sync — wait for it to finish before deploying the other Analytics services.

### Step 1: Start the replica and create a replication user

Deploy **only** the `arangodb_archive_replica` service on the Analytics Server:
```bash
# SSH into Analytics Server VM, then:
./run_ing_analytics.sh -i <instance_name> -l <logging_option> arangodb_archive_replica
```

Next, SSH into the **Main Server** and open an ArangoDB shell against the primary archive DB (replace the root user/password):
```bash
docker exec -it arangodb_archive arangosh \
  --server.username <your_primary_root_user> \
  --server.password <your_primary_root_password>
```

Create a replication user (replace `replication_user` and `your_replication_password` with your chosen values):
```js
var users = require("@arangodb/users");
users.save("replication_user", "your_replication_password");
users.grantDatabase("replication_user", "_system", "rw");
```

### Step 2: Configure replication on the replica

SSH into the **Analytics Server** and open an ArangoDB shell against the replica (replace the root user/password):
```bash
docker exec -it arangodb_archive_replica arangosh \
  --server.username <your_primary_root_user> \
  --server.password <your_primary_root_password>
```

Set up replication. Replace `replication_user` / `your_replication_password` with the values from Step 1, and change `endpoint` to your **Main Server** URL:
```js
db._createDatabase("ingenium");

db._useDatabase("ingenium");

var replication = require("@arangodb/replication");
replication.applier.stop();
replication.applier.forget();

var config = {
    endpoint: "ssl://ingenium-main.example.com:443",  // Change the URL to Main Server
    username: "replication_user",
    password: "your_replication_password",
    database: "ingenium",
    includeSystem: false,
    requireFromPresent: false,
    verbose: false,
    autoStart: true,
    autoResync: true
};

replication.setupReplication(config);
replication.applier.start();
replication.applier.state();
```

> **Note:** ArangoDB automatically starts the replication process. Wait for the initial sync to finish before deploying the other Analytics services.

### Step 3: Deploy the remaining Analytics services

Once the replica is ready and synced, deploy ElasticSearch, DataSyncService and SearchService:
```bash
./run_ing_analytics.sh -i <instance_name> -l <logging_option> analytics_nginx
```

## Repository to Service Mapping

| Repository | Docker Services |
|------------|----------------|
| archive | archive_ing |
| auth-service | auth_service |
| core_server | core_server |
| dict_service | dict_service |
| execution_server | exec_server |
| execution-monitor-service | execution_monitor |
| ui | ui, ui_nginx |
| report_server | report_server |
| data_sync_service | data_sync_service |
| search_server | search_server |

## Image Tagging

> **⚠️ IMPORTANT:** The `--tag` and `--branch` parameters only affect Docker image naming!  
> They do **NOT** checkout code. The build uses whatever code is currently in your `git_repos/` directory.  
> **Always run `clone_repos.py` first** to checkout the correct code version before building.

Images are tagged using the following patterns:

### With Release Tag
```bash
./build_images.py --repo ui --tag r14_3_1
# Creates: ingenium/ui:r14_3_1
#          ingenium/ui_nginx:r14_3_1
```

> **Note:** Tags may be 3-part (`r14_3_1`) or 2-part (`r15_0-rc1`). The interactive tag
> builder in the wizard makes the patch component optional to support both formats.

### With Branch (auto-includes commit hash)
```bash
./build_images.py --repo ui --branch main
# Creates: ingenium/ui:main-abc1234
#          ingenium/ui_nginx:main-abc1234
```

### With Namespace
```bash
./build_images.py --repo ui --tag r14_3_1 --namespace hotfix
# Creates: ingenium/ui:hotfix-r14_3_1
#          ingenium/ui_nginx:hotfix-r14_3_1
```

### With Registry (non-standard — not used by the wizard)
> **⚠️ Note:** The interactive wizard never pushes to a registry (images stay local on the VM). The `--registry` flag exists only for special CLI use cases.
```bash
./build_images.py --repo ui --tag r14_3_1 --registry localhost:5000
# Creates: localhost:5000/ingenium/ui:r14_3_1
#          localhost:5000/ingenium/ui_nginx:r14_3_1
# Also pushes to registry
```

## Workflow Examples

### Release Build Workflow
```bash
# 1. Clone all repos at release tag
./clone_repos.py --repo all --tag r14_3_1

# 2. Build all images
./build_images.py --repo all --tag r14_3_1

# 3. Images are now available locally:
docker images | grep ingenium
```

### Development Workflow
```bash
# 1. Clone repos on main branch
./clone_repos.py --repo all --branch main

# 2. Build images (will include commit hash)
./build_images.py --repo all --branch main

# 3. Make changes to a specific repo
cd git_repos/ui
# ... make changes ...
git commit -am "My changes"

# 4. Rebuild just that service
cd ../..
./build_images.py --repo ui --branch main
```

### Single Service Update
```bash
# Update just one service without rebuilding everything
./clone_repos.py --repo core_server --tag r14_3_2
./build_images.py --repo core_server --tag r14_3_2
```

## File Structure

```
opensource_deployment3/
├── run.sh                              # Setup script (creates venv, installs deps)
├── requirements.txt                    # Python dependencies
├── config.py                           # Repository configuration
├── ingenium.py                         # Interactive wizard (main entry point)
├── clone_repos.py                      # Repository cloning (CLI)
├── build_images.py                     # Image building (CLI)
├── setup_instance.py                   # Instance setup wizard
├── run_ing.sh                          # Main Server deployment script
├── run_ing_analytics.sh                # Analytics Server deployment script
├── docker-compose.yml                  # Main Server service definitions
├── docker-compose-analytics.yml        # Analytics Server service definitions
├── docker-compose-build.yml            # Build contexts for all services
├── docker-compose-splunk.yml           # Splunk log driver (Main Server)
├── docker-compose-splunk-analytics.yml # Splunk log driver (Analytics Server)
├── docker-compose-local.yml            # Local log driver (Main Server)
├── docker-compose-local-analytics.yml  # Local log driver (Analytics Server)
├── project_instance_template/          # Template for new deployment instances
├── git_repos/                          # Cloned repositories (gitignored)
└── README.md                           # This file
```

## Design Highlights

| Aspect | Approach |
|--------|----------|
| **Repo Cloning** | Standalone `clone_repos.py` script |
| **Image Building** | ✅ Local docker compose build |
| **Image Storage** | ✅ Local VM only (no external registry) |
| **Configuration** | Python + YAML |
| **Build Trigger** | ✅ Manual/Script (full control) |
| **Dependencies** | ✅ None beyond Docker/Git/Python (self-contained) |

## Requirements

- Python 3.6+ (compatible with the older Python versions found on deployment VMs)
- Docker and Docker Compose
- Git
- HTTPS access to github.com/OpenIngenium (the open-source repositories)

## Troubleshooting

### "Repos path does not exist"
Run `clone_repos.py` first to clone the repositories.

### "Compose file not found"
The compose files are located in the `opensource_deployment3/` directory:
- `docker-compose.yml` - Service definitions
- `docker-compose-build.yml` - Build contexts

You can specify a custom location with `--compose-dir`:
```bash
./build_images.py --repo all --tag r14_3_1 --compose-dir /path/to/compose/files
```

### "Failed to tag image"
The image might not have been built. Check the build output for errors.

### Docker permission errors
Make sure Docker daemon is running and your user has permission to run Docker commands.

## Contributing

Contributions are welcome! A few guidelines to keep in mind:

- Open an issue before starting significant work, so the change can be discussed first.
- Keep pull requests focused — one logical change per PR is easier to review.
- If you add a new `{{PLACEHOLDER}}` to `project_instance_template/ing_envs.sh`, add a
  matching prompt (and, for editable instances, an extraction pattern) in `setup_instance.py`.
  See [`docs/Architecture.md`](docs/Architecture.md#configuration-system) for details.
- Test changes against `docker compose config` before submitting (validates the compose
  files render correctly with your changes).

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
