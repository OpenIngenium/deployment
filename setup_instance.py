#!/usr/bin/env python3
"""
Setup wizard for creating new Ingenium deployment instances.

This script creates a new instance by:
1. Copying project_instance_template
2. Prompting for configuration values
3. Replacing placeholders in ing_envs.sh
4. Validating infrastructure (Docker network, data directories, SSL, images)
5. Displaying setup summary and next steps
"""

import argparse
import re
import secrets
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import questionary

import config


def run_command(cmd: List[str], cwd: Path = None, capture_output: bool = True) -> Tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        if capture_output:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            return True, result.stdout
        else:
            subprocess.run(cmd, cwd=cwd, check=True)
            return True, ""
    except subprocess.CalledProcessError as e:
        if capture_output:
            return False, e.stdout if e.stdout else str(e)
        return False, str(e)


def resolve_hostname(hostname: str) -> Optional[str]:
    """Resolve hostname to IP address. Returns None if resolution fails."""
    try:
        # Remove https:// or http:// if present
        clean_hostname = hostname.replace('https://', '').replace('http://', '')
        # Remove any path after hostname
        clean_hostname = clean_hostname.split('/')[0]
        
        # Try to resolve the hostname
        ip_address = socket.gethostbyname(clean_hostname)
        return ip_address
    except (socket.gaierror, socket.herror):
        # Signal failure so callers can warn the user instead of
        # silently baking in a bogus IP (which breaks extra_hosts).
        return None


def prompt_ip_for_host(hostname: str, existing: Optional[str] = None) -> str:
    """Resolve `hostname` and prompt the user to confirm/enter its IP.

    If DNS resolution fails, the user is notified and required to enter a
    non-empty IP (blank answers are rejected) so no bogus/empty value is
    ever written into ing_envs.sh extra_hosts.
    """
    resolved = resolve_hostname(hostname)
    if resolved is None:
        print(f"  WARNING: Could not resolve '{hostname}' via DNS.")
        return questionary.text(
            f"Enter IP address for {hostname}:",
            default=existing or "",
            validate=lambda v: True if v.strip() else "IP address is required"
        ).ask()
    return questionary.text(
        f"IP for {hostname} (resolved via DNS, verify):",
        default=existing or resolved
    ).ask()


