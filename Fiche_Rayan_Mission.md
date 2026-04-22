# CON4MITY — Fiche Rayan · Dashboard & Backend

## C'est quoi ton rôle

Tu développes l'interface finale du SIEM — ce que le client verra et utilisera au quotidien. L'objectif c'est une interface web claire, accessible sans expertise cyber, qui centralise les logs et les alertes en un seul endroit.

Le projet fonctionne comme ça :

```
Sources PME (Windows / Linux / Switches)
        ↓
Filebeat (Kylian) — collecte les logs
        ↓
OpenSearch (Nikita) — stocke et indexe les logs
        ↓
ElastAlert (JP) — détecte les anomalies → écrit les alertes dans PostgreSQL
        ↓
Ton backend FastAPI — interroge OpenSearch + PostgreSQL
        ↓
Ton dashboard — affiche tout ça dans le navigateur du client
```

Tu es le dernier maillon — celui que le client voit.

---

## Tes accès

### Proxmox (interface de gestion des serveurs)
- URL : `https://con4mity.duckdns.org:33000`
- Login : `rayan` ou `rayan@pve` — choisir **pve** dans le menu Realm
- Mot de passe : `Rayan@@`
- Depuis Proxmox tu cliques sur CT 103 → Console pour avoir un terminal

### VS Code dans le navigateur (code-server)
- URL : `http://con4mity.duckdns.org:33003`
- Mot de passe : `1420eb98958d1815a0eab039`
- C'est VS Code complet dans ton navigateur, connecté directement à ton CT 103
- Tu codes ici, tu vois tes fichiers, tu ouvres un terminal — tout au même endroit

### OpenSearch Dashboards (interface temporaire pour voir les logs)
- URL : `http://con4mity.duckdns.org:33004`
- Pas de mot de passe (sécurité désactivée en dev)
- C'est une interface préfaite pour visualiser les logs pendant que tu développes ton vrai dashboard

### Ton backend FastAPI (déjà lancé)
- URL externe : `http://con4mity.duckdns.org:33005`
- URL interne : `http://192.168.0.103:8000`
- Tourne en arrière-plan dans le CT 103

---

## Ton CT (CT 103)

- IP : `192.168.0.103`
- Système : Debian 12
- Dossier projet : `/opt/con4mity/`
- Backend : `/opt/con4mity/backend/main.py`
- Frontend : `/opt/con4mity/frontend/`

---

## Les bases de données que tu interroges

### OpenSearch — les logs bruts
- URL : `http://192.168.0.101:9200`
- Index : `con4mity-logs-*` (un index par jour, ex: `con4mity-logs-2026.04.17`)
- Pas d'authentification en dev
- C'est là que sont stockés tous les logs des machines de la PME

### PostgreSQL — les alertes et utilisateurs
- Host : `192.168.0.104`
- Port : `5432`
- Base : `con4mity`
- User : `con4mity`
- Mot de passe : `Con4mity2024`

**Tables disponibles :**

```sql
-- Alertes générées par ElastAlert (Jean Pierre)
alerts (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ,
    rule_name VARCHAR(255),   -- nom de la règle qui a détecté
    severity VARCHAR(20),     -- critical / high / medium / low
    host VARCHAR(255),        -- machine concernée
    description TEXT,         -- détail de l'alerte
    status VARCHAR(20),       -- new / in_progress / resolved
    log_ids JSONB             -- IDs des logs liés
)

-- Utilisateurs du dashboard
users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100),
    password_hash TEXT,       -- mot de passe hashé bcrypt
    role VARCHAR(20)          -- admin / analyst / reader
)

-- Règles de détection
rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    severity VARCHAR(20),
    enabled BOOLEAN,
    sigma_yaml TEXT
)

-- Sources surveillées
sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    type VARCHAR(50),         -- windows / linux / switch
    ip INET,
    enabled BOOLEAN,
    last_seen TIMESTAMPTZ
)
```

