#!/usr/bin/env node
/**
 * test-all.mjs — Node test suite for career-ops
 *
 * Usage:
 *   node tests/test-all.mjs
 */

import { execSync } from 'child_process';
import { readFileSync, existsSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

let passed = 0;
let failed = 0;
let warnings = 0;

function pass(msg) { console.log(`  ✅ ${msg}`); passed++; }
function fail(msg) { console.log(`  ❌ ${msg}`); failed++; }
function warn(msg) { console.log(`  ⚠️  ${msg}`); warnings++; }
function run(cmd) {
  try { return execSync(cmd, { cwd: ROOT, encoding: 'utf-8', timeout: 30000 }).trim(); }
  catch { return null; }
}
function fileExists(p) { return existsSync(join(ROOT, p)); }
function readFile(p) { return readFileSync(join(ROOT, p), 'utf-8'); }

console.log('\n🧪 career-ops node test suite\n');

// ── 1. SYNTAX CHECKS ────────────────────────────────────────────

console.log('1. Syntax checks');

const mjsFiles = readdirSync(join(ROOT, 'bin')).filter(f => f.endsWith('.mjs'));
for (const f of mjsFiles) {
  const result = run(`node --check bin/${f}`);
  if (result !== null) pass(`bin/${f} syntax OK`);
  else fail(`bin/${f} has syntax errors`);
}

const scanMjs = join(ROOT, 'skills/scan/bin/scan.mjs');
if (existsSync(scanMjs)) {
  const result = run('node --check skills/scan/bin/scan.mjs');
  if (result !== null) pass('skills/scan/bin/scan.mjs syntax OK');
  else fail('skills/scan/bin/scan.mjs has syntax errors');
}

// ── 2. REQUIRED FILES ───────────────────────────────────────────

console.log('\n2. Required files');

const required = [
  'CLAUDE.md', 'DATA_CONTRACT.md', 'STYLEGUIDE.md',
  'templates/_profile.template.md', 'templates/states.yml',
  'templates/cv-template.html', 'templates/cv-template.tex',
  'templates/applications.template.md',
  '.claude-plugin/plugin.json',
  'skills/scan/bin/scan.py',
  'skills/scan/bin/filter.py',
  'skills/scan/SKILL.md',
];

for (const f of required) {
  if (fileExists(f)) pass(`exists: ${f}`);
  else fail(`missing: ${f}`);
}

// ── 3. PERSONAL DATA LEAK CHECK ─────────────────────────────────

console.log('\n3. Personal data leak check');

const leakPatterns = ['Santiago', 'santifer.io', 'hi@santifer.io'];
const allowedFiles = [
  'README.md', 'CONTRIBUTING.md', 'CLAUDE.md', 'GOVERNANCE.md',
  'SECURITY.md', 'SUPPORT.md', 'CODE_OF_CONDUCT.md', '.github/SECURITY.md',
  'tests/test-all.mjs',
];

let leakFound = false;
for (const pattern of leakPatterns) {
  const result = run(`git grep -n "${pattern}" -- '*.md' '*.yml' '*.mjs' '*.py' '*.json' 2>/dev/null`);
  if (result) {
    for (const line of result.split('\n')) {
      const file = line.split(':')[0];
      if (allowedFiles.some(a => file.includes(a))) continue;
      warn(`Possible personal data in ${file}: "${pattern}"`);
      leakFound = true;
    }
  }
}
if (!leakFound) pass('No personal data leaks outside allowed files');

// ── 4. ABSOLUTE PATH CHECK ──────────────────────────────────────

console.log('\n4. Absolute path check');

const absResult = run(
  `git grep -n "/Users/" -- '*.mjs' '*.sh' '*.yml' '*.py' 2>/dev/null | grep -v tests/test-all.mjs`
);
if (!absResult) pass('No hardcoded absolute paths');
else for (const line of absResult.split('\n').filter(Boolean))
  fail(`Absolute path: ${line.slice(0, 100)}`);

// ── 5. CLAUDE.md INTEGRITY ──────────────────────────────────────

console.log('\n5. CLAUDE.md integrity');

const claude = readFile('CLAUDE.md');
for (const section of [
  'Data Contract', 'Ethical Use', 'Offer Verification',
  'Canonical States', 'First Run', 'STYLEGUIDE.md',
]) {
  if (claude.includes(section)) pass(`CLAUDE.md has: ${section}`);
  else fail(`CLAUDE.md missing: ${section}`);
}

// ── SUMMARY ─────────────────────────────────────────────────────

console.log('\n' + '='.repeat(50));
console.log(`Results: ${passed} passed, ${failed} failed, ${warnings} warnings`);

if (failed > 0) { console.log('TESTS FAILED\n'); process.exit(1); }
else { console.log('All tests passed\n'); process.exit(0); }
