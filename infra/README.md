# infra/ — composants CON4MITY

| Dossier | Rôle |
|---------|------|
| `collector/` | Fluent Bit : collecte et parsing des logs |
| `opensearch/` | OpenSearch : stockage et indexation |
| `correlator/` | Déprécié — la corrélation est assurée par ElastAlert2 |
| `detection/` | ElastAlert2 + bibliothèque Sigma + scripts |

## Stack de test (tout-en-un)

```bash
cp .env.example .env            # éditer les valeurs
sudo sysctl -w vm.max_map_count=262144
docker compose -f docker-compose.test.yml --env-file .env up -d
```

Chaque sous-dossier a aussi son propre `docker-compose.yml` pour un déploiement séparé.
La configuration (IP, token…) vient du `.env` — rien n'est codé en dur.
