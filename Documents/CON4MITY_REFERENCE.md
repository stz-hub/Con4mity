# CON4MITY — Référence complète du projet

## Présentation

Con4mity est un SIEM (Security Information and Event Management) open source développé pour les PME. C'est un système qui collecte les logs de toutes les machines d'un réseau, les stocke, les analyse en temps réel, et déclenche des alertes quand quelque chose d'anormal est détecté.

**Objectifs :**
- Moins de 500 € de matériel
- Installation réalisée par notre équipe en moins de 30 minutes sur site
- Jusqu'à 100 utilisateurs surveillés
- 90 jours de rétention des logs
- 100 % open source, zéro licence

**Contexte :** Projet étudiant OTERIA 2025–2026. Les PME représentent 43 % des cibles de cyberattaques (ANSSI 2024). 330 000 attaques réussies en France en 2023. Coût moyen d'un incident : 58 600 €. Les SIEM commerciaux coûtent 15 000 à 60 000 €/an — Con4mity est la réponse open source pour les PME sans budget.

---

## Équipe

| Membre | Rôle | CT Proxmox | IP | Login Proxmox | MDP Proxmox |
|---|---|---|---|---|---|
| Nikita BELII | Chef de projet + OpenSearch + Corrélation | CT 101 | 192.168.0.101 | nikita ou nikita@pve | Con4mity2024 |
| Kylian DELOUIS | Collecte & pipeline (Filebeat) | CT 100 | 192.168.0.100 | kylian ou kylian@pve | Kylian@@ |
| Jean Pierre MIRANDA | Détection & règles Sigma | CT 102 | 192.168.0.102 | jp ou jp@pve | JeanPierre@ |
| Rayan POTTERAT | Dashboard & backend | CT 103 | 192.168.0.103 | rayan ou rayan@pve | Rayan@@ |
| BDD commune | PostgreSQL | CT 104 | 192.168.0.104 | — | con4mity / Con4mity2024 |

---

## Infrastructure

**Serveur de développement :** Dell XPS sous Proxmox 9.1.1
- Accès local : `https://192.168.0.5:8006`
- Accès externe : `https://con4mity.duckdns.org:33000`
- Duck DNS actif, IP publique : 91.160.207.142
- Accès CT depuis shell Proxmox : `pct enter XXX`

**Stockage Proxmox :**
- local : 98 Go — 8 % utilisé
- local-lvm : 365 Go — 8 % utilisé (334 Go disponibles)

**Tailles des disques CT :**
- CT 100 : 18 Go
- CT 101 : 30 Go
- CT 102 : 28 Go
- CT 103 : 18 Go
- CT 104 : 30 Go

---

## Stack technique

| Brique | Outil | Version | CT | Port |
|---|---|---|---|---|
| Collecte logs | Filebeat | 8.11.0 | CT 100 | — |
| Collecte réseau | Syslog-ng | — | CT 100 | 514 UDP |
| Stockage/indexation | OpenSearch | 2.11.0 | CT 101 | 9200 |
| BDD structurée | PostgreSQL | 15 | CT 104 | 5432 |
| Détection | ElastAlert2 | latest | CT 102 | — |
| Règles détection | Sigma | SigmaHQ | CT 102 | — |
| Dashboard temporaire | OpenSearch Dashboards | 2.11.0 | CT 103 | 5601 |
| Dashboard final | FastAPI + HTML/CSS/JS | — | CT 103 | 8000 |
| Alertes dev | Discord webhook | — | — | — |
| Alertes prod | Intégré dans le dashboard Rayan | — | — | — |
| Orchestration | Docker + Docker Compose | 20.10.24 | tous | — |

**Important :** OpenSearch Dashboards est uniquement temporaire pendant le dev. La cible finale est le dashboard custom de Rayan. Discord est uniquement pour le dev — en production les alertes seront intégrées dans le dashboard.

---

## Architecture

