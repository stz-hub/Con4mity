# Con4mity — guide de démarrage rapide

Ce fichier résume **l’accès à l’éditeur**, **le lancement du backend + front**, le **changement de port**, et les **étapes PostgreSQL / OpenSearch** utiles. Les mots de passe et URLs sensibles restent dans **`CON4MITY_SECRETS.md`** (fichier local, à ne pas commiter).

---

## 1. Ouvrir le projet (VS Code, Cursor, code-server)

### Sur ta machine (VS Code ou Cursor)

1. Lance **Visual Studio Code** ou **Cursor**.
2. **Fichier → Ouvrir un dossier…** puis choisis le dossier du dépôt (ex. `Conf4mity` / `con4mity`).
3. Sous Windows, tu peux aussi faire **clic droit sur le dossier → Ouvrir avec Code** si l’option est installée.

### Liens utiles

- **code-server** (VS Code dans le navigateur) : URL et mot de passe documentés dans **`CON4MITY_SECRETS.md`** (ex. instance DuckDNS sur un port dédié).
- **Télécharger VS Code** : [https://code.visualstudio.com/](https://code.visualstudio.com/)
- **VS Code Web (GitHub)** : [https://vscode.dev/](https://vscode.dev/)

---

## 2. Lancer l’application (API + interface)

Le backend **FastAPI** sert à la fois l’**API** (`/api/...`) et les fichiers statiques du dossier **`frontend/`** (racine `/`). Une seule commande suffit en usage normal.

### Windows (PowerShell)

```powershell
cd backend
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Linux / Debian / Ubuntu / serveur (bash)

Sur Linux, **`python`** peut être absent : utilise **`python3`**. L’activation du **venv** est obligatoire ; sans elle, `pip` cible le Python système et tu obtiens **externally-managed-environment** (PEP 668).

```bash
cd /opt/con4mity/backend

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Si `venv` manque : `sudo apt-get install -y python3 python3-venv python3-pip`

Ouvre ensuite : **http://localhost:8001/** (ou `http://IP_DU_SERVEUR:8001/`).

### Changer le port

Remplace `8001` par le port souhaité (ex. `8080`) dans la commande `uvicorn`. Le front appelle l’API sur **la même origine** (`/api`), donc aucun changement dans les HTML n’est nécessaire.

### Variables d’environnement (rappel)

Voir **`backend/main.py`** : `PG_*`, `OS_*`, `JWT_SECRET`, `FRONTEND_DIR`, etc. Les valeurs de production doivent rester hors dépôt ou dans un fichier secrets local.

---

## 3. Normalisation des logs (syslog / ECS)

Le module **`backend/log_normalization.py`** déduit pour chaque document OpenSearch :

- **`con4mity_ui_host`** — depuis `host.name`, champs connus, ou **parsing de lignes syslog** (`log`, `message`).
- **`con4mity_ui_severity`** — champs ECS / PRI syslog / mots-clés.
- **`con4mity_ui_message`** — message lisible (évite d’afficher tout le JSON brut quand c’est possible).

La route **`GET /api/logs`** renvoie des documents **enrichis** avec ces champs. Les filtres « hôte » cherchent aussi dans **`log`**, **`message`**, **`raw_message`**.

---

## 4. PostgreSQL — alertes et journal opérateur

- **Table `alerts`** : si elle n’existe pas, l’API ne peut pas servir le centre d’alertes. Créer la structure avec **`backend/sql/006_alerts_bootstrap.sql`**, puis au besoin **`001_alerts_updated_at.sql`** et **`004_alerts_status_note.sql`**. Enfin, alimenter la table (règles de détection, ETL, `INSERT` de test) — sans lignes, l’UI affiche 0 alerte mais ne doit plus renvoyer d’erreur 500.
- **Préférences interface** (thème, langue, ordre des blocs du tableau de bord) : exécuter **`backend/sql/007_user_preferences.sql`** (sinon l’API retombe sur des réponses par défaut, sans stockage).
- **Historique des actions** (page Automatisation) : exécuter **`backend/sql/003_operator_activity.sql`** sur la base (voir aussi le **README** racine).

---

## 5. Front seul (sans backend)

Tu peux ouvrir `frontend/index.html` avec un serveur statique ou **Live Server**, mais **login et données** nécessitent l’API. Pour un usage réel, lance **uvicorn** comme ci-dessus.

### API sur une autre origine

Avant `<script src="app.js">`, tu peux définir :

```html
<script>
  window.CON4MITY_API_BASE = "https://ton-serveur.example/api";
</script>
```

(Voir le commentaire en tête de **`frontend/app.js`**.)

---

## 6. Cache navigateur

Après modification de **`style.css`** ou des scripts, force un rechargement (**Ctrl+Shift+R**) ou incrémente les paramètres **`?v=`** dans les balises `<link>` / `<script>` des pages HTML.

---

## 7. Documentation produit

Le contenu éditorial pour les utilisateurs est dans **`frontend/documentation.html`** ; la version affichée en pied de page est synchronisée avec **`frontend/footer.js`** (`DOC_VERSION`).
