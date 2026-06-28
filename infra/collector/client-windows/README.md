# Winlogbeat — postes et serveurs Windows clients

Agent natif Windows (service, pas de conteneur) qui lit les Event Logs et les
envoie vers OpenSearch, avec le pipeline d'ingestion `con4mity-windows-parse`
qui aplatit les champs ECS (`winlog.event_data.*`) vers le format attendu par
les règles ElastAlert2 (`EventID`, `LogonType`, `TargetUserName`, ...).

## Installation

1. Télécharger Winlogbeat (OSS) correspondant à OpenSearch 2.11 depuis le site Elastic.
2. Copier `winlogbeat.yml` dans le dossier d'installation.
3. Définir la variable d'environnement système `OPENSEARCH_HOST` (IP du Pi), ou
   remplacer directement `${OPENSEARCH_HOST}` dans le fichier par l'IP.
4. Installer le service (PowerShell en administrateur) :
   ```powershell
   cd "C:\Program Files\Winlogbeat"
   .\install-service-winlogbeat.ps1
   Start-Service winlogbeat
   ```
5. Appliquer le pipeline d'ingestion une fois sur OpenSearch (depuis le Pi ou un poste avec accès) :
   ```bash
   curl -X PUT "http://<IP_PI>:9200/_ingest/pipeline/con4mity-windows-parse" \
     -H "Content-Type: application/json" \
     -d @../../detection/pipelines/pipeline-windows.json
   ```
   (`deploy_rules.sh` l'applique aussi automatiquement à chaque déploiement.)

## Prérequis : politique d'audit avancée

Par défaut, Windows n'écrit **pas** tous les événements nécessaires. Sans ces
réglages, certaines règles ne se déclencheront jamais — pas une erreur du SIEM,
juste un événement jamais généré côté Windows.

Activer via `gpedit.msc` → *Configuration ordinateur → Paramètres Windows →
Paramètres de sécurité → Configuration avancée de la stratégie d'audit* :

| Catégorie d'audit | EventID généré | Règle concernée |
|---|---|---|
| Audit des événements de connexion | 4624, 4625 | rdp_brute_force, login_after_failures, lateral_movement, pass_the_hash |
| Audit de la gestion des comptes utilisateur | 4720, 4740 | new_local_user, account_lockout |
| Audit de la gestion des groupes de sécurité | 4728, 4732, 4756 | new_admin_account, privilege_group_modified |
| Audit du suivi détaillé → **Activité PNP** | 6416 | usb_device_connected (Windows 10/11 uniquement) |
| Audit des autres événements d'accès aux objets | 4698 | new_service (tâche planifiée) |

## Limité aux contrôleurs de domaine (si Active Directory)

Ces règles nécessitent Winlogbeat installé **sur le contrôleur de domaine**,
pas sur un poste de travail standard — l'événement n'existe que là :

| Règle | EventID | Audit AD requis |
|---|---|---|
| `windows_gpo_modified` | 5136, 5137, 5141 | Audit des services d'annuaire AD |
| `windows_kerberoasting` | 4769 | Audit des opérations de tickets de service Kerberos |

Pour une PME sans contrôleur de domaine (la majorité des TPE/PME ciblées par
Con4mity), ces deux règles resteront inactives — c'est attendu, pas un bug.

## Vérification

```bash
curl "http://<IP_PI>:9200/con4mity-logs-*/_search?q=EventID:4625&size=1&pretty"
```
Le document retourné doit avoir `EventID`, `LogonType` etc. en champs plats
(pas seulement sous `winlog.event_data`). Si absents : vérifier que le pipeline
`con4mity-windows-parse` est bien appliqué (`output.elasticsearch.pipeline`).
