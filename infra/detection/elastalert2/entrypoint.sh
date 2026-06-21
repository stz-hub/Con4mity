#!/bin/sh
set -e
: "${OPENSEARCH_HOST:?}"; : "${OPENSEARCH_PORT:=9200}"
: "${DASHBOARD_IP:?}"; : "${DASHBOARD_PORT:=8090}"; : "${WEBHOOK_TOKEN:?}"
sed "s#{{OPENSEARCH_HOST}}#${OPENSEARCH_HOST}#g; s#{{OPENSEARCH_PORT}}#${OPENSEARCH_PORT}#g; s#__DASHBOARD__#${DASHBOARD_IP}:${DASHBOARD_PORT}#g; s#__TOKEN__#${WEBHOOK_TOKEN}#g" \
    /opt/elastalert/config.yaml.template > /tmp/config.yaml
DST=/tmp/rules-rendered
mkdir -p "$DST"; rm -f "$DST"/*.yml 2>/dev/null || true
for f in /opt/elastalert/rules/active/*.yml; do
  [ -f "$f" ] || continue
  b=$(basename "$f"); cp "$f" "$DST/$b"
  grep -q "^index:" "$DST/$b" || echo "index: con4mity-logs-*" >> "$DST/$b"
  grep -q "^alert:" "$DST/$b" || printf "alert:\n- post\n" >> "$DST/$b"
done
echo "[entrypoint] $(ls $DST/*.yml 2>/dev/null | wc -l) regles -> webhook ${DASHBOARD_IP}:${DASHBOARD_PORT}, OpenSearch ${OPENSEARCH_HOST}:${OPENSEARCH_PORT}"
exec elastalert --verbose --config /tmp/config.yaml
