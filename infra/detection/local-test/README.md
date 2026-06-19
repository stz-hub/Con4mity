# Labo de test local — Détection (sans Proxmox)

Stack minimale pour développer/valider les règles ElastAlert2 + Sigma sans
dépendre de l'infra Proxmox (192.168.0.x).

## Contenu
- `docker-compose.yml` — OpenSearch (seul, sécurité désactivée) + ElastAlert2
- `config.yaml` — config ElastAlert pointant sur `opensearch` (nom de service)
- `rules/` — copies de test des règles (alerter `debug` au lieu du webhook prod)
- `seed_logs.ps1` — injecte de faux logs dans OpenSearch pour déclencher les règles

## Démarrage
```powershell
cd infra/detection/local-test
docker compose up -d
docker compose ps
```

Vérifier OpenSearch :
```powershell
curl http://localhost:9200
```

## Tester une règle
```powershell
.\seed_logs.ps1
docker compose logs -f elastalert
```
Au bout de ~30s, un message `Alert for SSH Brute Force Detection (local test)` doit
apparaître dans les logs ElastAlert.

## Workflow pour les nouvelles règles (11-20)
1. Écrire/copier la règle dans `rules/` avec `alert: debug`.
2. Adapter `seed_logs.ps1` (ou injecter manuellement via curl) pour générer
   le cas de test correspondant.
3. Vérifier le déclenchement ET la non-détection en situation normale.
4. Une fois validée, copier la règle finale (avec `alert: post` + webhook prod)
   dans `../rules/`.

## Arrêt / nettoyage
```powershell
docker compose down -v
```

## Dépannage
- **OpenSearch ne démarre pas (`max virtual memory areas vm.max_map_count`)** :
  exécuter `wsl -d docker-desktop sysctl -w vm.max_map_count=262144` puis relancer.
- **ElastAlert "Could not find expected index"** : attendre qu'OpenSearch soit
  `healthy` (`docker compose ps`) avant qu'ElastAlert ne démarre — déjà géré par
  `depends_on`, mais peut prendre 30-60s au premier lancement.
