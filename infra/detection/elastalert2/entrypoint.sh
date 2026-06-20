#!/bin/sh
set -e
: "${OPENSEARCH_HOST:?}"; : "${OPENSEARCH_PORT:=9200}"
: "${DASHBOARD_IP:?}"; : "${DASHBOARD_PORT:=8090}"; : "${WEBHOOK_TOKEN:?}"
SRC=/opt/elastalert/rules/active
DST=/tmp/rules-rendered
mkdir -p "$DST"; rm -f "$DST"/*.yml 2>/dev/null || true
cp "$SRC"/*.yml "$DST"/ 2>/dev/null || true
sed -i "s#__DASHBOARD__#${DASHBOARD_IP}:${DASHBOARD_PORT}#g; s#__TOKEN__#${WEBHOOK_TOKEN}#g" "$DST"/*.yml
sed "s#{{OPENSEARCH_HOST}}#${OPENSEARCH_HOST}#g; s#{{OPENSEARCH_PORT}}#${OPENSEARCH_PORT}#g" \
    /opt/elastalert/config.yaml.template > /tmp/config.yaml
echo "[entrypoint] $(ls $DST/*.yml | wc -l) regles rendues -> OpenSearch ${OPENSEARCH_HOST}:${OPENSEARCH_PORT}, webhook ${DASHBOARD_IP}:${DASHBOARD_PORT}"
exec elastalert --verbose --config /tmp/config.yaml
