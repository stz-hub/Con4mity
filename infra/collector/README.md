# Collector — Fluent Bit

Collecte les logs système Linux (auth.log, syslog, kern.log), les parse avec syslog-rfc3164,
les enrichit avec hostname/severity/category et les envoie vers OpenSearch en index `con4mity-logs-*`.

| Dossier | Rôle |
|---------|------|
| `pi/` | Tourne sur la machine SIEM — auto-monitoring + écoute UDP 514 (réseau) + TCP 24224 (clients Linux). Lancé via le docker-compose racine. |
| `client/` | À déployer sur chaque poste Linux client de la PME — lit `/var/log` local et forward vers le Pi. |
| `client-windows/` | Winlogbeat, à déployer sur les postes/serveurs Windows clients (service natif, pas Docker). |

## Déploiement (machine SIEM)
Voir le `docker-compose.yml` à la racine du repo — le service `fluentbit` y est déjà configuré avec `infra/collector/pi/`.

## Vérification
```bash
docker compose logs -f fluentbit
curl http://OPENSEARCH_HOST:9200/_cat/indices?v
```
