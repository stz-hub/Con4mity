# Con4mity

SIEM open source : API FastAPI + interface web statique.

## Lancer en local (ou sur serveur)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Sur Linux, la commande **`python`** peut être absente hors venv : utilise toujours **`python3`** pour créer le venv, puis **`python`** ou **`python3 -m uvicorn`** une fois le venv activé.

### Si `activate` ou `uvicorn` est introuvable (venv cassé)

Le prompt `(.venv)` peut rester alors que `.venv/` a été supprimé. Faire :

```bash
deactivate 2>/dev/null; unset VIRTUAL_ENV
cd backend
rm -rf .venv
sudo apt-get install -y python3 python3-venv python3-pip   # Debian / Ubuntu si besoin
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Ouvrir **http://localhost:8001/** (connexion puis tableau de bord).

Variables utiles : `PG_*`, `OS_*`, `JWT_SECRET`, `FRONTEND_DIR` (voir `backend/main.py`).

Les documents OpenSearch hétérogènes (syslog dans `log`, ECS, etc.) sont normalisés côté API dans **`backend/log_normalization.py`** (champs `con4mity_ui_*` renvoyés par `/api/logs`). Un guide pas à pas est aussi dans **`DEMARRAGE_RAPIDE.md`**.

## Copier le projet vers une autre machine (VS Code / serveur)

Copie **tout le dossier** `frontend/` tel quel, sans oublier le sous-dossier **`assets/`** (logo).

Fichiers et dossiers attendus sous `frontend/` :

- `index.html`, `overview.html` (accueil), `logs.html`, `alerts.html`, `reports.html`, `automation.html`, `settings.html`, `documentation.html`, `dashboard.html` (redirige vers l’accueil)
- `style.css`, `app.js`, `i18n.js`, `nav.js`, `footer.js`
- **`assets/logo.png`** (obligatoire pour l’image du logo)

La **vue d’ensemble** charge **Chart.js** depuis un CDN (léger) ; le Pi doit pouvoir joindre `cdn.jsdelivr.net` une première fois, ou héberger le script en local.

Copie aussi **`backend/`** (au minimum `main.py`, `requirements.txt`, `sql/`).

### Journal d’activité / playbooks

Après déploiement, exécuter sur PostgreSQL :

`backend/sql/003_operator_activity.sql`

Sinon la page **Automatisation** affiche un historique vide et les enregistrements d’actions peuvent renvoyer 503.

Après mise à jour du front : rechargement forcé du navigateur (**Ctrl+Shift+R**) ou nouvelle version des URLs (`?v=…` dans les pages).

### Documentation client (à maintenir avec le produit)

Fichier **`frontend/documentation.html`** (contenu FR / EN / ES + journal des mises à jour). À chaque évolution notable de l’interface ou de l’API :

1. Mettre à jour le texte dans **les trois** blocs `data-doc-lang` (fr, en, es).
2. Incrémenter la version dans le **commentaire en tête du fichier**, l’attribut **`data-doc-version`** sur `<body>`, la ligne **« Journal des mises à jour »** dans chaque langue, et la constante **`DOC_VERSION`** dans **`frontend/footer.js`** (affichée en pied de page).

Le lien **Documentation** en bas de chaque page pointe vers ce fichier.
