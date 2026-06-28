#!/bin/bash
# Deploiement complet des regles ElastAlert2

set -e

# Chemins absolus
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../" && pwd)"
ACTIVE_DIR="$SCRIPT_DIR/../elastalert2/rules/active"

# Charger le .env
if [ -f "$ROOT_DIR/.env" ]; then
	source "$ROOT_DIR/.env"
else
	echo "Fichier .env manquant dans $ROOT_DIR"
	exit 1
fi

echo "=== Deploiement Con4mity SIEM ==="
echo "Profil    : $PROFILE"
echo "OpenSearch: $OPENSEARCH_HOST:$OPENSEARCH_PORT"
echo "Dashboard : $DASHBOARD_IP:$DASHBOARD_PORT"
echo "=================================="

# 1 Verifier OpenSearch
curl -sf "http://${OPENSEARCH_HOST}:${OPENSEARCH_PORT}" > /dev/null \
	|| { echo "OpenSearch inaccessible"; exit 1; }
echo "1. OpenSearch OK"

# 2 Convertir les regles Sigma
echo "2. Conversion des regles Sigma..."
bash "$SCRIPT_DIR/convert_rules.sh"

# 3 Corriger les severites
echo "3. Correction des severites..."
bash "$SCRIPT_DIR/fix_severity.sh"

# 4 Remplacer les variables dans les regles
echo "4. Injection des variables..."
for f in "$ACTIVE_DIR"/*.yml; do
	sed -i \
	       -e "s|http://[0-9.]*:[0-9]*/api/webhook/alert|http://${DASHBOARD_IP}:${DASHBOARD_PORT}/api/webhook/alert|g" \
	       -e "s|X-Webhook-Token: .*|X-Webhook-Token: ${WEBHOOK_TOKEN}|g" \
	       "$f"
done
echo "   Variables injectees dans $(ls $ACTIVE_DIR/*.yml | wc -l) regles"

# Applique un pipeline d'ingestion et verifie le code HTTP (sinon echec silencieux)
apply_pipeline() {
	local name="$1" file="$2"
	local resp_body http_code
	resp_body="$(mktemp)"
	http_code=$(curl -s -o "$resp_body" -w "%{http_code}" -X PUT \
		"http://${OPENSEARCH_HOST}:${OPENSEARCH_PORT}/_ingest/pipeline/${name}" \
		-H "Content-Type: application/json" \
		-d @"$file")
	if [ "$http_code" -lt 200 ] || [ "$http_code" -ge 300 ]; then
		echo "ERREUR pipeline ${name} (HTTP ${http_code}) :"
		cat "$resp_body"
		rm -f "$resp_body"
		exit 1
	fi
	rm -f "$resp_body"
	echo "Pipeline ${name} applique (HTTP ${http_code})"
}

# 5 Appliquer le pipeline grok (Linux auth.log)
echo "5. Application pipeline grok..."
apply_pipeline "con4mity-auth-parse" "$SCRIPT_DIR/../pipelines/pipeline-grok.json"

# 6 Appliquer le pipeline Windows (aplatissement champs ECS Winlogbeat)
echo "6. Application pipeline Windows..."
apply_pipeline "con4mity-windows-parse" "$SCRIPT_DIR/../pipelines/pipeline-windows.json"

echo ""
echo "=== Deploiement termine : $(ls $ACTIVE_DIR/*.yml | wc -l) regles actives ==="
