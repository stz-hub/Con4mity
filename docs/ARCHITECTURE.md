# Architecture CON4MITY

Document de référence : architecture, chaîne d'alerting, sécurité, RGPD, déploiement.
SIEM open-source managé selon le **modèle MSSP** (Managed Security Service Provider) : une sonde
par site, une console centrale unique.

## 1. Vue d'ensemble

Chez chaque client, une **sonde** collecte et stocke les logs localement, puis pousse les
**événements de sécurité** vers une **console centrale** via un tunnel chiffré. La détection, la
corrélation inter-sites et la supervision sont **centralisées** sur la console.

Le parti pris est un **hybride local/central** :

- **Autonomie locale** : la sonde collecte et conserve les logs complets sur place (90 jours).
- **Minimisation** : seuls les événements de sécurité remontent au central (argument RGPD).
- **Supervision centralisée** : détection, corrélation inter-clients et dashboard au central.
- **Sécurité** : la sonde se connecte en **sortant** ⇒ aucun port ouvert chez le client.

## 2. Composants

### Console centrale

| Rôle | Techno | Indispensable |
|------|--------|---------------|
| Stockage / recherche des logs | OpenSearch 2.11 | Oui |
| Moteur de détection | ElastAlert2 (règles Sigma) | Oui |
| API + interface opérateur | FastAPI + frontend web | Oui |
| État des alertes + comptes | PostgreSQL | Oui |
| Passerelle d'ingestion centrale | Fluent Bit | Optionnel |

### Sonde de site

- **Fluent Bit** : collecteur unique, vers un OpenSearch **local** (rétention 90 j).
- **Agent de push** (cron 1 min) : pousse les événements de sécurité vers le central via le tunnel.
- **Détection locale de secours** réactivable si la sonde est coupée du central.

## 3. Chaîne d'alerting (bout en bout)

```
1. Un événement se produit (brute-force SSH, sudo suspect, kerberoasting, PowerShell suspect…)
   └─ Fluent Bit collecte → OpenSearch LOCAL de la sonde (rétention 90 j)
2. L'agent de push (cron 1 min) envoie l'événement de sécurité dans le tunnel chiffré
3. OpenSearch central reçoit l'événement (index con4mity-logs-*)
4. ElastAlert2 interroge ces logs chaque minute avec les règles Sigma
   └─ match → POST /api/webhook/alert (header X-Webhook-Token)
5. Le backend valide le token → INSERT dans PostgreSQL
6. Une corrélation périodique escalade (ex. ≥ N occurrences même règle+host / 1 h → sévérité haute)
7. Le dashboard lit PostgreSQL → l'opérateur voit l'alerte
```

La détection est **centralisée**, ce qui permet la **corrélation inter-clients** et une gestion
unifiée des règles.

## 4. Bibliothèque de règles (Sigma → ElastAlert2)

Les règles viennent de **Sigma** et sont converties au format ElastAlert2. La **logique de
détection** vient de Sigma ; la **livraison** (alerter webhook) est ajoutée par CON4MITY.

Le webhook est défini **une seule fois** dans la configuration globale d'ElastAlert2
(`http_post_url`, header `X-Webhook-Token`, payload `rule_name`/`severity`/`host` via
`include_rule_params_in_matches`, `realert`). Conformément au schéma d'ElastAlert2, **`alert` et
`index` restent obligatoires par règle** ; ils sont ajoutés automatiquement au démarrage à tout
import Sigma brut. Couverture : Linux et Windows (SSH brute force, login root, sudo/sudoers,
nouvel utilisateur, port scan, élévation de privilèges, accès fichiers sensibles, kerberoasting,
pass-the-hash, PowerShell suspect, nouvel admin, GPO modifiée, pare-feu désactivé, mouvement
latéral, périphérique USB, compte verrouillé…).

## 5. Sécurité

| Contrôle | État |
|----------|------|
| Seul le tunnel (UDP) exposé sur Internet ; sonde en sortant (0 port ouvert côté client) | ✅ |
| OpenSearch derrière une allowlist firewall puis DROP | ✅ |
| API : authentification JWT + allowlist IP applicative | ✅ |
| Reverse proxy TLS (nginx) devant le dashboard | ✅ |
| PostgreSQL : `pg_hba` restreint au backend | ✅ |
| Anti-brute-force : fail2ban (jail sshd) sur les conteneurs centraux | ✅ |
| Secrets en `.env` (chmod 600), hors dépôt | ✅ |

## 6. RGPD — cycle de vie de la donnée

1. **Collecte & rétention locale** : logs complets sur la sonde, 90 jours (policy ISM).
2. **Minimisation** : seuls les événements de sécurité remontent au central.
3. **Archivage** : export automatique avant purge, conservation 1 an, puis suppression.
4. La donnée reste **majoritairement chez le client** (localité) — argument RGPD fort.

## 7. Déploiement d'un nouveau client

1. Préparer une sonde (Fluent Bit + OpenSearch local + agent de push).
2. Générer un pair de tunnel (clé + IP dédiée) sur le hub central.
3. Déposer la configuration du pair sur la sonde → le tunnel monte en sortant.
4. L'agent pousse vers `con4mity-logs-<client>-*` avec un identifiant client unique.
5. Les règles centrales s'appliquent immédiatement ; rien à configurer côté détection.
6. (Parc) : déployer Fluent Bit par GPO/Ansible sur les endpoints → ils expédient vers la sonde du site.

## 8. Décisions d'architecture

- **Fluent Bit partout** (sonde + endpoints) : collecteur unique, natif OpenSearch, Linux + Windows.
- **Détection centralisée** (plutôt que par sonde) : corrélation inter-clients, gestion unifiée des
  règles, console unique.
- **Hybride local/central** (plutôt que tout-centralisé) : meilleur compromis localité RGPD /
  sécurité (sortant-only) / résilience / corrélation.
