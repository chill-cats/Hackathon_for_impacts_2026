// Génère src/environments/environment.ts à partir des variables FRONT_*.
//
// Angular ne lit pas les fichiers .env. Ce script fait le pont :
//   1. en local : il lit le `.env` situé à la RACINE du repo
//   2. dans Docker : le `.env` n'est pas dans le contexte de build, les valeurs
//      arrivent via process.env (build args du docker-compose.yml)
// Les variables déjà présentes dans process.env sont prioritaires.
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const rootEnvFile = resolve(root, '.env');

if (existsSync(rootEnvFile)) {
  process.loadEnvFile(rootEnvFile); // n'écrase pas les variables déjà définies
}

const environment = {
  apiUrl: process.env.FRONT_API_URL ?? '/api',
};

const target = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'environments', 'environment.ts');
mkdirSync(dirname(target), { recursive: true });
writeFileSync(
  target,
  `// FICHIER GÉNÉRÉ par scripts/generate-env.mjs - ne pas éditer (modifier le .env racine)\nexport const environment = ${JSON.stringify(environment, null, 2)} as const;\n`,
);
console.log(`[env] ${target} généré (apiUrl=${environment.apiUrl})`);