```
Sources PME (Windows / Linux / Switches)
        │
        ▼
[CT 100 — Kylian]
Filebeat (logs Linux/Windows) + Syslog-ng (port 514 UDP réseau)
        │
        ▼
[CT 101 — Nikita]
OpenSearch 2.11 — stockage et indexation des logs
Index : con4mity-logs-AAAA.MM.JJ
        │
        ├──────────────────────────────────────────┐
        ▼                                          ▼
[CT 102 — Jean Pierre]                    [CT 104 — BDD commune]
ElastAlert2 — surveillance continue       PostgreSQL 15
Règles Sigma — détection d'anomalies      Tables : alerts, rules, users, sources
        │                                          ▲
        └──────────────────────► alerte ──────────┘
                                                   │
                                                   ▼
                                        [CT 103 — Rayan]
                                        Backend FastAPI
                                        Dashboard web custom
```

**Philosophie Pi final :**
- Pi 5 = cerveau (collecte + analyse + détection + dashboard)
- Mini-PC Debian 12 = mémoire (stockage long terme, disque chiffré LUKS)
- Les deux sur un VLAN dédié, inaccessible depuis les postes utilisateurs

---

## Configuration OpenSearch (CT 101)

**Fichier :** `/opt/con4mity/docker-compose.yml`

```yaml
version: '3.8'
services:
  opensearch:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - discovery.type=single-node
      - OPENSEARCH_JAVA_OPTS=-Xms3g -Xmx3g   # Pi 5 8 Go → 3 Go heap
      - DISABLE_SECURITY_PLUGIN=true          # À désactiver en prod
    ports:
      - "9200:9200"
    volumes:
      - opensearch-data:/usr/share/opensearch/data
    restart: unless-stopped

volumes:
  opensearch-data:
```

**État actuel :**
- OpenSearch tourne et répond sur `http://192.168.0.101:9200`
- Index template `con4mity-logs-*` créé avec les champs : `received_at`, `host`, `severity`, `source`, `raw_message`
- Politique ISM (rétention) : suppression automatique après 90 jours
- Heap actuel : 1 Go (à monter à 3 Go pour le Pi 5)

**Vérification :**
```bash
curl http://192.168.0.101:9200
curl http://192.168.0.101:9200/_cat/indices?v
```

---

## Configuration PostgreSQL (CT 104)

**Installé directement sur le système (pas Docker)**

- Host : 192.168.0.104
- Port : 5432
- Base : con4mity
- User : con4mity
- MDP : Con4mity2024
- Accessible depuis tout le réseau 192.168.0.0/24

**Tables créées :**

```sql
-- Alertes générées par ElastAlert
alerts (id, created_at, rule_name, severity, host, description, status, log_ids JSONB)

-- Règles de détection
rules (id, name, severity, enabled, sigma_yaml)

-- Utilisateurs du dashboard
users (id, username, password_hash, role)

-- Sources surveillées
sources (id, name, type, ip, enabled, last_seen)
```

**Connexion depuis un CT :**
```bash
psql -h 192.168.0.104 -U con4mity -d con4mity
```

---

## Mission Kylian — Collecte & Pipeline (CT 100)

**Rôle :** Premier maillon de la chaîne. S'assurer que les logs de toutes les machines de la PME arrivent proprement sur le Pi.

**Outils :**
- **Filebeat 8.11.0** : lit les logs Linux/Windows, filtre à la source (10-15 % du volume brut), envoie vers OpenSearch
- **Syslog-ng** : reçoit les logs réseau (switches, routeurs) sur le port 514 UDP
- **Winlogbeat** : agent à installer sur les postes Windows clients

**Docker installé :** oui

**Structure à créer :**
```
/opt/con4mity/
├── docker-compose.yml
└── config/
    └── filebeat.yml
```

**filebeat.yml :**
```yaml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/*.log
      - /var/log/syslog
    fields:
      source_type: linux

  - type: udp
    enabled: true
    host: "0.0.0.0:514"
    fields:
      source_type: syslog_network

output.elasticsearch:
  hosts: ["http://192.168.0.101:9200"]
  index: "con4mity-logs-%{+yyyy.MM.dd}"

logging.level: info
```

