# Redémarrer le backend Con4mity après un changement

## Sur Linux : ne pas copier les commandes Windows

Sur le serveur (Debian, Ubuntu, Raspberry Pi, CT Proxmox, etc.) :

- **Mauvais** : `.\.venv\Scripts\activate` (c’est **PowerShell / Windows**). Sous `bash` ça ne marche pas.
- **Bon** : `source .venv/bin/activate` depuis le dossier `backend/`.

`python` n’existe souvent **pas** sur Linux : utilise **`python3`**.

L’erreur **« externally-managed-environment »** (PEP 668) apparaît quand **`pip`** tourne **sans** venv actif. Il faut d’abord :

1. `cd /opt/con4mity/backend` (ou ton chemin)
2. `source .venv/bin/activate` (tu dois voir `(.venv)` au début de la ligne)
3. puis seulement `pip install -r requirements.txt` et `python3 -m uvicorn ...`

Si le dossier `.venv` n’existe pas ou est vide :

```bash
cd /opt/con4mity/backend
sudo apt-get install -y python3-venv   # si besoin
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## En développement (`--reload`)

Avec `uvicorn ... --reload`, le serveur **recharge seul** quand tu modifies un fichier Python (`backend/main.py`, etc.).  
Tu n’as **rien à redémarrer** sauf si :

- tu changes **`requirements.txt`** → réinstalle les paquets, puis relance Uvicorn ;
- le process plante → relance la commande ci-dessous.

## Recréer le venv + relancer (Linux / serveur)

À faire depuis le dossier du backend (ex. `/opt/con4mity/backend`).

```bash
# 1) Sortir d’un venv cassé / ancien
deactivate 2>/dev/null; unset VIRTUAL_ENV

cd /opt/con4mity/backend

# 2) (optionnel) tout repartir de zéro
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate

# 3) Dépendances
pip install -U pip
pip install -r requirements.txt

# 4) Lancer l’app
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Variables d’environnement (PG_*, OS_*, JWT_SECRET, etc.) : exporte-les **avant** l’étape 4, ou mets-les dans un fichier `.env` chargé par ton shell / systemd (sans commiter `.env`).

## Arrêter proprement

Dans le terminal où tourne Uvicorn : **Ctrl+C**.

Si un ancien Uvicorn tourne encore en arrière-plan sur le port 8001 :

```bash
pkill -f "uvicorn main:app"   # à ajuster si besoin
# ou, pour voir le processus : ss -tlnp | grep 8001
```

## Windows (PowerShell)

```powershell
cd chemin\vers\Con4mity\backend
deactivate 2>$null; Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue
python3 -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## Fichiers statiques (HTML / CSS / JS)

Les changements dans **`frontend/`** sont servis dès l’enregistrement.  
Un **rechargement forcé** du navigateur suffit le plus souvent : **Ctrl+Shift+R** (évite le cache).
