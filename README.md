# CON4MITY

**SIEM open-source managé (modèle MSSP)** — une sonde par site collecte et stocke les logs
localement, puis pousse les événements de sécurité vers une **console centrale** à travers un
tunnel chiffré. Détection, corrélation inter-sites et supervision se font depuis un **dashboard
web unique**.

> Projet open-source à but **pédagogique**.

---

## Sommaire

- [Architecture](#architecture)
- [Stack technique](#stack-technique)
- [Démarrage rapide (stack de test)](#démarrage-rapide-stack-de-test)
- [Arborescence](#arborescence)
- [Détection (Sigma → ElastAlert2)](#détection-sigma--elastalert2)
- [Sécurité & RGPD](#sécurité--rgpd)
- [Licence](#licence)

---

## Architecture

```
   Site client (sonde Raspberry Pi)                Console centrale (Proxmox)
 ┌───────────────────────────────┐              ┌──────────────────────────────────┐
 │  Fluent Bit ──> OpenSearch     │   WireGuard  │  OpenSearch  <──  Fluent Bit      │
 │  local (rétention 90 j)        │═════════════>│  (logs sécu)                      │
 │  logship (push 1 min) ─────────┼──tunnel──────│      │                            │
 └───────────────────────────────┘   sortant    │      v                            │
                                                 │  ElastAlert2 (règles Sigma)       │
   La sonde se connecte en SORTANT               │      │  match -> webhook          │
   => aucun port ouvert chez le client           │      v                            │
                                                 │  Backend FastAPI ──> PostgreSQL   │
                                                 │      │                            │
                                                 │      v                            │
                                                 │  Dashboard web (opérateur)        │
                                                 └──────────────────────────────────┘
```

Choix assumé : **hybride local/central**. Autonomie et rétention complète des logs **chez le
client** (localité RGPD), **minimisation** (seuls les événements de sécurité remontent), et
**supervision + corrélation inter-clients centralisées**.

## Stack technique

| Brique | Techno |
|--------|--------|
| Collecte | Fluent Bit |
| Stockage / recherche | OpenSearch 2.11 |
| Détection | ElastAlert2 (règles converties depuis Sigma) |
| API + frontend | FastAPI + interface web |
| Base d'état (alertes, comptes) | PostgreSQL |
| Transport inter-sites | WireGuard |

## Démarrage rapide (stack de test)

Lance **OpenSearch + Fluent Bit + ElastAlert2** d'un seul coup :

```bash
cd infra
cp .env.example .env          # renseigne OPENSEARCH_HOST, DASHBOARD_IP/PORT, WEBHOOK_TOKEN...
sudo sysctl -w vm.max_map_count=262144      # requis par OpenSearch
docker compose -f docker-compose.test.yml --env-file .env up -d
docker compose -f docker-compose.test.yml logs -f elastalert2   # doit afficher "N regles -> webhook ..."
```

> En LXC non privilégié : pas de `ulimits: memlock` (rlimit interdit), les règles sont rendues
> dans `/tmp` (l'image ElastAlert2 tourne en non-root).

## Arborescence

| Dossier | Rôle |
|---------|------|
| `infra/collector` | Fluent Bit (collecte et parsing des logs) |
| `infra/opensearch` | OpenSearch (stockage et indexation) |
| `infra/detection` | ElastAlert2 + bibliothèque Sigma + scripts |
| `infra/docker-compose.test.yml` | Stack de test unifiée (OpenSearch + Fluent Bit + ElastAlert2) |
| `backend` | API FastAPI du dashboard |
| `frontend` | Interface web |

## Détection (Sigma → ElastAlert2)

Les règles de détection viennent de **Sigma**, converties au format ElastAlert2 dans
`infra/detection/elastalert2/rules/active/`.

Le **webhook de livraison est défini une seule fois** dans la config globale
(`elastalert2/config.yaml.template`) : URL, header `X-Webhook-Token`, payload
(`rule_name` + `severity` + `host` via `include_rule_params_in_matches`) et `realert`. Les
valeurs sensibles sont des **placeholders** (`__DASHBOARD__` / `__TOKEN__`) rendus depuis le
`.env` au démarrage — **aucun secret n'est committé**.

Conformément au schéma d'ElastAlert2, **`alert` et `index` restent obligatoires par règle** ; le
`entrypoint.sh` les **ajoute automatiquement** à tout import Sigma brut qui ne les aurait pas. Un
import de règle Sigma se câble donc tout seul, sans étape manuelle.

## Sécurité & RGPD

- **Surface d'attaque minimale** : seul WireGuard (UDP) est exposé sur Internet ; la sonde se
  connecte en sortant (aucun port ouvert côté client).
- **API protégée** : authentification JWT + allowlist IP applicative ; reverse proxy TLS (nginx).
- **Bases restreintes** : OpenSearch derrière une allowlist firewall ; `pg_hba` PostgreSQL limité
  au backend.
- **Anti-brute-force** : fail2ban (jail sshd) sur les conteneurs centraux.
- **RGPD** : rétention 90 jours (ISM), archivage automatique puis suppression, minimisation des
  données remontées au central.
- **Secrets** : en `.env` (chmod 600), hors dépôt (`.gitignore`).

## Licence

Projet pédagogique. La licence reste **à définir par l'équipe** (ajouter un fichier `LICENSE`
avant toute diffusion publique).
