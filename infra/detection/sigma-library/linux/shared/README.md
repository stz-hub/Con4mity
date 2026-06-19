# Règles communes (shared)

Règles applicables à tous les profils PME.
Basées sur les logs Linux collectés par Filebeat.

## Sources de logs
- `/var/log/auth.log` : authentification SSH
- `/var/log/syslog` : système général

## Règles incluses
| Fichier | Description | Sévérité |
|---------|-------------|----------|
| ssh_brute_force.yml | Détecte les tentatives de brute force SSH | High |
| ssh_root_login.yml | Connexion directe en root via SSH | Critical |
| ssh_off_hours.yml | Connexion SSH hors horaires de bureau | Medium |
| sudo_suspect.yml | Utilisation suspecte de sudo | High |
| new_user_created.yml | Création d'un nouvel utilisateur Linux | High |
| password_edits.yml | Modification de de mot de passe | High |
| sudoers_modified.yml | Modification de /etc/sudoers | Critical |
| port_scan.yml | Scan de ports détecté | Medium |
| privilege_escalation.yml | Tentative d'escalade de privilèges | High |
| sensitive_file_access.yml | Accès à des fichiers sensibles | Medium |

## Limitations connues

### Filtrage horaire
Les règles Sigma ne supportent pas nativement les conditions basées sur des plages horaires (ex: connexions hors heures de bureau).

La règle `ssh_off_hours.yml` détecte toutes les connexions SSH réussies.
Le filtre horaire (18h-9h, weekends) est délégué au moteur de détection Python qui exploite le champ `@timestamp` de chaque événement.