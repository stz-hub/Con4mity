# Règles PME Moyenne

Profil ciblant les PME de 20 à 100 personnes.
Infrastructure Windows avec Active Directory + serveurs Linux.

## Caractéristiques
- Postes Windows 10/11
- Windows Server + Active Directory
- Serveurs Linux (web, applicatif)
- Firewall managé

## Sources de logs
- Windows Event Logs via agent Filebeat
- Active Directory (Security logs)
- Logs Linux via Filebeat

## Règles incluses
| Fichier | Description | Sévérité | Event ID |
|---------|-------------|----------|----------|
| new_admin_account_ad.yml | Création d'un compte admin dans l'AD | Critical | 4720+4732 |
| lateral_movement.yml | Mouvement latéral détecté | High | 4624 |
| pass_the_hash.yml | Tentative de Pass-the-Hash | Critical | 4624 |
| kerberoasting.yml | Tentative de Kerberoasting | High | 4769 |
| ad_enumeration.yml | Enumération de l'Active Directory | Medium | 4661+4662 |
| gpo_modified.yml | Modification d'une GPO | High | 5136+5137+5141 |
| account_lockout.yml | Verrouillage de compte | Medium | 4740 |
| suspicious_logon_type.yml | Type de connexion inhabituel | Medium | 4624 |
| privilege_group_modified.yml | Modification d'un groupe à privilèges | Critical | 4728+4732+4756 |
| golden_ticket.yml | Tentative d'attaque Golden Ticket | Critical | 4769 |

## Déploiement
Charger linux/ + pme-simple/ + pme-moyenne/ sur l'appliance.

## Limitations connues
Les règles pass_the_hash et kerberoasting nécessitent
un audit Kerberos activé sur le contrôleur de domaine.