#!/bin/bash

INSTANCE=""
LOG_DRIVER="local"
COMPOSE_COMMAND=""

# Detect docker compose command (modern plugin vs legacy standalone)
if docker compose version &>/dev/null; then
    DOCKER_COMPOSE="docker compose"
elif docker-compose version &>/dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "ERROR: Neither 'docker compose' nor 'docker-compose' found."
    exit 1
fi

usage() {
  echo "
  Usage: $0 -i INSTANCE -l LOG_DRIVER SERVICE_NAME
  
    Options:
      -i INSTANCE (required): name of Ingenium instance (name of subdirectory)
      -l LOG_DRIVER (required): name of log driver (local or splunk)

  Example:
  $0 -i my_project -l splunk analytics_nginx
  " 
}

input_error() {
  usage
  exit 1
}

while getopts ":i:l:" options; do
  case "${options}" in                     
    i)                                    
      INSTANCE=${OPTARG}
      ;;
    l)
      LOG_DRIVER=${OPTARG}
      ;;
    :)
      echo "Error: -${OPTARG} requires a value."
      input_error
      ;;
    *)                                    
      break
      ;;
  esac
done

echo "INSTANCE: $INSTANCE"
echo "LOG_DRIVER: $LOG_DRIVER"

if [[ -z $INSTANCE ]] || [[ -z $LOG_DRIVER ]]
then
    echo "Error: INSTANCE and LOG_DRIVER are required."
    input_error
fi

if [[ -d "$INSTANCE" ]]
then
    ING_ENVS="${INSTANCE}/ing_envs.sh"
    if [[ -f "${ING_ENVS}" ]]
    then
        echo "sourcing: ${ING_ENVS}"
        source "${ING_ENVS}"
    else
        echo "ERROR: File does not exists: ${ING_ENVS}"
        exit 1
    fi

    ING_SECRETS="${INSTANCE}/ing_secrets.sh"
    if [[ -f "${ING_SECRETS}" ]]
    then
        echo "sourcing: ${ING_SECRETS}"
        source "${ING_SECRETS}"
    else
        echo "ERROR: File does not exists: ${ING_SECRETS}"
        exit 1
    fi
else
    echo "ERROR: Directory does not exists: ${INSTANCE}"
    exit 1
fi

shift $((OPTIND-1))
SERVICE_NAME=$@

export NGINX_SSL_DIR="${PWD}/${INSTANCE}/ssl_analytics"

echo "NGINX_SSL_DIR: ${NGINX_SSL_DIR}"

export NGINX_CONF_DIR="${PWD}/${INSTANCE}/nginx_analytics_conf"

echo "NGINX_CONF_DIR: ${NGINX_CONF_DIR}"

if [[ "$LOG_DRIVER" == "splunk" ]]
then
    COMPOSE_CMD="${DOCKER_COMPOSE} -f docker-compose-analytics.yml -f docker-compose-splunk-analytics.yml up -d ${SERVICE_NAME}"
elif [[ "$LOG_DRIVER" == "local" ]]
then
    COMPOSE_CMD="${DOCKER_COMPOSE} -f docker-compose-analytics.yml -f docker-compose-local-analytics.yml up -d ${SERVICE_NAME}"
else
    echo "ERROR: Invalid log driver: ${LOG_DRIVER}"
    usage
    exit 1
fi

echo "Running: $COMPOSE_CMD"
$COMPOSE_CMD