---

## Ce qui est déjà en place

### Backend FastAPI — `/opt/con4mity/backend/main.py`

Le fichier existe et tourne. Il a 4 endpoints basiques :

| Endpoint | Méthode | Description |
|---|---|---|
| `/` | GET | Vérifie que le backend tourne |
| `/logs` | GET | 100 derniers logs depuis OpenSearch |
| `/alerts` | GET | 50 dernières alertes depuis PostgreSQL |
| `/stats` | GET | Nombre d'alertes non traitées |

**Pour relancer le backend si besoin :**
```bash
cd /opt/con4mity/backend
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /var/log/con4mity-backend.log 2>&1 &
```

**Pour voir les logs du backend :**
```bash
tail -f /var/log/con4mity-backend.log
```

**Pour tester un endpoint :**
```bash
curl http://192.168.0.103:8000
curl http://192.168.0.103:8000/alerts
curl http://192.168.0.103:8000/logs
```

### Dépendances Python installées

```
fastapi       — le framework backend
uvicorn       — le serveur web qui fait tourner FastAPI
opensearch-py — pour interroger OpenSearch
psycopg2      — pour interroger PostgreSQL
python-jose   — pour générer les tokens JWT
passlib       — pour hasher les mots de passe
```

---

## Ce qu'il te reste à faire — dans l'ordre

### Étape 1 — Authentification JWT

**Pourquoi :** Le dashboard ne doit pas être accessible à n'importe qui. Il faut un système de login.

**Ce que c'est :** JWT (JSON Web Token) c'est un système de token — quand un utilisateur se connecte avec son username/password, le backend vérifie dans la table `users` et retourne un token signé. Ce token est ensuite envoyé dans chaque requête pour prouver que l'utilisateur est authentifié.

**Ce qu'il faut coder dans `main.py` :**
- Endpoint `POST /login` — reçoit username + password, vérifie dans PostgreSQL, retourne un JWT si correct
- Middleware d'authentification — toutes les routes `/logs`, `/alerts`, `/stats` doivent vérifier le token avant de répondre
- Hashing du mot de passe avec `passlib` — ne jamais stocker un mot de passe en clair

**Pour tester :** demander à Nikita d'insérer un utilisateur de test dans la table `users` avec un mot de passe hashé.

---

### Étape 2 — Endpoint PATCH /alerts/{id}

**Pourquoi :** Quand le client voit une alerte dans le dashboard, il doit pouvoir indiquer qu'il s'en occupe ou qu'il l'a résolue. C'est ce qu'on appelle l'acquittement.

**Ce qu'il faut coder :**
- Endpoint `PATCH /alerts/{id}` qui reçoit un nouveau statut (`new`, `in_progress`, `resolved`) et met à jour la table `alerts` dans PostgreSQL
- Ajouter un champ `updated_at` dans la requête SQL pour tracer quand c'est modifié

---

### Étape 3 — Améliorer /logs avec des filtres

**Pourquoi :** Pour l'instant `/logs` retourne 100 logs sans tri ni filtre. Le client doit pouvoir chercher par machine, par date, par niveau de sévérité.

**Ce qu'il faut coder :**
- Paramètres optionnels sur `/logs` : `?host=192.168.0.50&severity=critical&from=2026-04-01&size=50`
- Construire la requête OpenSearch dynamiquement selon les filtres reçus
- Pagination — retourner aussi le nombre total de résultats

---

### Étape 4 — Servir le frontend depuis FastAPI

**Pourquoi :** FastAPI peut servir des fichiers statiques (HTML, CSS, JS). Ça évite d'avoir un serveur web séparé.

**Ce qu'il faut coder dans `main.py` :**
```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="/opt/con4mity/frontend", html=True), name="frontend")
```

Comme ça quand quelqu'un ouvre `http://con4mity.duckdns.org:33005` il voit le dashboard, et les appels API partent vers `/logs`, `/alerts`, etc. sur le même serveur.