**docker-compose.yml :**
```yaml
version: '3.8'
services:
  filebeat:
    image: elastic/filebeat:8.11.0
    volumes:
      - ./config/filebeat.yml:/usr/share/filebeat/filebeat.yml
      - /var/log:/var/log:ro
    ports:
      - "514:514/udp"
    restart: unless-stopped
    mem_limit: 256m
```

**Missions :**
1. Créer la structure `/opt/con4mity/config/`
2. Créer `filebeat.yml` — pointer vers `192.168.0.101:9200`
3. Créer `docker-compose.yml` — Filebeat + port 514 UDP
4. Lancer avec `docker-compose up -d` et vérifier les logs
5. Valider que les index `con4mity-logs-*` apparaissent dans OpenSearch
6. Configurer Winlogbeat sur une machine Windows de test
7. Documenter dans un `README.md`

---

## Mission Nikita — OpenSearch + Corrélation + PostgreSQL (CT 101)

**Rôle :** Cerveau du système. Tout passe par OpenSearch. Chef de projet.

**Outils :**
- **OpenSearch 2.11** : moteur de stockage et de recherche des logs
- **ISM** : gestion du cycle de vie des index (rétention 90 jours)
- **PostgreSQL 15** : BDD structurée commune (CT 104)
- **Docker**

**Ce qui est déjà en place :**
- OpenSearch tourne sur CT 101 port 9200 ✅
- Index template `con4mity-logs-*` créé ✅
- Politique ISM 90 jours créée ✅
- PostgreSQL installé sur CT 104 ✅
- 4 tables créées ✅
- Accès réseau PostgreSQL ouvert à 192.168.0.0/24 ✅

**Missions restantes :**
1. Monter le heap OpenSearch de 1g à 3g (Pi 5 8 Go) — modifier `OPENSEARCH_JAVA_OPTS=-Xms3g -Xmx3g`
2. Créer les utilisateurs OpenSearch par membre (lecture seule / écriture seule)
3. Insérer un utilisateur de test dans la table `users` pour que Rayan puisse tester son login
4. Développer le moteur de corrélation (agrégations OpenSearch → alertes PostgreSQL)
5. Monitorer les ressources : `curl http://localhost:9200/_nodes/stats/jvm?pretty`

**Moteur de corrélation :** détecter des patterns sur plusieurs événements liés. Exemple : 3 échecs SSH + 1 succès en 5 minutes sur le même host = compromission probable. Utiliser les agrégations OpenSearch et écrire les résultats dans la table `alerts` de PostgreSQL.

---

## Mission Jean Pierre — Détection & Règles Sigma (CT 102)

**Rôle :** Expert sécurité. Définir ce qui est dangereux, écrire les règles, configurer ElastAlert2.

**Outils :**
- **ElastAlert2** : surveille OpenSearch toutes les minutes, déclenche une alerte dès qu'une règle matche
- **Sigma** : format standard de règles de détection SIEM. Dépôt officiel : `github.com/SigmaHQ/sigma`
- **Discord webhook** : alertes pendant le dev uniquement

**IMPORTANT :** Ne pas importer tout le dépôt Sigma en bloc. Chaque règle doit être lue, comprise, testée et adaptée au contexte PME. Certaines règles génèrent des faux positifs (ex : connexion SSH le week-end par un IT en maintenance → pas une attaque).

**Docker installé :** oui

**Structure à créer :**
```
/opt/con4mity/
├── docker-compose.yml
├── rules/
│   ├── ssh_brute_force.yml
│   ├── rdp_brute_force.yml
│   └── ...
└── config/
    └── elastalert.yml
```

**elastalert.yml :**
```yaml
es_host: 192.168.0.101
es_port: 9200
rules_folder: /opt/elastalert/rules
run_every:
  minutes: 1
buffer_time:
  minutes: 15
alert_time_limit:
  days: 2
writeback_index: elastalert_status
```

