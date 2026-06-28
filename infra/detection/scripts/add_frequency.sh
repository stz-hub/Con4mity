#!/bin/bash
# Injecte les paramètres ElastAlert2 (type, num_events, timeframe, query_key, realert)
# dans les règles converties, à partir de frequency_manifest.yml.
# À exécuter après convert_rules.sh et fix_severity.sh.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ACTIVE_DIR="$SCRIPT_DIR/../elastalert2/rules/active"
MANIFEST="$SCRIPT_DIR/frequency_manifest.yml"

if ! command -v python3 &>/dev/null; then
  echo "[ERREUR] python3 requis (pip install pyyaml)"
  exit 1
fi

python3 - <<EOF
import yaml, os, sys

manifest_path = "$MANIFEST"
active_dir    = "$ACTIVE_DIR"

with open(manifest_path) as f:
    manifest = yaml.safe_load(f) or {}

ok = skip = 0
for filename, params in manifest.items():
    target = os.path.join(active_dir, filename)
    if not os.path.isfile(target):
        print(f"  SKIP (absent): {filename}")
        skip += 1
        continue
    with open(target) as f:
        rule = yaml.safe_load(f) or {}
    rule.update(params)
    with open(target, "w") as f:
        yaml.dump(rule, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    t = params.get("type", "any")
    n = params.get("num_events", "-")
    print(f"  OK: {filename}  type={t}  num_events={n}")
    ok += 1

print(f"Frequences : {ok} regles mises a jour, {skip} absentes ignorees")
EOF
