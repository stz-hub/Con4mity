# Con4mity — Récapitulatif & tâches pour Rayan POTTERAT

OTERIA · B3 Cybersécurité · Promo 2025–2026  
*Document généré à partir du dossier `Documents/` (référence projet + fiches équipe + guide mise en production).*

---

## 1. Récapitulatif de la situation

### Qu’est-ce que Con4mity ?

**Con4mity** est un **SIEM open source** pensé pour les **PME** : collecte des logs du réseau, stockage et indexation, analyse en temps réel, **alertes** en cas d’anomalie. Contraintes cibles : budget matériel modeste, installation rapide sur site, jusqu’à **100 utilisateurs** surveillés, **90 jours** de rétention chaude, stack **100 % open source**.

### Où en est le projet (avril 2026) ?

D’après la documentation, l’avancement global est estimé à **~30 %**. Beaucoup d’**infrastructure** est prête ; les briques **métier** (collecte complète, détection, interface) sont encore en cours ou à finaliser.

| Déjà en place | Manque encore (global) |
|---------------|-------------------------|
| Proxmox, CTs, Docker sur les CTs, réseau 192.168.0.0/24 | Filebeat / pipeline collecte opérationnel de bout en bout |
| OpenSearch 2.11 (CT 101), template d’index, politique 90 j | ElastAlert2 + règles Sigma calibrées |
| PostgreSQL (CT 104), tables `alerts`, `rules`, `users`, `sources` | **Dashboard + backend FastAPI** (ta brique) |
| Accès inter-CTs | Sécurisation prod : auth OpenSearch, TLS, ufw, secrets `.env`, etc. |

**Objectif livrable** : **MVP sur Raspberry Pi 5** — **fin avril 2026**.

### Ton rôle dans l’équipe

Tu es **Rayan POTTERAT** : **Dashboard & backend** sur le **CT 103** (`192.168.0.103`). Tu construis **ce que le client voit** : une interface web (inspiration type SentinelOne / NinjaOne) branchée sur **OpenSearch** (logs) et **PostgreSQL** (alertes, utilisateurs, sources). **OpenSearch Dashboards** (port **5601**) n’est qu’un **outil temporaire de dev** ; la **livraison finale**, c’est **ton** dashboard (FastAPI + frontend), avec les **alertes en prod intégrées au dashboard** (pas Discord).

### Dépendances importantes pour toi

- **Nikita** : utilisateur de test dans `users` (login / mot de passe haché) pour valider `POST /login` ; éventuellement doc du schéma SQL précis ; plus tard compte OpenSearch lecture seule quand la sécurité sera activée.
- **Kylian** : logs qui arrivent dans OpenSearch (`con4mity-logs-*`) pour que `GET /logs` et `GET /stats` aient des données réelles.
- **Jean Pierre** : alertes dans PostgreSQL via ElastAlert2 pour que `GET /alerts` et le flux « acquittement » soient testables de bout en bout.

### Test d’intégration que toute l’équipe vise

**Scénario type** : générer une attaque simple (ex. **SSH brute-force** simulée) → log collecté → stocké → règle déclenchée → **alerte visible et gérable dans ton dashboard**. Tant que ce fil n’est pas vert, le projet n’est pas « démontrable » comme SIEM.

---

## 2. Tes accès utiles (CT 103)

| Information | Valeur |
|-------------|--------|
| CT Proxmox | **103** |
| IP CT | **192.168.0.103** |
| Proxmox (externe) | `https://con4mity.duckdns.org:33000` |
| Login Proxmox | `Rayan` ou `rayan@pve` (realm **pve**) |
| Mot de passe Proxmox | Rayan@@@|
| Entrer dans le CT | `pct enter 103` (depuis le shell Proxmox) |
| Dossier projet | `/opt/con4mity/` |
| OpenSearch (logs) | `http://192.168.0.101:9200` — index `con4mity-logs-*` |
| PostgreSQL | `192.168.0.104:5432` — base `con4mity` — user `con4mity` |
| API backend (cible) | port **8000** (FastAPI / Uvicorn) |
| Dashboards temporaire | port **5601** sur ton CT |

---

## 3. Liste des choses que tu as à faire (Rayan)

Coche au fur et à mesure. L’ordre suit la fiche métier ; certaines tâches peuvent se **chevaucher** (ex. backend pendant que Dashboards tourne).

### Phase A — Environnement & outil temporaire

- [ ] **A1** — Accéder au CT 103 (console Proxmox ou `pct enter 103`).
- [ ] **A2** — Créer l’arborescence : `mkdir -p /opt/con4mity` et s’y placer.
- [ ] **A3** — **Mission 1 (fiche)** : `docker-compose.yml` avec **OpenSearch Dashboards 2.11.0** (`OPENSEARCH_HOSTS=http://192.168.0.101:9200`, `DISABLE_SECURITY_DASHBOARDS_PLUGIN=true`, port **5601**), `docker-compose up -d`, vérifier `http://192.168.0.103:5601`.
- [ ] **A4** — Dans Dashboards : créer un **index pattern** `con4mity-logs-*` pour visualiser les logs (dès qu’il y a des données côté Kylian / tests).