**docker-compose.yml :**
```yaml
version: '3.8'
services:
  elastalert:
    image: jertel/elastalert2:latest
    volumes:
      - ./rules:/opt/elastalert/rules
      - ./config/elastalert.yml:/opt/elastalert/config.yml
    restart: unless-stopped
```

**20 règles prioritaires :**
1. SSH brute-force : plus de 10 tentatives échouées en 60 secondes
2. RDP brute-force : plus de 5 tentatives sur le port 3389 en 60 secondes
3. Scan de ports : plus de 20 connexions vers des ports différents en 30 secondes
4. Connexion depuis une nouvelle IP jamais vue
5. Multiples échecs Windows (Event ID 4625) : plus de 5 en 2 minutes
6. Escalade de privilèges Linux : sudo par un utilisateur qui ne l'a jamais utilisé
7. Accès aux fichiers sensibles : /etc/passwd, /etc/shadow, /etc/sudoers
8. Création d'un nouvel utilisateur Linux
9. Connexion root directe en SSH
10. Transfert de données important sortant
11-20 : à sélectionner depuis SigmaHQ en fonction du contexte PME

**Missions :**
1. Créer la structure `/opt/con4mity/rules/` et `/opt/con4mity/config/`
2. Créer `elastalert.yml`
3. Créer `docker-compose.yml`
4. Écrire et tester la règle SSH brute-force en premier
5. Lancer ElastAlert2 et vérifier la connexion à OpenSearch
6. Écrire les 20+ règles et tester chacune
7. Documenter dans `REGLES.md` — pour chaque règle : ce qu'elle détecte, faux positifs possibles, comment la désactiver

---

## Mission Rayan — Dashboard & Backend (CT 103)

**Rôle :** Interface finale du SIEM. Ce que le client verra et utilisera.

**Outils :**
- **OpenSearch Dashboards 2.11** : interface temporaire pendant le dev (port 5601)
- **FastAPI (Python)** : backend custom — API REST entre les bases et le frontend
- **opensearch-py** : client Python pour OpenSearch (`pip3 install opensearch-py`)
- **psycopg2** : client Python pour PostgreSQL (`pip3 install psycopg2-binary`)
- **Frontend HTML/CSS/JS** : interface web custom (ou React/Vue)

**Docker installé :** oui

**Connexions backend :**
- OpenSearch : `http://192.168.0.101:9200` — index `con4mity-logs-*`
- PostgreSQL : `192.168.0.104:5432` — base `con4mity` — user `con4mity` / `Con4mity2024`

**OpenSearch Dashboards temporaire (docker-compose.yml) :**
```yaml
version: '3.8'
services:
  dashboards:
    image: opensearchproject/opensearch-dashboards:2.11.0
    environment:
      - OPENSEARCH_HOSTS=http://192.168.0.101:9200
      - DISABLE_SECURITY_DASHBOARDS_PLUGIN=true
    ports:
      - "5601:5601"
    restart: unless-stopped
```

**Endpoints API FastAPI à développer :**
- `GET /logs` : 100 derniers logs depuis OpenSearch, triés par date
- `GET /alerts` : alertes depuis PostgreSQL, triées par date
- `GET /stats` : nombre de logs aujourd'hui, alertes actives, machines actives
- `POST /login` : vérification username/password dans table `users`, retourne JWT
- `PATCH /alerts/{id}` : changer le statut d'une alerte (new → in_progress → resolved)

**Interface cible (inspiration SentinelOne / NinjaOne) :**
- Page login : formulaire username/password + token JWT
- Page principale : logs en temps réel (refresh toutes les 30s), compteur alertes actives
- Page alertes : liste avec colonnes horodatage/machine/type/sévérité/statut, boutons d'acquittement, filtres
- Page sources : machines surveillées, IP, dernière activité

**Missions :**
1. Lancer OpenSearch Dashboards (outil temporaire)
2. Installer Python + FastAPI + dépendances
3. Développer le backend FastAPI de base (endpoints /logs, /alerts, /stats)
4. Ajouter l'authentification JWT
5. Développer le frontend
6. Gérer les statuts d'alertes (acquittement)
7. Remplacer OpenSearch Dashboards par le dashboard custom une fois terminé