---

### Étape 5 — Développer le frontend

**Pourquoi :** C'est l'interface que le client verra. Elle doit être claire, simple, et fonctionnelle.

**Technologie recommandée :** HTML + CSS + JavaScript pur pour commencer — pas de framework, pas de compilation, tu édites un fichier et tu rafraîchis le navigateur.

**Fichiers à créer dans `/opt/con4mity/frontend/` :**

```
frontend/
├── index.html      — page de login
├── dashboard.html  — vue principale (logs en temps réel)
├── alerts.html     — vue des alertes avec acquittement
├── style.css       — styles communs
└── app.js          — logique JavaScript (appels API, affichage)
```

**Ce que doit faire chaque page :**

**index.html — Login**
- Formulaire username + password
- Au submit, appel `POST /login` vers l'API
- Si OK → stocker le token JWT dans `localStorage` et rediriger vers `dashboard.html`
- Si KO → afficher un message d'erreur

**dashboard.html — Vue principale**
- Afficher les derniers logs en temps réel (refresh toutes les 30 secondes)
- Compteur d'alertes actives bien visible en haut
- Tableau avec colonnes : date, machine, sévérité, message
- Lien vers la page alertes

**alerts.html — Vue des alertes**
- Liste des alertes avec : date, machine, type, sévérité, statut
- Boutons pour changer le statut (Prendre en charge / Résolu)
- Filtre par sévérité et par statut
- Couleurs selon la sévérité (rouge = critique, orange = élevé, etc.)

**Inspiration visuelle :** SentinelOne, NinjaOne, Datadog — interface sombre, chiffres clés en grand, tableaux clairs.

---

### Étape 6 — Connexion PostgreSQL robuste

**Pourquoi :** La connexion PostgreSQL actuelle peut tomber si elle reste inactive trop longtemps (timeout). Il faut gérer la reconnexion automatique.

**Solution simple :** utiliser un pool de connexions avec `psycopg2.pool.SimpleConnectionPool` au lieu d'une connexion unique.

---

## Outils utiles dans VS Code (code-server)

Dans VS Code tu peux installer des extensions directement depuis l'interface :

- **Python** — coloration syntaxique, autocomplétion pour Python
- **Prettier** — formatage automatique du code HTML/CSS/JS
- **REST Client** — tester tes endpoints API directement dans VS Code sans passer par curl

Pour ouvrir un terminal dans VS Code : `Ctrl+J` ou menu Terminal → New Terminal. Le terminal est directement dans ton CT 103 — tu peux lancer uvicorn, tester des commandes, etc.

Pour ouvrir ton dossier projet dans VS Code : File → Open Folder → `/opt/con4mity`

---

## Récap des URLs

| URL | Quoi |
|---|---|
| `http://con4mity.duckdns.org:33000` | Proxmox — gestion des serveurs |
| `http://con4mity.duckdns.org:33003` | VS Code — ton éditeur |
| `http://con4mity.duckdns.org:33004` | OpenSearch Dashboards — visualisation temporaire |
| `http://con4mity.duckdns.org:33005` | Ton backend FastAPI + ton dashboard final |

---

## En cas de problème

**Le backend ne répond plus :**
```bash
# Depuis Proxmox → Console CT 103
cd /opt/con4mity/backend
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /var/log/con4mity-backend.log 2>&1 &
```

**Vérifier que le backend tourne :**
```bash
ps aux | grep uvicorn
curl http://192.168.0.103:8000
```

**OpenSearch ne répond pas :**
```bash
curl http://192.168.0.101:9200
# Si ça ne répond pas, prévenir Nikita
```

**PostgreSQL ne répond pas :**
```bash
psql -h 192.168.0.104 -U con4mity -d con4mity -c "\dt"
# Si ça ne répond pas, prévenir Nikita
```

---

*Con4mity — OTERIA 2025–2026 · Rayan POTTERAT — Dashboard & Backend*
