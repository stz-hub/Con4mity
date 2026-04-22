# Detection — ElastAlert2 + règles Sigma

Surveille OpenSearch toutes les minutes, déclenche des alertes sur les règles définies dans `rules/`.
Envoie les alertes vers le backend via webhook (POST /api/webhook/alert).

## Règles actuelles
- `ssh_bruteforce.yml` : 10 échecs SSH en 1 minute = alerte high

## Déploiement
```bash
docker-compose up -d
```

## Ajouter une règle
Créer un fichier `.yml` dans `rules/`, redémarrer ElastAlert.
