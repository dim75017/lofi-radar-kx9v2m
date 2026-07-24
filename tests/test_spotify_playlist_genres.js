'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'spotify', 'dashboard.js'), 'utf8');
const start = source.indexOf('const PLAYLIST_GENRES=');
const end = source.indexOf('function plFiltered()', start);
assert.ok(start >= 0 && end > start, 'playlist genre resolver must remain available');

const context = {PLrows: []};
vm.runInNewContext(`${source.slice(start, end)}; this.resolve=playlistPrimaryGenre; this.available=playlistAvailableGenres;`, context);

assert.equal(context.resolve(['x', 'Lofi Girl - beats to relax/study to', '', '', 0, '', 0, '', '', '', 'Piano']), 'lofi_hip_hop');
assert.equal(context.resolve(['x', 'lofi beats', '', '', 0, '', 0, '', '', '', 'Ambient']), 'lofi_hip_hop');
assert.equal(context.resolve(['37i9dQZF1DWZeKCadgRdKQ', 'Deep Focus', '', '', 0, '', 0, '', '', '', 'Lofi / chillhop']), 'ambient');
assert.equal(context.resolve(['x', 'Peaceful Guitar', '', '', 0, '', 0, '', '', '', 'Ambient']), 'guitar');

context.PLrows.push(
  ['x', 'lofi beats', '', '', 0, '', 0, '', '', '', 'Ambient'],
  ['37i9dQZF1DWZeKCadgRdKQ', 'Deep Focus', '', '', 0, '', '', '', '', '', 'Lofi / chillhop'],
  ['y', 'Peaceful Guitar', '', '', 0, '', '', '', '', '', 'Ambient'],
);
assert.deepEqual(Array.from(context.available()), ['ambient', 'guitar', 'lofi_hip_hop'],
  'playlist filter choices are derived from every available classified genre');

for (const genre of ['Lofi hip-hop', 'Guitare / acoustic / fingerstyle', 'Ambient', 'À classifier']) {
  assert.match(source, new RegExp(`'${genre.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}'`),
    `${genre} remains paired with an emoji in artist and track genre menus`);
}
assert.match(source, /playlistAvailableGenres\(\)\.map/, 'playlist genre dropdown cannot be limited to hard-coded choices');

console.log('Spotify playlist genre resolver checks passed.');
