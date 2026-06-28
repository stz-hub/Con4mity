#!/bin/bash

# Conversion des règles Sigma vers ElastAlert2

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SIGMA_LIB="$SCRIPT_DIR/../sigma-library"
ACTIVE_DIR="$SCRIPT_DIR/../elastalert2/rules/active"

mkdir -p "$ACTIVE_DIR"

for profile in linux/ windows/pme-simple windows/pme-moyenne; do
	echo "Conversion $profile..."
	for f in "$SIGMA_LIB/$profile"/*.yml; do
		filename=$(basename "$f")
		sigma convert -t elastalert --without-pipeline \
			-o "$ACTIVE_DIR/$filename" "$f" 2>/dev/null \
			&& echo "  OK: $filename" \
			|| echo "  IGNORE: $filename"
	 done
done
echo "Termine: $(ls $ACTIVE_DIR/*.yml | wc -l) regles generees"

bash "$SCRIPT_DIR/fix_severity.sh"
bash "$SCRIPT_DIR/add_frequency.sh"
