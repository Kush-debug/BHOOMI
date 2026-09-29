#!/usr/bin/env node
// Dev-only utility (Phase 9): compares every locale file in src/locales against
// en.json (the canonical schema) and reports missing/extra keys per language.
// Never runs in production and the app never depends on its exit code -
// missing keys are already handled at runtime by LanguageContext's per-key
// English fallback (with a dev console warning), this script just makes gaps
// visible up front instead of waiting to spot them in the UI.
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const localesDir = path.join(__dirname, '..', 'src', 'locales');

function flatten(obj, prefix = '') {
  const out = new Set();
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      for (const nested of flatten(v, key)) out.add(nested);
    } else {
      out.add(key);
    }
  }
  return out;
}

const files = fs.readdirSync(localesDir).filter((f) => f.endsWith('.json'));
if (!files.includes('en.json')) {
  console.error('en.json not found in src/locales - it is the canonical schema.');
  process.exit(1);
}

const enKeys = flatten(JSON.parse(fs.readFileSync(path.join(localesDir, 'en.json'), 'utf8')));

let anyGap = false;
for (const file of files) {
  if (file === 'en.json') continue;
  const lang = path.basename(file, '.json');
  const keys = flatten(JSON.parse(fs.readFileSync(path.join(localesDir, file), 'utf8')));

  const missing = [...enKeys].filter((k) => !keys.has(k)).sort();
  const extra = [...keys].filter((k) => !enKeys.has(k)).sort();

  if (missing.length === 0 && extra.length === 0) {
    console.log(`[i18n] ${lang}: OK (${keys.size} keys, matches en.json)`);
    continue;
  }
  anyGap = true;
  console.log(`[i18n] ${lang}: ${keys.size} keys (en.json has ${enKeys.size})`);
  if (missing.length) {
    console.log(`  missing (${missing.length}):`);
    missing.forEach((k) => console.log(`    - ${k}`));
  }
  if (extra.length) {
    console.log(`  extra / unused elsewhere (${extra.length}):`);
    extra.forEach((k) => console.log(`    + ${k}`));
  }
}

if (!anyGap) {
  console.log('\nAll locale files match the en.json schema.');
}
