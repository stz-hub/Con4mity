# CON4MITY — SIEM open-source (modèle MSSP)

CON4MITY est un SIEM auto-hébergé pensé pour la supervision de sécurité de PME, sur un
**modèle MSSP** : une **sonde** collecte et stocke les logs chez chaque client, puis pousse
les événements de sécurité vers une **console centrale** à travers un tunnel chiffré. Un
opérateur supervise tous les sites depuis un **dashboard web unique**.

## Architecture

```
Sondes / endpoints ──(Fluent Bit)──> OpenSearch ──> ElastAlert2 (règles Sigma)
                                          │                 │ match → webhook
                                          ▼                 ▼
                                     Dashboard (FastAPI) ◀── PostgreSQL (alertes)
```

- **Collecte** : Fluent Bit (Linux & Windows) → OpenSearch.
- **Stockage / recherche** : OpenSearch 2.11 (rétention via ISM).
- **Détection / corrélation** : ElastAlert2 sur des règles Sigma converties.
- **Console** : backend FastAPI (API + auth JWT) + frontend statique.
- **État des alertes** : PostgreSQL.

## Arborescence

| Dossier | Rôle |
|---------|------|
| `infra/collector` | Fluent Bit (collecte et parsing des logs) |
| `infra/opensearch` | OpenSearch (stockage et indexation) |
| `infra/detection` | ElastAlert2 + bibliothèque Sigma + scripts de déploiement |
| `infra/correlator` | Déprécié (corrélation assurée par ElastAlert2) |
| `backend` | API FastAPI du dashboard |
| `frontend` | Interface web |

## Démarrage rapide (stack de test)

Lance OpenSearch + Fluent Bit + ElastAlert2 d'un seul coup :

```bash
cd infra
cp .env.example .env            # renseigne OPENSEARCH_HOST, DASHBOARD_IP, WEBHOOK_TOKEN…
sudo sysctl -w vm.max_map_count=262144
docker compose -f docker-compose.test.yml --env-file .env up -d
docker compose -f docker-compose.test.yml logs -f elastalert2
```

## Règles de détection

Les règles Sigma vivent dans `infra/detection/sigma-library` (profils Linux / Windows).
Elles sont converties vers ElastAlert2 et reçoivent automatiquement l'alerter CON4MITY
(webhook + sévérité dérivée du niveau Sigma) :

```bash
bash infra/detection/scripts/convert_rules.sh      # Sigma → règles actives + alerter
bash infra/detection/scripts/deploy_rules.sh       # rend depuis .env et applique
```

## Configuration & sécurité

- Toute la configuration sensible (IP, hôtes, **token webhook**, secrets) passe par des
  fichiers `.env` **non versionnés** (voir `*.env.example`). Ne jamais committer de `.env`.
- Les règles versionnées utilisent des **placeholders** (`__DASHBOARD__`, `__TOKEN__`)
  substitués au déploiement — aucun secret dans le dépôt.
- En production : un secret distinct par service, l'authentification activée sur OpenSearch,
  et le dashboard derrière TLS.

## Licence

Projet open-source à but pédagogique.