---

## Dimensionnement — Pi 5 8 Go

| Service | RAM allouée |
|---|---|
| OpenSearch | 3 Go heap |
| Filebeat | ~150 Mo |
| ElastAlert2 | ~200 Mo |
| PostgreSQL | ~512 Mo |
| Dashboard/backend | ~512 Mo |
| OS + marge | ~500 Mo |
| **Total** | **~5 Go** |

**Capacité de stockage (1 To SSD, filtrage 10-15 %) :**

| Utilisateurs | Volume/jour | Rétention 90j |
|---|---|---|
| 10 users | ~80 Mo/j | confortable |
| 30 users | ~300 Mo/j | confortable |
| 50 users | ~600 Mo/j | confortable |
| 100 users | ~1,5 Go/j | limite recommandée |

---

## Cycle de vie des logs

| Phase | Durée | Stockage | Description |
|---|---|---|---|
| Chaud | 0 à 90 j | OpenSearch (mini-PC NFS) | Indexé, consultable, alertes actives |
| Froid | 90 j à 1 an | Archives compressées (.zst ×5) | Conformité LPM/LCEN 1 an min |
| Purge | Après 1 an | Supprimé (shred) | Conforme RGPD Art. 5 |

---

## Sécurité — État actuel et roadmap

### En place (dev)
- PostgreSQL accessible uniquement au réseau 192.168.0.0/24
- Docker installé sur tous les CTs
- ip_forward activé sur Proxmox

### À faire avant démo client (CRITIQUE)

| Action | Responsable | Priorité |
|---|---|---|
| Activer l'authentification OpenSearch (désactiver DISABLE_SECURITY_PLUGIN) | Nikita | BLOQUANT |
| TLS 1.3 + mTLS entre Filebeat et OpenSearch | Kylian + Nikita | CRITIQUE |
| Pare-feu ufw sur chaque CT | Tous | CRITIQUE |
| Fichier .env pour tous les secrets (jamais en dur dans le code) | Tous | CRITIQUE |
| Mots de passe uniques par service | Tous | CRITIQUE |
| Chiffrement LUKS AES-256 sur le mini-PC de stockage | Kylian + Nikita | IMPORTANT |
| SSH par clé uniquement sur le Pi | Kylian | IMPORTANT |
| Docker sans root (utilisateur dédié) | Nikita | IMPORTANT |
| Mises à jour automatiques Debian (unattended-upgrades) | Kylian | IMPORTANT |

### Conformité
- **RGPD** : rétention limitée (90j chaud + 1an froid), chiffrement LUKS, procédure de suppression sur demande
- **LPM/LCEN** : conservation 1 an minimum — notre politique est conforme
- **ANSSI** : principe du moindre privilège, VLAN dédié, journalisation des accès au dashboard

---

## Déploiement chez le client

### Ce que le client fournit
- Un port switch (avec support VLAN idéalement)
- Une prise électrique pour le Pi et le mini-PC
- Accès aux machines à surveiller

### Ce qu'on apporte
- Raspberry Pi 5 8 Go pré-configuré
- Mini-PC Debian 12 + SSD 1 To chiffré LUKS + NFS configuré
- Câbles réseau
- Clé USB avec scripts d'installation des agents

### Étapes d'installation sur site
1. Brancher Pi + mini-PC sur le switch
2. Configurer les IPs statiques (modifier le `.env`)
3. `docker compose up -d`
4. Installer Winlogbeat sur les postes Windows
5. Activer Syslog sur switches et routeurs
6. Vérifier que les logs arrivent dans le dashboard
7. Montrer au client comment lire les alertes

---

## docker-compose.yml final (Pi 5 — à assembler)

