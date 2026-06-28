# OpenSearch

Moteur de stockage et de recherche full-text. Heap configurable via `OS_JAVA_OPTS`
dans le `.env` racine (3g recommandé pour Pi 5 8 Go).
Sécurité désactivée en dev (DISABLE_SECURITY_PLUGIN=true). À activer en prod.

## Déploiement
Voir le `docker-compose.yml` à la racine du repo — service `opensearch`.

## Vérification
```bash
curl http://localhost:9200
curl http://localhost:9200/_cat/indices?v
```
