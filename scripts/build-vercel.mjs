import { copyFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, 'public');

// Vercel hosts the app's existing embedded-data snapshot. It is intentionally
// read-only: the full SMTP sender and file-backed editor remain local-only.
await mkdir(output, { recursive: true });
await copyFile(
  path.join(root, 'dashboard_snapshot.html'),
  path.join(output, 'index.html'),
);
console.log('Built protected, read-only dashboard snapshot in public/.');