### Phase B — Python & backend minimal

- [ ] **B1** — **Mission 2** : installer **Python 3**, **pip**, puis `fastapi`, `uvicorn`, `opensearch-py`, `psycopg2-binary` ; test `import fastapi, opensearchpy, psycopg2`.
- [ ] **B2** — **Mission 3** : dossier `/opt/con4mity/backend`, fichier `main.py` avec clients OpenSearch + PostgreSQL.
- [ ] **B3** — Implémenter **`GET /logs`** : ~100 derniers logs depuis OpenSearch, tri date décroissante.
- [ ] **B4** — Implémenter **`GET /alerts`** : alertes PostgreSQL, tri date décroissante.
- [ ] **B5** — Implémenter **`GET /stats`** : ex. logs du jour, alertes actives, machines / sources les plus actives (adapter au schéma réel des documents / tables).
- [ ] **B6** — Lancer avec `uvicorn main:app --host 0.0.0.0 --port 8000` (et `--reload` en dev) ; tester avec `curl` depuis le CT.

### Phase C — Authentification

- [ ] **C1** — **Mission 4** : `python-jose`, `passlib` (ou équivalent validé par le cours) pour **JWT** et vérification mot de passe vs `users.password_hash`.
- [ ] **C2** — **`POST /login`** : vérif username / mot de passe → retour **JWT**.
- [ ] **C3** — Protéger **`/logs`**, **`/alerts`**, **`/stats`** : sans JWT valide → **401**.
- [ ] **C4** — **Coordination Nikita** : obtenir un **utilisateur de test** inséré dans `users` ; tester login + accès protégés.

### Phase D — Frontend (interface client)

- [ ] **D1** — **Mission 5** : dossier `frontend` sous `/opt/con4mity/` (ou servi par FastAPI en static).
- [ ] **D2** — **Page login** : formulaire → `/login` → stockage token (ex. `localStorage`).
- [ ] **D3** — **Page principale** : logs avec **refresh ~30 s**, compteur alertes actives visible, idéalement un **graphique** logs/heure.
- [ ] **D4** — **Page alertes** : colonnes (horodatage, machine, type, sévérité, statut), filtres sévérité / machine, actions de statut.
- [ ] **D5** — **Page sources** : machines surveillées, IP, dernière activité (données table `sources` + éventuellement dérivé des logs si besoin).
- [ ] **D6** — Navigation (ex. menu latéral), charte **bleu marine / blanc / accents bleu clair**, lisible et si possible **responsive**.

### Phase E — Gestion des alertes (workflow)

- [ ] **E1** — **Mission 6** : **`PATCH /alerts/{id}`** pour statuts `new` → `in_progress` → `resolved` (noms exacts à aligner avec la BDD).
- [ ] **E2** — Avec **Nikita** : si besoin, champ **`updated_at`** sur `alerts` (migration SQL) pour tracer les changements de statut.
- [ ] **E3** — Frontend : boutons / actions par alerte, **mise à jour UI** sans rechargement complet ; filtre « non résolues » (`new` / `in_progress`).

### Phase F — Fin de la brique « Dashboard Rayan »

- [ ] **F1** — **Mission 7** : vérifier que le custom couvre l’essentiel (logs, filtres/recherche raisonnable) par rapport à l’usage équipe sur Dashboards.
- [ ] **F2** — Retirer le service **OpenSearch Dashboards** du `docker-compose`, `down` / `up`, valider que tout tourne **sans** 5601.
- [ ] **F3** — **Documentation courte** : URL d’accès, comptes de test, comment relancer le service (docker / systemd si vous l’ajoutez).

### Phase G — Ce qui te concerne en « équipe / prod » (plus tard mais à anticiper)

- [ ] **G1** — **Secrets** : ne pas laisser mots de passe en dur ; préparer lecture **variables d’environnement** / **`.env`** (aligné avec le guide : `${VARIABLE}` dans compose, `.gitignore`).
- [ ] **G2** — **Pare-feu `ufw` sur le CT 103** : ouvrir uniquement ce qui doit l’être (ex. 8000 / 443 selon choix final), comme prévu pour **tous** les CTs en phase hardening.
- [ ] **G3** — **HTTPS** pour le dashboard en prod : à coordonner avec **Kylian + Nikita** (TLS, reverse proxy, certificats) quand la stack sera stabilisée.
- [ ] **G4** — Participer au **test de bout en bout** avec toute l’équipe (attaque simulée → alerte dans **ton** UI → acquittement).

---

## 4. Résumé en une phrase

**Ta mission** : livrer sur le **CT 103** un **backend FastAPI** + **frontend** qui consomment **OpenSearch** et **PostgreSQL**, avec **login JWT**, **visualisation des logs**, **liste et filtrage des alertes**, **mise à jour des statuts**, et **page sources** — puis **retirer OpenSearch Dashboards** une fois le tout validé, en restant aligné avec le **MVP fin avril 2026** et les exigences de **sécurisation** décrites dans le guide de mise en production.

---

*Con4mity — Document personnel de pilotage pour Rayan — à compléter avec les notes de réunion d’équipe.*
