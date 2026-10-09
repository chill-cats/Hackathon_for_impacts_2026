# Hackathon Lallemand

```
.
├── frontend/            Angular 22 (front only, pnpm)
├── backend/             Backend (techno à définir)
├── docker-compose.yml   Lance toute la stack (commenté, à lire !)
├── .env.example         Modèle des variables d'environnement (front + back + docker)
└── .env                 Tes valeurs locales (non commité)
```

## Démarrage

```bash
cp .env.example .env          # 1 fois, puis ajuster les valeurs

# Option A - tout avec Docker (comme en production)
docker compose up -d --build  # front sur http://localhost:8080

# Option B - dev front avec rechargement à chaud
cd frontend && pnpm install && pnpm start   # http://localhost:4200
```

Quand le back existera : `docker compose --profile backend up -d --build`.

## Variables d'environnement

Un seul fichier : `.env` à la racine.
- Docker Compose et le back le lisent directement.
- Angular ne lit pas les `.env` : `frontend/scripts/generate-env.mjs` (lancé automatiquement par `pnpm start/build/test`) convertit les variables `FRONT_*` en `frontend/src/environments/environment.ts` (fichier généré, non commité).
- Tout ce qui est `FRONT_*` est public (embarqué dans le JS du navigateur) : aucun secret.

Ajouter une variable front : la déclarer `FRONT_XXX` dans `.env.example` et `.env`, l'ajouter dans `generate-env.mjs`, et dans les `args` du service `frontend` (`docker-compose.yml`) + `ARG/ENV` du `frontend/Dockerfile`.

## Déployer sur un serveur (rappel Docker)

1. Installer Docker + le plugin compose sur le serveur, cloner le repo.
2. `cp .env.example .env` et **changer les mots de passe**.
3. `docker compose --profile backend up -d --build`
4. Mise à jour : `git pull && docker compose --profile backend up -d --build`

Le front appelle `/api/...` : nginx (dans le conteneur front) redirige vers le service `backend`.
