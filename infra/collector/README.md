# Collector — Fluent Bit

Collecte les logs système Linux (auth.log, syslog, kern.log), les parse avec syslog-rfc3164,
les enrichit avec hostname/severity/category et les envoie vers OpenSearch en index `con4mity-logs-*`.

## Déploiement
```bash
docker-compose up -d
```

## Vérification
```bash
docker-compose logs -f fluentbit
curl http://192.168.0.101:9200/_cat/indices?v
```
