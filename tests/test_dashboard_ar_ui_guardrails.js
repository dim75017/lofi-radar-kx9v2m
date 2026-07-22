'use strict';

const fs = require('fs');
const assert = require('assert');

const source = fs.readFileSync('spotify/dashboard.js', 'utf8');

function functionBody(name, nextName) {
  const startToken = `function ${name}(`;
  const start = source.indexOf(startToken);
  assert(start >= 0, `${name} must exist`);
  const end = nextName ? source.indexOf(`function ${nextName}(`, start + startToken.length) : source.length;
  assert(end > start, `${name} body boundary must exist`);
  return source.slice(start, end);
}

const radar = functionBody('renderRadar', 'renderWatch');
const allTracks = functionBody('renderOpps', 'renderArtists');

assert(radar.includes('Découverte quotidienne par playlists éditoriales'), 'A&R view must explain the live discovery loop');
assert(!radar.includes('search-wrap'), 'A&R view must not contain the removed search bar');
assert(!radar.includes('analytics-kpis'), 'A&R view must not restore the removed top KPI block');
assert(!radar.includes('class="kpi'), 'A&R view must not restore generic KPI cards');
assert(!allTracks.includes("T('détectée')"), 'All tracks must not display the detected badge');
assert(!allTracks.includes('badge new'), 'All tracks must not display any legacy detected badge');

console.log('Spotify A&R UI guardrails passed');
