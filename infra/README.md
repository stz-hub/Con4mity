# Infra — Configurations des services Con4mity

Configurations centralisées de chaque CT de développement, pré-requis pour le déploiement final sur Raspberry Pi.

## Structure

- `collector/` — Fluent Bit (CT 100, Kylian) : collecte et parsing des logs
- `opensearch/` — OpenSearch (CT 101, Nikita) : stockage et indexation
- `correlator/` — Moteur de corrélation Python (CT 101, Nikita)
- `detection/` — ElastAlert2 + règles Sigma (CT 102, Jean Pierre)
- `database/` — PostgreSQL (CT 104)

Le backend et le frontend sont dans `/backend/` et `/frontend/` à la racine du repo.

## Déploiement sur Pi

À terme, toutes ces configs seront fusionnées dans un `docker-compose.yml` unique à la racine.
