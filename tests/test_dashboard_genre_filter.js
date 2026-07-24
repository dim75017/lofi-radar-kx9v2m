'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'spotify', 'dashboard.js'), 'utf8');
const start = source.indexOf('const GENRE_TAXONOMY');
const end = source.indexOf('function perfHistory', start);
assert.ok(start >= 0 && end > start, 'genre filter helpers must remain defined');

const context = {};
vm.runInNewContext(`${source.slice(start, end)}; this.canonicalGenreKey=canonicalGenreKey;`, context);

for (const [input, expected] of [
  ['Ambient', 'ambient'],
  ['ambient', 'ambient'],
  ['Guitare / acoustic / fingerstyle', 'guitar'],
  ['acoustic', 'guitar'],
  ['Classique', 'classical'],
  ['classical', 'classical'],
  ['Dark ambient', 'dark_ambient'],
  ['dark_ambient', 'dark_ambient'],
  ['À classifier', 'unclassified'],
]) {
  assert.equal(context.canonicalGenreKey(input), expected, `${input} must map to ${expected}`);
}

assert.match(source, /S\.genres\.has\(canonicalGenreKey\(classification\.genre\)\)/,
  'track filtering must compare normalized genre keys');
assert.match(source, /S\.agenres\.has\(canonicalGenreKey\(classification\.genre\)\)/,
  'artist filtering must compare normalized genre keys');

console.log('Dashboard genre filter regression checks passed.');
