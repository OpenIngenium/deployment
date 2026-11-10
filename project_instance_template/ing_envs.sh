#!/usr/bin/bash
export ING_INSTANCE={{INSTANCE_NAME}}
export ING_MAIN_SERVER={{ING_MAIN_SERVER}}
export ING_ANALYTICS_SERVER={{ING_ANALYTICS_SERVER}}
# 
export RTAG={{RTAG}}
export AUTH_SERVICE_MYSQL_IMAGE=mysql:5.6
export AUTH_SERVICE_REDIS_IMAGE=redis:7.0.8
export AUTH_SERVICE_IMAGE=ingenium/auth_service:${RTAG}
export ARANGODB_ARCHIVE_IMAGE=arangodb:3.9.3
export ARCHIVE_ING_IMAGE=ingenium/archive_ing:${RTAG}
export EXEC_REDIS_IMAGE=redis:7.0.8
export EXEC_SERVER_IMAGE=ingenium/exec_server:${RTAG}
export EXECUTION_MONITOR_IMAGE=ingenium/execution_monitor:${RTAG}
export FILESERVERING_IMAGE=minio/minio:RELEASE.2018-07-13T00-09-07Z
export CORE_SERVER_IMAGE=ingenium/core_server:${RTAG}
export DICT_SERVICE_IMAGE=ingenium/dict_service:${RTAG}
export REPORT_SERVER_IMAGE=ingenium/report_server:${RTAG}
export UI_IMAGE=ingenium/ui:${RTAG}
export UI_NGINX_IMAGE=ingenium/ui_nginx:${RTAG}

# ANALYTICS SERVER
export ELASTICSEARCH_ANALYTICS_IMAGE=docker.elastic.co/elasticsearch/elasticsearch:8.6.0
export DATA_SYNC_SERVICE_IMAGE=ingenium/data_sync_service:${RTAG}
export SEARCH_SERVER_IMAGE=ingenium/search_server:${RTAG}
export REPORT_SERVICE_REDIS_IMAGE=redis:7.0.8
export SEARCH_API_URL=${ING_ANALYTICS_SERVER}/search_server
export REPORT_API_URL=${ING_ANALYTICS_SERVER}/report_server
export FILE_SERVER_API_URL=${ING_MAIN_SERVER}/minio
export CORE_API_URL=${ING_MAIN_SERVER}/core_server
export REPORT_REDIS_PORT_FROM=6379

# Auth
export LDAP_URL={{LDAP_URL}}
export RSA_URL={{RSA_URL}}
export RSA_CLIENT_ID={{RSA_CLIENT_ID}}
export RSA_CLIENT_KEY={{RSA_CLIENT_KEY}}
export AUTH_DB_MYSQL_DATABASE=auth
export AUTH_REDIS_PORT_FROM=6379
export LONG_EXPIRE=48000
export LDAP_BASE_DN={{LDAP_BASE_DN}}
export LDAP_GROUP_OBJECTCLASS={{LDAP_GROUP_OBJECTCLASS}}

# Report
export ING_SERVER=${ING_MAIN_SERVER}
export SMTP_HOST={{SMTP_HOST}}
export SMTP_HOST_PORT=25
export EMAIL_DOMAIN={{EMAIL_DOMAIN}}
export PDF_PROCEDURE_NOTE="{{PDF_PROCEDURE_NOTE}}"
export PDF_EXECUTION_NOTE="{{PDF_EXECUTION_NOTE}}"
## Project-specific PDF marking & handling.
## PDF_CUSTOM_HEADER: optional HTML/CSS prepended as an extra top line ABOVE the existing per-document header (procedure/execution/diff metadata is preserved).
## PDF_CUSTOM_FOOTER: optional HTML/CSS that REPLACES the default ITAR export-control statement in the footer (page number remains below it).
## Both accept text/HTML/CSS. If no inline CSS is provided, default styling is automatically applied (centered, 7px font, italic Arial). Empty string uses default value. 
export PDF_CUSTOM_HEADER="{{PDF_CUSTOM_HEADER}}"
export PDF_CUSTOM_FOOTER="{{PDF_CUSTOM_FOOTER}}"
export NUM_WORKERS=1
export PDF_CLEANUP_ENABLED="{{PDF_CLEANUP_ENABLED}}"
export PDF_RETENTION_DAYS="{{PDF_RETENTION_DAYS}}"