def generate_rsa_keypair() -> Tuple[str, str]:
    """Generate RSA key pair and return (private_key, public_key) as PEM strings."""
    try:
        # Generate RSA key pair using openssl
        # Generate private key
        private_result = subprocess.run(
            ['openssl', 'genrsa', '2048'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True
        )
        private_key = private_result.stdout
        
        # Extract public key from private key
        public_result = subprocess.run(
            ['openssl', 'rsa', '-pubout'],
            input=private_key,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True
        )
        public_key = public_result.stdout
        
        return private_key, public_key
    except (subprocess.CalledProcessError, FileNotFoundError):
        # If openssl is not available, return empty strings
        return "", ""


def generate_password(length: int = 12) -> str:
    """Generate a random alphanumeric password."""
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_secrets() -> Dict[str, str]:
    """Generate all secret values for ing_secrets.sh."""
    print("\n" + "="*60)
    print("GENERATING SECRETS")
    print("="*60 + "\n")
    
    secrets_values = {}
    
    # Generate RSA key pairs
    print("Generating RSA key pairs...")
    private_pem, public_pem = generate_rsa_keypair()
    secrets_values['PRIVATE_PEM'] = private_pem
    secrets_values['PUBLIC_PEM'] = public_pem
    
    exec_private_pem, exec_public_pem = generate_rsa_keypair()
    secrets_values['EXEC_VENUE_PRIVATE_PEM'] = exec_private_pem
    secrets_values['EXEC_VENUE_PUBLIC_PEM'] = exec_public_pem
    
    if private_pem and public_pem:
        print("✓ Generated JWT RSA key pair")
    else:
        print("⚠️  Could not generate JWT keys (openssl not available)")
    
    if exec_private_pem and exec_public_pem:
        print("✓ Generated Execution Venue RSA key pair")
    else:
        print("⚠️  Could not generate Execution Venue keys (openssl not available)")
    
    # Generate passwords
    print("\nGenerating passwords...")
    secrets_values['ARANGO_ROOT_PASSWORD'] = generate_password(12)
    print("✓ Generated ArangoDB root password")
    
    secrets_values['AUTH_DB_MYSQL_ROOT_PASSWORD'] = generate_password(12)
    print("✓ Generated MySQL root password")
    
    # Prompt for test user
    print("\nTest User Configuration:")
    test_user = questionary.text(
        "Test username (for authentication testing):",
        default="test_user"
    ).ask()
    secrets_values['TEST_USER'] = test_user
    
    secrets_values['TEST_PASS'] = generate_password(12)
    print("✓ Generated test password")
    
    secrets_values['EMS_SECRET'] = generate_password(12)
    print("✓ Generated EMS secret")
    
    secrets_values['CSRF_SECRET'] = generate_password(32)
    print("✓ Generated CSRF secret")
    
    # Generate AWS credentials
    print("\nGenerating AWS credentials...")
    secrets_values['AWS_ACCESS_KEY_ID'] = generate_password(12)
    secrets_values['AWS_SECRET_ACCESS_KEY'] = generate_password(12)
    print("✓ Generated AWS access key ID and secret")
    
    # Prompt for Splunk token
    print("\nSplunk Configuration:")
    splunk_token = questionary.text(
        "Splunk Token (leave empty if not using Splunk logging):",
        default=""
    ).ask()
    secrets_values['SPLUNK_TOKEN'] = splunk_token
    
    return secrets_values


def get_existing_instances(deployments_path: Path) -> List[str]:
    """Get list of existing instance directories."""
    instances = []
    if not deployments_path.exists():
        return instances
    
    for item in deployments_path.iterdir():
        if item.is_dir() and not item.name.startswith('.') and item.name not in ['git_repos', 'project_instance_template']:
            env_file = item / "ing_envs.sh"
            if env_file.exists():
                instances.append(item.name)
    
    return sorted(instances)


def load_instance_config(instance_path: Path) -> Dict[str, str]:
    """Load configuration from existing instance's ing_envs.sh."""
    env_file = instance_path / "ing_envs.sh"
    if not env_file.exists():
        return {}
    
    config_values = {}
    content = env_file.read_text()
    
    # Extract key values using regex
    patterns = {
        'ING_INSTANCE': r'export ING_INSTANCE=(\S+)',
        'ING_MAIN_SERVER': r'export ING_MAIN_SERVER=(\S+)',
        'ING_ANALYTICS_SERVER': r'export ING_ANALYTICS_SERVER=(\S+)',
        'EMAIL_DOMAIN': r'export EMAIL_DOMAIN=(\S+)',
        'LDAP_BASE_DN': r'export LDAP_BASE_DN=(\S+)',
        'LDAP_GROUP_OBJECTCLASS': r'export LDAP_GROUP_OBJECTCLASS=(\S+)',
        'LDAP_URL': r'export LDAP_URL=(\S+)',
        'LDAP_HOST': r'export LDAP_HOST=(\S+)',
        'LDAP_IP': r'export LDAP_IP=(\S+)',
        'RSA_URL': r'export RSA_URL=(\S+)',
        'RSA_CLIENT_ID': r'export RSA_CLIENT_ID=(\S+)',
        'RSA_CLIENT_KEY': r'export RSA_CLIENT_KEY=(\S+)',
        'SMTP_HOST': r'export SMTP_HOST=(\S+)',
        'SMTP_IP': r'export SMTP_IP=(\S+)',
        'SPLUNK_URL': r'export SPLUNK_URL=(\S+)',
        'RTAG': r'export RTAG=(\S+)',
        'APPLICATION_TITLE': r'export APPLICATION_TITLE="([^"]+)"',
        'APPLICATION_ACRONYM': r'export APPLICATION_ACRONYM="([^"]+)"',
        'PROCEDURE_ID_PREFIX': r'export PROCEDURE_ID_PREFIX="([^"]+)"',
        'EXECUTION_ID_PREFIX': r'export EXECUTION_ID_PREFIX="([^"]+)"',
        'AWS_DEFAULT_REGION': r'export AWS_DEFAULT_REGION="([^"]+)"',
        'MEDIA_BUCKET': r'export MEDIA_BUCKET=(\S+)',
        'FROALA_KEY': r'export FROALA_KEY="([^"]*)"',
        'CMD_STRING_FORMAT': r'export CMD_STRING_FORMAT="([^"]*)"',
        'PDF_CUSTOM_HEADER': r'export PDF_CUSTOM_HEADER="([^"]*)"',
        'PDF_CUSTOM_FOOTER': r'export PDF_CUSTOM_FOOTER="([^"]*)"',
        'UI_CUSTOM_FOOTER': r'export UI_CUSTOM_FOOTER="([^"]*)"',
        'PDF_PROCEDURE_NOTE': r'export PDF_PROCEDURE_NOTE="([^"]*)"',
        'PDF_EXECUTION_NOTE': r'export PDF_EXECUTION_NOTE="([^"]*)"',
        'PDF_CLEANUP_ENABLED': r'export PDF_CLEANUP_ENABLED="?(\w+)"?',
        'PDF_RETENTION_DAYS': r'export PDF_RETENTION_DAYS="?(\w+)"?',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            config_values[key] = match.group(1)
    
    return config_values


def get_available_tags(repos_path: Path) -> List[str]:
    """Get available git tags from repositories."""
    tags = set()
    
    for repo_name in config.GIT_REPOS.keys():
        repo_path = repos_path / repo_name
        if not repo_path.exists():
            continue
        
        result = subprocess.run(
            ["git", "tag", "-l", "r*"],
            cwd=repo_path,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        if result.returncode == 0:
            repo_tags = result.stdout.strip().split('\n')
            tags.update([t for t in repo_tags if t])
    
    return sorted(tags, reverse=True)


def get_built_images() -> List[str]:
    """Get list of built ingenium images with tags."""
    result = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", "--filter", "reference=ingenium/*"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    if result.returncode == 0:
        return [img for img in result.stdout.strip().split('\n') if img]
    return []


def build_tag_interactive() -> str:
    """Build a tag interactively (major.minor[.patch])."""
    major = questionary.text("Major version:").ask()
    minor = questionary.text("Minor version:").ask()
    patch = questionary.text("Patch version (leave empty to skip):").ask()
    
    base = f"r{major}_{minor}"
    if patch:
        base = f"{base}_{patch}"
    return base


def prompt_for_config(mode: str, existing_config: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Prompt user for configuration values."""
    config_values = existing_config.copy() if existing_config else {}
    
    print("\n" + "="*60)
    print("INSTANCE CONFIGURATION")
    print("="*60 + "\n")
    
    # Instance name (only for new instances)
    if mode == "create":
        instance_name = questionary.text(
            "Instance name (e.g., 'my_project', 'staging'):",
            validate=lambda text: bool(re.match(r'^[a-zA-Z0-9_-]+$', text))
        ).ask()
        config_values['INSTANCE_NAME'] = instance_name
    
    # RTAG selection
    print("\nSelect RTAG version:")
    rtag_choices = [
        questionary.Choice("1. Enter manually", value="manual"),
        questionary.Choice("2. Build tag interactively (major.minor[.patch])", value="build"),
        questionary.Choice("3. Select from available git tags", value="select"),
        questionary.Choice("4. Use latest built image", value="latest"),
    ]
    
    if mode == "update" and 'RTAG' in config_values:
        rtag_choices.append(
            questionary.Choice(f"5. Keep current ({config_values['RTAG']})", value="keep")
        )
    
    rtag_choices.extend([
        questionary.Separator(),
        questionary.Choice("⬅️  Back", value="back"),
    ])
    
    rtag_choice = questionary.select("", choices=rtag_choices).ask()
    
    if rtag_choice is None or rtag_choice == "back":
        print("\n⬅️  Returning to main menu...\n")
        sys.exit(0)
    
    if rtag_choice == "manual":
        rtag = questionary.text(
            "Enter RTAG (e.g., r14_3_1):",
            default=config_values.get('RTAG', ''),
            validate=lambda text: bool(re.match(r'^r\d+_\d+_\d+$', text))
        ).ask()
        config_values['RTAG'] = rtag
    elif rtag_choice == "build":
        config_values['RTAG'] = build_tag_interactive()
    elif rtag_choice == "select":
        repos_path = Path.cwd() / "git_repos"
        tags = get_available_tags(repos_path)
        if tags:
            tag_choices = list(tags) + [questionary.Separator(), questionary.Choice("⬅️  Back", value="back")]
            rtag = questionary.select("Select tag:", choices=tag_choices).ask()
            if rtag is None or rtag == "back":
                print("\n⬅️  Returning to main menu...\n")
                sys.exit(0)
            config_values['RTAG'] = rtag
        else:
            print("⚠️  No tags found in git repositories")
            rtag = questionary.text("Enter RTAG manually:").ask()
            config_values['RTAG'] = rtag
    elif rtag_choice == "latest":
        images = get_built_images()
        if images:
            # Extract unique tags
            tags = sorted(set(img.split(':')[1] for img in images if ':' in img), reverse=True)
            if tags:
                image_tag_choices = list(tags) + [questionary.Separator(), questionary.Choice("⬅️  Back", value="back")]
                rtag = questionary.select("Select from built images:", choices=image_tag_choices).ask()
                if rtag is None or rtag == "back":
                    print("\n⬅️  Returning to main menu...\n")
                    sys.exit(0)
                config_values['RTAG'] = rtag
            else:
                print("⚠️  No tagged images found")
                rtag = questionary.text("Enter RTAG manually:").ask()
                config_values['RTAG'] = rtag
        else:
            print("⚠️  No ingenium images found")
            rtag = questionary.text("Enter RTAG manually:").ask()
            config_values['RTAG'] = rtag
    elif rtag_choice == "keep":
        pass  # Keep existing RTAG
    
    # Convert underscores to dashes for URLs, prefixes, and bucket names
    instance_for_prefix = config_values.get('INSTANCE_NAME', 'myproject').replace('_', '-')
    
    # Server URLs
    print("\nServer Configuration:")
    config_values['ING_MAIN_SERVER'] = questionary.text(
        "Main Server URL:",
        default=config_values.get('ING_MAIN_SERVER', f"https://ingenium-{instance_for_prefix}.example.com")
    ).ask()
    
    config_values['ING_ANALYTICS_SERVER'] = questionary.text(
        "Analytics Server URL:",
        default=config_values.get('ING_ANALYTICS_SERVER', f"https://ingenium-{instance_for_prefix}-analytics.example.com")
    ).ask()
    
    config_values['EMAIL_DOMAIN'] = questionary.text(
        "Email Domain (used for outgoing notification emails, e.g. example.com):",
        default=config_values.get('EMAIL_DOMAIN', '')
    ).ask()
    
    # SMTP configuration
    print("\nSMTP Configuration:")
    config_values['SMTP_HOST'] = questionary.text(
        "SMTP Host:",
        default=config_values.get('SMTP_HOST', 'smtp.example.com')
    ).ask()
    
    config_values['SMTP_IP'] = prompt_ip_for_host(
        config_values['SMTP_HOST'], config_values.get('SMTP_IP')
    )
    
    # LDAP configuration
    print("\nLDAP Configuration:")
    config_values['LDAP_BASE_DN'] = questionary.text(
        "LDAP Base DN:",
        default=config_values.get('LDAP_BASE_DN', 'dc=example,dc=com')
    ).ask()
    
    config_values['LDAP_GROUP_OBJECTCLASS'] = questionary.text(
        "LDAP Group ObjectClass:",
        default=config_values.get('LDAP_GROUP_OBJECTCLASS', 'groupOfNames')
    ).ask()
    
    config_values['LDAP_URL'] = questionary.text(
        "LDAP URL:",
        default=config_values.get('LDAP_URL', 'ldaps://ldap.example.com')
    ).ask()
    
    config_values['LDAP_HOST'] = questionary.text(
        "LDAP Hostname:",
        default=config_values.get('LDAP_HOST', 'ldap.example.com')
    ).ask()
    
    config_values['LDAP_IP'] = prompt_ip_for_host(
        config_values['LDAP_HOST'], config_values.get('LDAP_IP')
    )
    
    # RSA / MFA configuration
    print("\nRSA/MFA Configuration (leave blank if not using RSA MFA):")
    config_values['RSA_URL'] = questionary.text(
        "RSA Authentication URL:",
        default=config_values.get('RSA_URL', '')
    ).ask()
    
    config_values['RSA_CLIENT_ID'] = questionary.text(
        "RSA Client ID:",
        default=config_values.get('RSA_CLIENT_ID', '')
    ).ask()
    
    config_values['RSA_CLIENT_KEY'] = questionary.password(
        "RSA Client Key (input hidden):",
        default=''
    ).ask() or config_values.get('RSA_CLIENT_KEY', '')
    
    # Splunk configuration
    print("\nSplunk Configuration (leave blank if using local logging only):")
    config_values['SPLUNK_URL'] = questionary.text(
        "Splunk HEC URL (e.g. https://splunk.example.com:8088):",
        default=config_values.get('SPLUNK_URL', '')
    ).ask()
    
    # Project details
    print("\nProject Details:")
    instance_title = config_values.get('INSTANCE_NAME', 'MyProject').replace('_', ' ').title()
    
    config_values['APPLICATION_TITLE'] = questionary.text(
        "Application Title:",
        default=config_values.get('APPLICATION_TITLE', f"{instance_title} Ingenium")
    ).ask()
    
    config_values['APPLICATION_ACRONYM'] = questionary.text(
        "Application Acronym:",
        default=config_values.get('APPLICATION_ACRONYM', instance_title)
    ).ask()
    
    config_values['PROCEDURE_ID_PREFIX'] = questionary.text(
        "Procedure ID Prefix:",
        default=config_values.get('PROCEDURE_ID_PREFIX', f"{instance_for_prefix}-procedure-")
    ).ask()
    
    config_values['EXECUTION_ID_PREFIX'] = questionary.text(
        "Execution ID Prefix:",
        default=config_values.get('EXECUTION_ID_PREFIX', f"{instance_for_prefix}-ingenium-")
    ).ask()
    
    # Froala WYSIWYG editor license key
    print("\nFroala Editor Configuration:")
    print("  ⚠️  Froala is a THIRD-PARTY commercial WYSIWYG editor library.")
    print("  A license key is required for production/licensed use.")
    print("  Review Froala's Terms of Service and licensing terms yourself at:")
    print("    https://froala.com  (see their pricing/licensing pages)")
    print("  You are responsible for obtaining a valid license if required.")
    config_values['FROALA_KEY'] = questionary.text(
        "Froala license key (leave empty if none):",
        default=config_values.get('FROALA_KEY', '')
    ).ask()
    
    # Command string format (CMD "Lookup" builder)
    default_cmd_string_format = "{{STEM}}{{PRE_ARGS}},{{/PRE_ARGS}}{{#ARGS}}{{ARG_VALUE}}{{SEP}},{{/SEP}}{{/ARGS}}"
    print("\nCommand String Format (CMD 'Lookup' builder):")
    print("  Controls how STEM + ARGS are assembled into a command string.")
    print("  Tokens: {{STEM}}, {{PRE_ARGS}}...{{/PRE_ARGS}}, {{POST_ARGS}}...{{/POST_ARGS}},")
    print("          {{#ARGS}}...{{/ARGS}}, {{ARG_NAME}}, {{ARG_VALUE}}, {{SEP}}...{{/SEP}}")
    print("  Example, for STEM=PWR_CTRL with args SUBSYSTEM=SSPA and STATE=ON:")
    print(f"    {default_cmd_string_format}")
    print("      -> PWR_CTRL,SSPA,ON  (default)")
    print("  See docs/Configuration.md#command-string-format for full token reference.")
    config_values['CMD_STRING_FORMAT'] = questionary.text(
        "CMD_STRING_FORMAT:",
        default=config_values.get('CMD_STRING_FORMAT', default_cmd_string_format)
    ).ask()

    # AWS configuration
    print("\nAWS Configuration:")
    config_values['AWS_DEFAULT_REGION'] = questionary.text(
        "AWS Region:",
        default=config_values.get('AWS_DEFAULT_REGION', 'us-east-1')
    ).ask()
    
    config_values['MEDIA_BUCKET'] = questionary.text(
        "S3 Media Bucket:",
        default=config_values.get('MEDIA_BUCKET', f"ingenium-media-{instance_for_prefix}")
    ).ask()
    
    # Extra hosts configuration
    print("\nExtra Hosts Configuration (for plugout scenario):")
    configure_hosts = questionary.confirm(
        "Configure extra hosts? (Press Enter for defaults)",
        default=False
    ).ask()
    
    if configure_hosts:
        config_values['ING_HOST'] = questionary.text(
            "Main Server Hostname:",
            default=config_values.get('ING_HOST', config_values['ING_MAIN_SERVER'].replace('https://', ''))
        ).ask()
        
        config_values['ING_IP'] = prompt_ip_for_host(
            config_values['ING_HOST'], config_values.get('ING_IP')
        )
        
        config_values['ING_ANALYTICS_HOST'] = questionary.text(
            "Analytics Server Hostname:",
            default=config_values.get('ING_ANALYTICS_HOST', config_values['ING_ANALYTICS_SERVER'].replace('https://', ''))
        ).ask()
        
        config_values['ING_ANALYTICS_IP'] = prompt_ip_for_host(
            config_values['ING_ANALYTICS_HOST'], config_values.get('ING_ANALYTICS_IP')
        )
        
        add_venues = questionary.confirm("Add venue hosts?", default=True).ask()
        if add_venues:
            config_values['VENUE_HOST_1'] = questionary.text(
                "Venue Host 1:",
                default=config_values.get('VENUE_HOST_1', f"{instance_for_prefix}-dummy-1.example.com")
            ).ask()
            config_values['VENUE_IP_1'] = questionary.text(
                "Venue IP 1:",
                default=config_values.get('VENUE_IP_1', '240.0.0.1')
            ).ask()
            config_values['VENUE_HOST_2'] = questionary.text(
                "Venue Host 2:",
                default=config_values.get('VENUE_HOST_2', f"{instance_for_prefix}-dummy-2.example.com")
            ).ask()
            config_values['VENUE_IP_2'] = questionary.text(
                "Venue IP 2:",
                default=config_values.get('VENUE_IP_2', '240.0.0.2')
            ).ask()
        else:
            config_values['VENUE_HOST_1'] = ""
            config_values['VENUE_IP_1'] = ""
            config_values['VENUE_HOST_2'] = ""
            config_values['VENUE_IP_2'] = ""
    else:
        # Use defaults with dummy venue hosts and auto-resolved IPs
        config_values['ING_HOST'] = config_values['ING_MAIN_SERVER'].replace('https://', '')
        config_values['ING_ANALYTICS_HOST'] = config_values['ING_ANALYTICS_SERVER'].replace('https://', '')

        # Auto-resolve IPs, but never silently bake in a bogus value.
        # A wrong IP here breaks docker-compose extra_hosts and causes
        # connectivity failures to the main/analytics servers. If DNS
        # resolution fails the user is notified and required to enter the IP.
        config_values['ING_IP'] = prompt_ip_for_host(config_values['ING_HOST'])
        config_values['ING_ANALYTICS_IP'] = prompt_ip_for_host(config_values['ING_ANALYTICS_HOST'])

        config_values['VENUE_HOST_1'] = f"{instance_for_prefix}-dummy-1.example.com"
        config_values['VENUE_IP_1'] = "240.0.0.1"
        config_values['VENUE_HOST_2'] = f"{instance_for_prefix}-dummy-2.example.com"
        config_values['VENUE_IP_2'] = "240.0.0.2"
    
    # Custom footers/headers
    print("\nCustomization (optional):")
    customize = questionary.confirm(
        "Customize PDF/UI footers and PDF notes?",
        default=False
    ).ask()
    
    if customize:
        config_values['PDF_CUSTOM_HEADER'] = questionary.text(
            "PDF Custom Header (HTML/CSS, press Enter for none):",
            default=config_values.get('PDF_CUSTOM_HEADER', '')
        ).ask()
        
        config_values['PDF_CUSTOM_FOOTER'] = questionary.text(
            "PDF Custom Footer (HTML/CSS, press Enter for default):",
            default=config_values.get('PDF_CUSTOM_FOOTER', '')
        ).ask()
        
        config_values['UI_CUSTOM_FOOTER'] = questionary.text(
            "UI Custom Footer (HTML/CSS, press Enter for default):",
            default=config_values.get('UI_CUSTOM_FOOTER', '')
        ).ask()

        config_values['PDF_PROCEDURE_NOTE'] = questionary.text(
            "PDF Procedure Note (HTML/CSS, press Enter for default):",
            default=config_values.get('PDF_PROCEDURE_NOTE', 'NOTE: Paper copy of this procedure may not be current and should not be relied on for official information. The current version is available in the Ingenium web application.')
        ).ask()

        config_values['PDF_EXECUTION_NOTE'] = questionary.text(
            "PDF Execution Note (HTML/CSS, press Enter for default):",
            default=config_values.get('PDF_EXECUTION_NOTE', 'NOTE: Paper copy of this AS RUN may not be current and should not be relied on for official information. The current version is available in the Ingenium web application.')
        ).ask()
    else:
        config_values['PDF_CUSTOM_HEADER'] = config_values.get('PDF_CUSTOM_HEADER', '')
        config_values['PDF_CUSTOM_FOOTER'] = config_values.get('PDF_CUSTOM_FOOTER', '')
        config_values['UI_CUSTOM_FOOTER'] = config_values.get('UI_CUSTOM_FOOTER', 'Proprietary - Not for Public Release - Do Not Distribute or Duplicate')
        config_values['PDF_PROCEDURE_NOTE'] = config_values.get('PDF_PROCEDURE_NOTE', 'NOTE: Paper copy of this procedure may not be current and should not be relied on for official information. The current version is available in the Ingenium web application.')
        config_values['PDF_EXECUTION_NOTE'] = config_values.get('PDF_EXECUTION_NOTE', 'NOTE: Paper copy of this AS RUN may not be current and should not be relied on for official information. The current version is available in the Ingenium web application.')
    
    # PDF cleanup configuration
    print("\nPDF Cleanup Configuration:")
    pdf_cleanup_enabled = questionary.confirm(
        "Enable PDF cleanup?",
        default=config_values.get('PDF_CLEANUP_ENABLED', 'true') == 'true'
    ).ask()
    config_values['PDF_CLEANUP_ENABLED'] = 'true' if pdf_cleanup_enabled else 'false'
    
    config_values['PDF_RETENTION_DAYS'] = questionary.text(
        "PDF Retention Days:",
        default=config_values.get('PDF_RETENTION_DAYS', '14'),
        validate=lambda text: True if text.strip().isdigit() else "Must be a number"
    ).ask()
    
    return config_values


def create_instance(instance_name: str, config_values: Dict[str, str], deployments_path: Path) -> bool:
    """Create new instance by copying template and replacing placeholders."""
    template_path = deployments_path / "project_instance_template"
    instance_path = deployments_path / instance_name
    
    print(f"\n📁 Creating instance directory: {instance_path}")
    
    # Check if instance already exists
    if instance_path.exists():
        print(f"❌ Error: Instance '{instance_name}' already exists!")
        return False
    
    # Copy template
    try:
        shutil.copytree(template_path, instance_path)
        print(f"✓ Copied template to {instance_name}/")
    except Exception as e:
        print(f"❌ Error copying template: {e}")
        return False
    
    # Replace placeholders in ing_envs.sh
    env_file = instance_path / "ing_envs.sh"
    content = env_file.read_text()
    
    for key, value in config_values.items():
        placeholder = f"{{{{{key}}}}}"
        content = content.replace(placeholder, value)
    
    env_file.write_text(content)
    print(f"✓ Generated ing_envs.sh with configuration")
    
    # Generate secrets
    secrets_values = generate_secrets()
    
    # Create ing_secrets.sh with generated values
    secrets_file = instance_path / "ing_secrets.sh"
    secrets_content = f"""#!/usr/bin/bash
export PRIVATE_PEM='{secrets_values['PRIVATE_PEM']}'
export PUBLIC_PEM='{secrets_values['PUBLIC_PEM']}'
export EXEC_VENUE_PRIVATE_PEM='{secrets_values['EXEC_VENUE_PRIVATE_PEM']}'
export EXEC_VENUE_PUBLIC_PEM='{secrets_values['EXEC_VENUE_PUBLIC_PEM']}'

# Archive
export ARANGO_ROOT_PASSWORD="{secrets_values['ARANGO_ROOT_PASSWORD']}"

# Auth
export AUTH_DB_MYSQL_ROOT_PASSWORD="{secrets_values['AUTH_DB_MYSQL_ROOT_PASSWORD']}"
export TEST_USER="{secrets_values['TEST_USER']}"
export TEST_PASS="{secrets_values['TEST_PASS']}"

# Execution Monitor
export EMS_SECRET="{secrets_values['EMS_SECRET']}"

# CSRF protection (auto-generated)
export CSRF_SECRET="{secrets_values['CSRF_SECRET']}"

# File Server
export AWS_ACCESS_KEY_ID="{secrets_values['AWS_ACCESS_KEY_ID']}"
export AWS_SECRET_ACCESS_KEY="{secrets_values['AWS_SECRET_ACCESS_KEY']}"

# logging
export SPLUNK_TOKEN="{secrets_values['SPLUNK_TOKEN']}"
"""
    
    secrets_file.write_text(secrets_content)
    print(f"✓ Generated ing_secrets.sh with auto-generated values")
    
    # Remove the template file
    secrets_template = instance_path / "ing_secrets.sh.template"
    if secrets_template.exists():
        secrets_template.unlink()
    
    return True


def update_instance(instance_name: str, config_values: Dict[str, str], deployments_path: Path) -> bool:
    """Update existing instance configuration."""
    instance_path = deployments_path / instance_name
    
    print(f"\n📝 Updating instance: {instance_path}")
    
    # Backup current ing_envs.sh
    env_file = instance_path / "ing_envs.sh"
    backup_file = instance_path / "ing_envs.sh.backup"
    shutil.copy(env_file, backup_file)
    print(f"✓ Backed up current config to ing_envs.sh.backup")
    
    # Load template and replace placeholders
    template_path = deployments_path / "project_instance_template"
    template_env = template_path / "ing_envs.sh"
    content = template_env.read_text()
    
    for key, value in config_values.items():
        placeholder = f"{{{{{key}}}}}"
        content = content.replace(placeholder, value)
    
    env_file.write_text(content)
    print(f"✓ Updated ing_envs.sh with new configuration")
    print(f"  Previous config saved as ing_envs.sh.backup")
    
    return True


def check_docker_network() -> Tuple[bool, str]:
    """Check if ingenium Docker network exists."""
    result = subprocess.run(
        ["docker", "network", "inspect", "ingenium"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    if result.returncode == 0:
        return True, "✓ Docker network 'ingenium' exists"
    else:
        return False, "⚠️  Docker network 'ingenium' not found"


def create_docker_network() -> Tuple[bool, str]:
    """Create ingenium Docker network."""
    success, output = run_command(["docker", "network", "create", "ingenium", "-d", "bridge"])
    if success:
        return True, "✓ Created Docker network 'ingenium'"
    else:
        return False, f"❌ Failed to create Docker network: {output}"


def check_data_directories() -> Dict[str, bool]:
    """Check if required data directories exist."""
    required_dirs = {
        # Main Server directories
        '/data/auth': False,
        '/data/arangodb': False,
        '/data/arangodb_dict_service': False,
        '/data/file_server': False,
        # Analytics Server directories
        '/data/elasticsearch': False,
    }
    
    for dir_path in required_dirs.keys():
        required_dirs[dir_path] = Path(dir_path).exists()
    
    return required_dirs


def create_data_directories() -> Dict[str, str]:
    """Create required data directories with proper permissions.
    
    WARNING: This creates directories on the LOCAL machine.
    In production, directories should be created on the target Main/Analytics server VMs.
    This function is kept for reference but should NOT be called automatically.
    """
    results = {}
    
    # All required directories (arangodb is used by both servers)
    all_dirs = ['/data/auth', '/data/arangodb', '/data/arangodb_dict_service', '/data/file_server', '/data/elasticsearch']
    
    print("\n📂 Creating data directories...")
    print("  (This requires sudo permissions)")
    print("  ⚠️  WARNING: Creating on LOCAL machine - may not be the target server!")
    
    # Try to create all directories
    for dir_path in all_dirs:
        try:
            subprocess.run(['sudo', 'mkdir', '-p', dir_path], check=True)
            subprocess.run(['sudo', 'chmod', '777', dir_path], check=True)
            results[dir_path] = f"✓ Created and set permissions"
        except subprocess.CalledProcessError as e:
            results[dir_path] = f"❌ Failed: {e}"
    
    # Create nested data directory inside elasticsearch
    elasticsearch_data = '/data/elasticsearch/data'
    try:
        subprocess.run(['sudo', 'mkdir', '-p', elasticsearch_data], check=True)
        subprocess.run(['sudo', 'chmod', '777', elasticsearch_data], check=True)
        results[elasticsearch_data] = f"✓ Created and set permissions"
    except subprocess.CalledProcessError as e:
        results[elasticsearch_data] = f"❌ Failed: {e}"
    
    return results


def check_ssl_certificates(instance_path: Path) -> Dict[str, bool]:
    """Check if SSL certificates exist."""
    ssl_files = {
        'Main SSL Cert': instance_path / 'ssl' / 'ing_https.crt',
        'Main SSL Key': instance_path / 'ssl' / 'ing_https.key',
        'Analytics SSL Cert': instance_path / 'ssl_analytics' / 'ing_https.crt',
        'Analytics SSL Key': instance_path / 'ssl_analytics' / 'ing_https.key',
    }
    
    results = {}
    for name, path in ssl_files.items():
        results[name] = path.exists()
    
    return results


def check_required_images(rtag: str) -> Tuple[List[str], List[str]]:
    """Check which required images exist for the given RTAG."""
    required_services = [
        'auth_service',
        'archive_ing',
        'exec_server',
        'execution_monitor',
        'core_server',
        'dict_service',
        'report_server',
        'ui',
        'ui_nginx',
        'data_sync_service',
        'search_server',
    ]
    
    required_images = [f"ingenium/{service}:{rtag}" for service in required_services]
    
    # Get existing images
    result = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    existing_images = set(result.stdout.strip().split('\n')) if result.returncode == 0 else set()
    
    found = [img for img in required_images if img in existing_images]
    missing = [img for img in required_images if img not in existing_images]
    
    return found, missing


def display_summary(instance_name: str, config_values: Dict[str, str], instance_path: Path):
    """Display setup summary and next steps."""
    rtag = config_values.get('RTAG', 'unknown')
    
    print("\n" + "="*80)
    print("✅ INSTANCE SETUP COMPLETE!")
    print("="*80)
    
    print(f"\nInstance Configuration:")
    print(f"  Name:              {instance_name}")
    print(f"  Location:          {instance_path}")
    print(f"  RTAG:              {rtag}")
    print(f"  Main Server:       {config_values.get('ING_MAIN_SERVER')}")
    print(f"  Analytics Server:  {config_values.get('ING_ANALYTICS_SERVER')}")
    
    print(f"\nConfiguration Files:")
    print(f"  ✓ ing_envs.sh      Generated with all configuration")
    print(f"  ✓ ing_secrets.sh   Generated with auto-generated secrets")
    print(f"    - RSA key pairs (JWT & Execution Venue)")
    print(f"    - Database passwords (12-character random)")
    print(f"    - AWS credentials (12-character random)")
    print(f"    - CSRF secret (32-character random)")
    print(f"    - Splunk token (as provided)")
    
    # Check infrastructure
    print(f"\nInfrastructure:")
    
    network_exists, network_msg = check_docker_network()
    print(f"  {network_msg}")
    
    if not network_exists:
        create_net = questionary.confirm("  Create Docker network now?", default=True).ask()
        if create_net:
            success, msg = create_docker_network()
            print(f"  {msg}")
    
    # Check data directories (informational - create using wizard or manually)
    data_dirs = check_data_directories()
    total_count = sum(1 for v in data_dirs.values() if v)
    
    if total_count == 0:
        print(f"  Data directories: missing")
    else:
        print(f"  Data directories: {total_count}/5 exist on this server")
    print(f"    ℹ️  Note: Use '📂 Create Data Directories' from main wizard menu")
    print(f"    Main Server needs: auth, arangodb, arangodb_dict_service, file_server")
    print(f"    Analytics Server needs: arangodb, elasticsearch (with elasticsearch/data nested)")
    
    # User can create via main wizard menu
    dirs_created = False
    
    # Check SSL
    print(f"\nSSL Certificates:")
    ssl_status = check_ssl_certificates(instance_path)
    for name, exists in ssl_status.items():
        status = "✓" if exists else "⚠️ "
        print(f"  {status} {name}")
    
    # Check images
    print(f"\nDocker Images:")
    found, missing = check_required_images(rtag)
    print(f"  Found:   {len(found)}/{len(found) + len(missing)} required images")
    if missing:
        print(f"  Missing: {len(missing)} images")
        print(f"\n  Missing images:")
        for img in missing[:5]:  # Show first 5
            print(f"    - {img}")
        if len(missing) > 5:
            print(f"    ... and {len(missing) - 5} more")
    
    # Next steps
    print("\n" + "="*80)
    print("📋 NEXT STEPS:")
    print("="*80)
    
    step_num = 1
    
    print(f"\n{step_num}. ℹ️  Review generated secrets (optional)")
    print(f"   $ cat {instance_path}/ing_secrets.sh")
    print("\n   All secrets have been auto-generated:")
    print("   - RSA keys for JWT authentication")
    print("   - Database passwords (ArangoDB, MySQL)")
    print("   - AWS credentials (random strings)")
    print("   - CSRF secret (random string)")
    print("   - Splunk token (as provided)")
    print("\n   ⚠️  Note: AWS credentials are randomly generated.")
    print("      Replace them with real AWS credentials if using S3.")
    step_num += 1
    
    # Data directories step - ALWAYS show (must be created on servers)
    print(f"\n{step_num}. ⚠️  REQUIRED: Create data directories")
    print(f"   On each server VM (Main/Analytics), create required directories:")
    print(f"\n   Option 1 - Use wizard (on the server VM):")
    print(f"   $ ./run.sh")
    print(f"   Select: '📂 Create Data Directories'")
    print(f"   Choose: Main Server or Analytics Server")
    print(f"\n   Option 2 - Manual commands:")
    print(f"\n   📦 On Main Server VM:")
    print(f"   $ mkdir -p /data && cd /data")
    print(f"   $ mkdir auth && chmod 777 auth")
    print(f"   $ mkdir arangodb && chmod 777 arangodb")
    print(f"   $ mkdir arangodb_dict_service && chmod 777 arangodb_dict_service")
    print(f"   $ mkdir file_server && chmod 777 file_server")
    print(f"\n   📊 On Analytics Server VM:")
    print(f"   $ mkdir -p /data && cd /data")
    print(f"   $ mkdir arangodb && chmod 777 arangodb")
    print(f"   $ mkdir -p elasticsearch/data && chmod 777 elasticsearch elasticsearch/data")
    step_num += 1
    
    if not all(ssl_status.values()):
        print(f"\n{step_num}. ⚠️  REQUIRED: Add SSL certificates")
        print(f"   Main Server:")
        print(f"     - {instance_path}/ssl/ing_https.crt")
        print(f"     - {instance_path}/ssl/ing_https.key")
        print(f"   Analytics Server:")
        print(f"     - {instance_path}/ssl_analytics/ing_https.crt")
        print(f"     - {instance_path}/ssl_analytics/ing_https.key")
        print(f"\n   Get certificates from: https://ssl.example.com")
        step_num += 1
    
    if missing:
        print(f"\n{step_num}. ⚠️  RECOMMENDED: Build missing Docker images")
        print(f"   On the server VM where images are needed:")
        print(f"\n   Option 1 - Use wizard:")
        print(f"   $ ./run.sh")
        print(f"   Select: '🔨 Build Docker Images'")
        print(f"   Choose: Main Server or Analytics Server (based on this VM)")
        print(f"   Build with tag: {rtag}")
        print(f"\n   Option 2 - Command line:")
        print(f"   $ ./build_images.py --repo all --tag {rtag}")
        step_num += 1
    
    print(f"\n{step_num}. 🚀 Deploy Ingenium")
    print(f"   $ ./run.sh")
    print(f"   Select: 'Deploy Services'")
    print(f"   Choose instance: {instance_name}")
    
    print("\n" + "="*80)
    print("For full deployment instructions, see:")
    print("  - README.md (Setting up the Read Replica of ArangoDB section covers")
    print("    database setup, replication, etc.)")
    print("="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Setup wizard for Ingenium deployment instances",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (recommended)
  %(prog)s
  
  # Create new instance with specific name
  %(prog)s --create my_project
  
  # Update existing instance
  %(prog)s --update my_project
"""
    )
    
    parser.add_argument(
        "--create",
        metavar="INSTANCE",
        help="Create new instance with specified name"
    )
    
    parser.add_argument(
        "--update",
        metavar="INSTANCE",
        help="Update existing instance"
    )
    
    args = parser.parse_args()
    
    deployments_path = Path.cwd()
    
    # Validate we're in opensource_deployment3 directory
    if not (deployments_path / "project_instance_template").exists():
        print("❌ Error: Must run from opensource_deployment3 directory")
        print(f"   Current directory: {deployments_path}")
        sys.exit(1)
    
    # Determine mode
    if args.create:
        mode = "create"
        instance_name = args.create
        existing_config = None
    elif args.update:
        mode = "update"
        instance_name = args.update
        instance_path = deployments_path / instance_name
        if not instance_path.exists():
            print(f"❌ Error: Instance '{instance_name}' does not exist")
            sys.exit(1)
        existing_config = load_instance_config(instance_path)
    else:
        # Interactive mode selection
        print("\n" + "="*60)
        print("INGENIUM INSTANCE SETUP WIZARD")
        print("="*60 + "\n")
        
        mode_choice = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Choice("Create new instance", value="create"),
                questionary.Choice("Update existing instance", value="update"),
                questionary.Separator(),
                questionary.Choice("⬅️  Back", value="back"),
            ]
        ).ask()
        
        if mode_choice is None or mode_choice == "back":
            print("\n⬅️  Returning to main menu...\n")
            sys.exit(0)
        
        mode = mode_choice
        
        if mode == "update":
            existing_instances = get_existing_instances(deployments_path)
            if not existing_instances:
                print("❌ No existing instances found")
                sys.exit(1)
            
            update_choices = list(existing_instances) + [questionary.Separator(), questionary.Choice("⬅️  Back", value="back")]
            instance_name = questionary.select(
                "Select instance to update:",
                choices=update_choices
            ).ask()
            
            if instance_name is None or instance_name == "back":
                print("\n⬅️  Returning to main menu...\n")
                sys.exit(0)
            
            instance_path = deployments_path / instance_name
            existing_config = load_instance_config(instance_path)
        else:
            instance_name = None
            existing_config = None
    
    # Prompt for configuration
    config_values = prompt_for_config(mode, existing_config)
    
    # Get instance name if not set yet
    if instance_name is None:
        instance_name = config_values['INSTANCE_NAME']
    else:
        config_values['INSTANCE_NAME'] = instance_name
    
    # Create or update instance
    if mode == "create":
        success = create_instance(instance_name, config_values, deployments_path)
    else:
        success = update_instance(instance_name, config_values, deployments_path)
    
    if not success:
        sys.exit(1)
    
    # Display summary
    instance_path = deployments_path / instance_name
    display_summary(instance_name, config_values, instance_path)


if __name__ == "__main__":
    main()