```yaml
version: '3.8'
services:

  filebeat:
    image: elastic/filebeat:8.11.0
    volumes:
      - ./config/filebeat.yml:/usr/share/filebeat/filebeat.yml
      - /var/log:/var/log:ro
    ports:
      - "514:514/udp"
    restart: unless-stopped
    mem_limit: 256m

  opensearch:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - discovery.type=single-node
      - OPENSEARCH_JAVA_OPTS=-Xms3g -Xmx3g
      - DISABLE_SECURITY_PLUGIN=true
    ports:
      - "9200:9200"
    volumes:
      - opensearch-data:/usr/share/opensearch/data
      - /mnt/nfs-storage:/usr/share/opensearch/data/archive
    restart: unless-stopped
    mem_limit: 4g

  elastalert:
    image: jertel/elastalert2:latest
    volumes:
      - ./rules:/opt/elastalert/rules
      - ./config/elastalert.yml:/opt/elastalert/config.yml
    restart: unless-stopped

  dashboard:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - OPENSEARCH_HOST=opensearch
      - PG_HOST=192.168.0.104
      - PG_USER=con4mity
      - PG_DB=con4mity
    restart: unless-stopped

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=con4mity
      - POSTGRES_USER=con4mity
      - POSTGRES_PASSWORD=${PG_PASSWORD}
    volumes:
      - pg-data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  opensearch-data:
  pg-data:
```

---

## Commandes utiles

### Proxmox
```bash
pct enter 100        # Entrer dans le CT de Kylian
pct enter 101        # Entrer dans le CT de Nikita
pct enter 102        # Entrer dans le CT de JP
pct enter 103        # Entrer dans le CT de Rayan
pct enter 104        # Entrer dans le CT PostgreSQL
pct status 100       # Vérifier l'état d'un CT
pct reboot 100       # Redémarrer un CT
pvesm status         # Espace disque Proxmox
```

### Docker
```bash
docker-compose up -d          # Lancer les services
docker-compose down           # Arrêter les services
docker-compose logs -f        # Voir les logs en temps réel
docker-compose ps             # État des conteneurs
docker-compose restart        # Redémarrer
```

### OpenSearch
```bash
# Vérifier qu'OpenSearch tourne
curl http://192.168.0.101:9200

# Lister les index
curl http://192.168.0.101:9200/_cat/indices?v

# Vérifier la RAM heap
curl http://192.168.0.101:9200/_nodes/stats/jvm?pretty

# Compter les documents
curl http://192.168.0.101:9200/_cat/count/con4mity-logs-*
```

### PostgreSQL
```bash
# Connexion depuis n'importe quel CT
psql -h 192.168.0.104 -U con4mity -d con4mity

# Vérifier les tables
\dt

# Voir les alertes
SELECT * FROM alerts ORDER BY created_at DESC LIMIT 10;
```

### Réseau
```bash
# Tester la connectivité entre CTs
ping 192.168.0.101    # OpenSearch
ping 192.168.0.104    # PostgreSQL

# Vérifier les ports ouverts
ss -tlnp
```

---

## Avancement global

**~30 %** — Avril 2026

| Élément | État |
|---|---|
| Analyse des besoins | ✅ Terminé |
| Choix de la stack | ✅ Terminé |
| Architecture | ✅ Validée |
| Infrastructure Proxmox | ✅ Opérationnelle |
| Docker sur tous les CTs | ✅ Installé |
| Réseau inter-CTs | ✅ Fonctionnel |
| OpenSearch + index template + ILM | ✅ Configuré |
| PostgreSQL + schéma | ✅ Configuré |
| Filebeat | 🔄 En cours (Kylian) |
| ElastAlert2 + règles Sigma | 🔄 En cours (JP) |
| Moteur de corrélation | 🔄 En cours (Nikita) |
| Dashboard + backend | 🔄 En cours (Rayan) |
| TLS + sécurisation | ⏳ À faire |
| LUKS + stockage | ⏳ À faire |
| Test sur Pi 5 | ⏳ À faire |
| Déploiement client pilote | ⏳ Objectif final |

---

## Objectif

MVP fonctionnel sur Raspberry Pi 5 — **fin avril 2026**

---

*Con4mity — OTERIA Promo 2025–2026 — Nikita BELII · Kylian DELOUIS · Jean Pierre MIRANDA · Rayan POTTERAT*
