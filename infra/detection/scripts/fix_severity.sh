#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ACTIVE_DIR="$SCRIPT_DIR/../elastalert2/rules/active"
SIGMA_LIB="$SCRIPT_DIR/../sigma-library"

for sigma_file in $(find "$SIGMA_LIB" -name "*.yml"); do
	filename=$(basename "$sigma_file")
	active_file="$ACTIVE_DIR/$filename"

	# Ignorer si pas de fichier converti correspondant
	[ -f "$active_file" ] || continue

	# Lire le level depuis la règle Sigma
	level=$(grep "^level:" "$sigma_file" | awk '{print $2}' | tr -d '[:space:]')

	case $level in
		critical) severity="critical" ;;
		high)     severity="high" ;;
		medium)   severity="medium" ;;
		low)      severity="low" ;;
		*)        continue ;;
	esac
	sed -i "s/severity: .*/severity: $severity/" "$active_file"
	echo "  $filename -> $severity"
done

echo "Corrections : OK"
