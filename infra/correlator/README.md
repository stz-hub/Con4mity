# Correlator — Moteur de corrélation custom

Script Python qui surveille OpenSearch toutes les 60s et détecte des patterns multi-événements.
Écrit les alertes détectées dans PostgreSQL (table alerts).

## Lancement
```bash
nohup python3 correlator.py > /var/log/correlator.log 2>&1 &
```

## Dépendances
- opensearch-py
- psycopg2-binary
