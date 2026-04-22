# OpenSearch

Moteur de stockage et de recherche full-text. Heap configuré à 3 Go pour Pi 5 8 Go.
Sécurité désactivée en dev (DISABLE_SECURITY_PLUGIN=true). À activer en prod.

## Déploiement
```bash
docker-compose up -d
```

## Vérification
```bash
curl http://localhost:9200
curl http://localhost:9200/_cat/indices?v
```
