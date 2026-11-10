# Instance Template

This directory serves as a template for creating new Ingenium deployment instances.

## Structure

```
project_instance_template/
├── ing_envs.sh                     # Environment configuration with placeholders
├── ing_secrets.sh.template         # Secrets template (to be filled by user)
├── ssl/                            # Main server SSL certificates (user provides)
├── ssl_analytics/                  # Analytics server SSL certificates (user provides)
└── nginx_analytics_conf/           # Optional nginx configuration for analytics
```

## Usage

**Do not modify this template directly.** Instead, use the setup wizard:

```bash
./ingenium.py
# Select: "Setup Instance"
```

The wizard will:
1. Copy this template to `opensource_deployment3/<instance_name>/`
2. Replace all placeholders with your values
3. Guide you through remaining setup steps

## Placeholders

The following placeholders in `ing_envs.sh` will be replaced during setup:

### Required
- `{{INSTANCE_NAME}}` - Instance identifier (e.g., "my_project")
- `{{RTAG}}` - Version tag (e.g., "r14_3_1")
- `{{ING_MAIN_SERVER}}` - Main server URL (e.g., "https://ingenium-myproject.example.com")
- `{{ING_ANALYTICS_SERVER}}` - Analytics server URL (e.g., "https://ingenium-myproject-analytics.example.com")

### Project Details
- `{{APPLICATION_TITLE}}` - UI title (e.g., "MyProject Ingenium")
- `{{APPLICATION_ACRONYM}}` - UI acronym (e.g., "MyProject")
- `{{PROCEDURE_ID_PREFIX}}` - Procedure ID prefix (e.g., "myproject-procedure-")
- `{{EXECUTION_ID_PREFIX}}` - Execution ID prefix (e.g., "myproject-ingenium-")

### AWS Configuration
- `{{AWS_DEFAULT_REGION}}` - AWS region (default: "us-east-1")
- `{{MEDIA_BUCKET}}` - S3 bucket name (e.g., "ingenium-media-myproject")

### Network Hosts
- `{{ING_HOST}}` - Main server hostname
- `{{ING_IP}}` - Main server IP
- `{{ING_ANALYTICS_HOST}}` - Analytics server hostname
- `{{ING_ANALYTICS_IP}}` - Analytics server IP
- `{{VENUE_HOST_1}}`, `{{VENUE_IP_1}}` - Optional venue host 1
- `{{VENUE_HOST_2}}`, `{{VENUE_IP_2}}` - Optional venue host 2

### Optional Customization
- `{{PDF_CUSTOM_HEADER}}` - Custom PDF header (HTML/CSS)
- `{{PDF_CUSTOM_FOOTER}}` - Custom PDF footer (HTML/CSS)
- `{{UI_CUSTOM_FOOTER}}` - Custom UI footer (HTML/CSS)
- `{{FROALA_KEY}}` - License key for the Froala WYSIWYG editor (third-party library). Can be left as an empty string. **Froala is commercial software** - review Froala's Terms of Service and licensing terms yourself at https://froala.com before deciding whether a paid license is required for your use case.

## Image Sourcing Approach

### Local Images
This template uses **locally-built images** with the `ingenium/` prefix:

```bash
# Local images (built by opensource_deployment3)
export UI_IMAGE=ingenium/ui:${RTAG}
export CORE_SERVER_IMAGE=ingenium/core_server:${RTAG}
```

Instead of pulling pre-built images from a private registry:
```bash
# Alternative approach (NOT used here)
export UI_IMAGE=your-registry.example.com/ingenium/ui:${RTAG}
```

### Third-party images
Third-party images (MySQL, Redis, ArangoDB, Elasticsearch, Minio) are pulled directly from their public registries (see `project_instance_template/ing_envs.sh`).

### Single Version Tag
All Ingenium services share a single `RTAG` value:

```bash
export RTAG=r14_3_1
export UI_IMAGE=ingenium/ui:${RTAG}
export CORE_SERVER_IMAGE=ingenium/core_server:${RTAG}
```

**Not** a per-service tag pattern:
```bash
# Per-service tag approach (NOT used here)
export UI_IMAGE=your-registry.example.com/ingenium/ui:${UI_TAG}
export CORE_SERVER_IMAGE=your-registry.example.com/ingenium/core_server:${CORE_TAG}
```

## Manual Setup (Advanced)

If you prefer manual setup without the wizard:

1. Copy this template:
   ```bash
   cp -r opensource_deployment3/project_instance_template opensource_deployment3/my_instance
   ```

2. Edit `opensource_deployment3/my_instance/ing_envs.sh`:
   - Replace all `{{PLACEHOLDERS}}` with actual values

3. Copy and fill secrets:
   ```bash
   cp opensource_deployment3/my_instance/ing_secrets.sh.template opensource_deployment3/my_instance/ing_secrets.sh
   # Edit ing_secrets.sh with your secret values
   ```

4. Add SSL certificates:
   ```bash
   # Place certificates in:
   opensource_deployment3/my_instance/ssl/ing_https.crt
   opensource_deployment3/my_instance/ssl/ing_https.key
   opensource_deployment3/my_instance/ssl_analytics/ing_https.crt
   opensource_deployment3/my_instance/ssl_analytics/ing_https.key
   ```

5. Follow infrastructure setup from the main `README.md`:
   - Create Docker network
   - Create `/data` directories
   - Set permissions

## See Also

- `../README.md` - Full deployment guide
