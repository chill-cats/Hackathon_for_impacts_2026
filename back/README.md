# Back

Technologie à définir. Quand elle sera choisie :

1. Ajouter ici le code et un `Dockerfile` (le service `back` de `docker-compose.yml` le construit depuis ce dossier).
2. Vérifier que l'appli écoute sur le port `BACK_PORT` (variable du `.env` racine) et lit sa config via les variables d'environnement (`DB_HOST`, `MYSQL_DATABASE`, ...).
3. Exposer ses routes sous le préfixe `/api` (le nginx du front y redirige les appels).
4. Lancer : `docker compose --profile back up -d --build`.
