# Règles PME Simple

Profil ciblant les PME de 5 à 20 personnes.
Infrastructure Windows sans Active Directory.

## Caractéristiques
- Postes Windows 10/11
- Comptes utilisateurs locaux
- Pas de contrôleur de domaine
- Firewall/routeur simple

## Sources de logs
- Windows Event Logs (Security, System)
- Collecte via agent Filebeat sur chaque poste

## Règles incluses
| Fichier | Description | Sévérité | Event ID |
|---------|-------------|----------|----------|
| rdp_brute_force.yml | Brute force RDP | High | 4625 |
| login_after_failures.yml | Connexion réussie après échecs | High | 4624+4625 |
| new_local_user.yml | Création compte utilisateur local | Medium | 4720 |
| disabled_account_login.yml | Connexion avec compte désactivé | Critical | 4625 |
| defender_disabled.yml | Désactivation Windows Defender | Critical | 5001 |
| powershell_suspect.yml | Exécution PowerShell suspecte | High | 4104 |

## Déploiement
Charger shared/ + pme-simple/ sur l'appliance.