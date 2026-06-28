# infra/ — composants CON4MITY

| Dossier | Rôle |
|---------|------|
| `collector/pi/` | Fluent Bit sur la machine SIEM : auto-monitoring + réception clients/réseau |
| `collector/client/` | Fluent Bit à déployer sur les postes Linux clients (forward vers le Pi) |
| `collector/client-windows/` | Winlogbeat à déployer sur les postes/serveurs Windows clients |
| `opensearch/` | OpenSearch : stockage et indexation (config de référence, voir docker-compose racine) |
| `correlator/` | Absent — à reconstruire. ElastAlert2 ne couvre pas la corrélation multi-événements (ex. échecs puis succès, création puis ajout admin) |
| `detection/` | ElastAlert2 + bibliothèque Sigma + scripts |

## Déploiement de la stack SIEM (Pi ou autre machine)

Un seul docker-compose, à la racine du repo (pas dans `infra/`) :

```bash
cp .env.example .env            # éditer les valeurs
sudo sysctl -w vm.max_map_count=262144
docker compose --env-file .env up -d
```

`collector/client/` et `collector/client-windows/` se déploient séparément, sur
les machines clientes de la PME — pas sur la machine SIEM elle-même.
La configuration (IP, token…) vient du `.env` — rien n'est codé en dur.