# Execution
export EXECUTION_CACHE_TYPE=REDIS
export NUMBER_OF_KERNELS_MIN=20
export AWS_DEFAULT_REGION="{{AWS_DEFAULT_REGION}}"
export VERIFY_FSW_CHANNELS=""
export VERIFY_FSW_EVR=CMD_SVC_EVR_CMD_COMPLETED_SUCCESS
export VERIFY_HW_CHANNELS=""
export VERIFY_HW_EVR=CMD_SVC_EVR_VC0_COMMAND_DISPATCH
export VERIFY_FILE_CHANNELS=""
export VERIFY_FILE_EVR=FV_SVC_EVR_WRITE_NVFS_FILE_SUCCESS
export VERIFY_EVR_MSG="true"

# Archive
export PROCEDURE_ID_PREFIX="{{PROCEDURE_ID_PREFIX}}"
export EXECUTION_ID_PREFIX="{{EXECUTION_ID_PREFIX}}"

# File Server
export MEDIA_BUCKET={{MEDIA_BUCKET}}


# UI
export APPLICATION_TITLE="{{APPLICATION_TITLE}}"
export APPLICATION_ACRONYM="{{APPLICATION_ACRONYM}}"
export AUTH_METHOD=password
## Project-specific marking & handling.
## UI_CUSTOM_FOOTER: optional HTML/CSS that REPLACES the default ITAR export-control statement in the footer. Empty string uses default value. 
export UI_CUSTOM_FOOTER="{{UI_CUSTOM_FOOTER}}"
## FROALA_KEY: license key for the Froala WYSIWYG editor (third-party library).
## Froala is commercial software - a valid license key is required for production use.
## Review Froala's Terms of Service / licensing terms at https://froala.com before use.
## Can be left as an empty string (editor may run in trial/unlicensed mode with limitations).
export FROALA_KEY="{{FROALA_KEY}}"
# --- Command string format (CMD "Lookup" builder) ---
# Controls how STEM + ARGS are assembled into a command string. Rendered client-side by
# src/client/src/modules/elements/executable/cmd/cmd-string-format.js from
# window.cmdStringFormat (templateLocals.js -> head.ejs).
#
# Tokens: {{STEM}}, {{PRE_ARGS}}...{{/PRE_ARGS}}, {{POST_ARGS}}...{{/POST_ARGS}},
#         {{#ARGS}}...{{/ARGS}}, {{ARG_NAME}}, {{ARG_VALUE}}, {{SEP}}...{{/SEP}}
#         (PRE_ARGS/POST_ARGS render only when arguments exist; SEP joins BETWEEN arguments).
#
# Examples, for STEM=PWR_CTRL with args SUBSYSTEM=SSPA and STATE=ON:
#   {{STEM}}{{PRE_ARGS}},{{/PRE_ARGS}}{{#ARGS}}{{ARG_VALUE}}{{SEP}},{{/SEP}}{{/ARGS}}  (default)
#     -> PWR_CTRL,SSPA,ON      (no args: PWR_CTRL - the PRE_ARGS comma is skipped)
#   {{STEM}}{{#ARGS}} {{ARG_NAME}}={{ARG_VALUE}}{{/ARGS}}
#     -> PWR_CTRL SUBSYSTEM=SSPA STATE=ON
#
# Full token reference, more examples and the round-trip (re-parse) caveats:
# docs/Configuration.md#command-string-format. Keep the value quoted so '#' is not treated
# as a dotenv comment.
export CMD_STRING_FORMAT="{{CMD_STRING_FORMAT}}"

# Logging (used by docker-compose-splunk.yml / docker-compose-splunk-analytics.yml)
export SPLUNK_URL={{SPLUNK_URL}}

#OPENSHIFT 
export MTU=1400

# Extra hosts information for plugout scenario
export ING_HOST={{ING_HOST}}
export ING_IP={{ING_IP}}
# For the analytics VM, IP address is used above. The two lines below are added for future reference and not to break docker compose file.
export ING_ANALYTICS_HOST={{ING_ANALYTICS_HOST}}
export ING_ANALYTICS_IP={{ING_ANALYTICS_IP}}
export LDAP_HOST={{LDAP_HOST}}
export LDAP_IP={{LDAP_IP}}
# Note that SMTP_HOST is already defined above.
export SMTP_IP={{SMTP_IP}}
export VENUE_HOST_1={{VENUE_HOST_1}}
export VENUE_IP_1={{VENUE_IP_1}}
export VENUE_HOST_2={{VENUE_HOST_2}}
export VENUE_IP_2={{VENUE_IP_2}}
