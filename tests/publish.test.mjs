import test from 'node:test';
import assert from 'node:assert/strict';
import { publishActivity, blobSha } from '../scripts/publish-activity.mjs';

const sha = 'a'.repeat(40);
const nextSha = 'c'.repeat(40);
const files = { 'data/activity.json': '{"caption":"90 completed UTC days"}\n', 'assets/activity.svg': '<svg><title>Activity ↗</title></svg>\n' };
const options = { repository: 'vighriday/vighriday', token: 'test-only', expectedSha: sha, files };

/** Model the API's expectedHeadOid check independently of git ancestry. */
function scenario({ stale = false, unchanged = false, race, httpAt, invalidJsonAt, graphqlErrorAt, networkAt, malformedMutation = false } = {}) {
  const calls = [];
  const initial = { 'README.md': 'Personal source content\n', 'scripts/source.mjs': 'keep me\n', ...Object.fromEntries(Object.keys(files).map(path => [path, unchanged ? files[path] : `old ${path}\n`])) };
  const state = { head: stale ? 'b'.repeat(40) : sha, files: { ...initial }, commits: [] };
  let afterRace;
  async function fetchImpl(url, request) {
    const body = JSON.parse(request.body);
    const phase = body.query.trim().startsWith('mutation') ? 'mutation' : 'query';
    calls.push({ url, phase, method: request.method, body });
    assert.equal(url, 'https://api.github.com/graphql');
    assert.equal(request.redirect, 'error');
    if (networkAt === phase) throw new Error('Sensitive test-only transport details');
    if (httpAt === phase) return new Response('{}', { status: 403 });
    if (invalidJsonAt === phase) return new Response('<html>upstream failure</html>');
    if (graphqlErrorAt === phase) return Response.json({ errors: [{ message: 'Sensitive test-only server details' }] });
    if (phase === 'query') {
      assert.equal(body.variables.snapshot, `${sha}:data/activity.json`);
      assert.equal(body.variables.chart, `${sha}:assets/activity.svg`);
      const payload = { data: { repository: {
        ref: { target: { oid: state.head } },
        snapshot: { oid: blobSha(Buffer.from(initial['data/activity.json'])) },
        chart: { oid: blobSha(Buffer.from(initial['assets/activity.svg'])) },
      } } };
      if (race) {
        // A normal competing commit and a reset to an ancestor must both fail
        // the same exact-head comparison at mutation execution time.
        state.head = race === 'forward' ? 'b'.repeat(40) : 'd'.repeat(40);
        state.files['scripts/source.mjs'] = race === 'forward' ? 'new user code\n' : 'user-reset version\n';
        afterRace = { head: state.head, files: { ...state.files } };
      }
      return Response.json(payload);
    }
    const input = body.variables.input;
    if (input.expectedHeadOid !== state.head) return Response.json({ errors: [{ type: 'STALE_DATA', message: 'The branch head changed.' }] });
    if (malformedMutation) return Response.json({ data: { createCommitOnBranch: null } });
    for (const addition of input.fileChanges.additions) state.files[addition.path] = Buffer.from(addition.contents, 'base64').toString('utf8');
    state.commits.push({ parent: state.head, input });
    state.head = nextSha;
    return Response.json({ data: { createCommitOnBranch: { commit: { oid: nextSha } } } });
  }
  return { calls, fetchImpl, state, initial, afterRace: () => afterRace };
}

test('one atomic compare-and-swap commit changes exactly the two assets and preserves source code', async () => {
  const { calls, fetchImpl, state, initial } = scenario();
  assert.deepEqual(await publishActivity({ ...options, fetchImpl }), { changed: true, sha: nextSha });
  assert.equal(calls.length, 2);
  assert.equal(state.commits.length, 1);
  const input = state.commits[0].input;
  assert.equal(state.commits[0].parent, sha);
  assert.equal(input.expectedHeadOid, sha);
  assert.deepEqual(input.branch, { repositoryNameWithOwner: 'vighriday/vighriday', branchName: 'main' });
  assert.deepEqual(input.fileChanges.additions.map(file => file.path).sort(), Object.keys(files).sort());
  assert.equal(input.fileChanges.deletions, undefined);
  assert.equal(state.files['README.md'], initial['README.md']);
  assert.equal(state.files['scripts/source.mjs'], initial['scripts/source.mjs']);
  for (const path of Object.keys(files)) assert.equal(state.files[path], files[path]);
});

test('an outdated checkout is rejected before attempting a commit', async () => {
  const { calls, fetchImpl, state, initial } = scenario({ stale: true });
  await assert.rejects(publishActivity({ ...options, fetchImpl }), /outdated checkout/);
  assert.equal(calls.length, 1);
  assert.equal(state.commits.length, 0);
  assert.deepEqual(state.files, initial);
});

test('identical bytes produce no mutation or commit', async () => {
  const { calls, fetchImpl, state } = scenario({ unchanged: true });
  assert.deepEqual(await publishActivity({ ...options, fetchImpl }), { changed: false, sha });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].phase, 'query');
  assert.equal(state.commits.length, 0);
});

test('unrelated, missing and non-text files are refused before accessing the API', async () => {
  for (const invalid of [{ ...files, 'README.md': 'wrong' }, { 'data/activity.json': '{}' }, { ...files, 'assets/activity.svg': Buffer.from('<svg/>') }, { ...files, 'assets/activity.svg': '' }]) {
    const { calls, fetchImpl } = scenario();
    await assert.rejects(publishActivity({ ...options, files: invalid, fetchImpl }), /Only the snapshot|UTF-8/);
    assert.equal(calls.length, 0);
  }
});

test('repository, token and expected commit context are required before any network access', async () => {
  for (const invalid of [{ repository: 'someone/else' }, { token: '' }, { token: '  ' }, { expectedSha: 'main' }, { expectedSha: undefined }]) {
    const { calls, fetchImpl } = scenario();
    await assert.rejects(publishActivity({ ...options, ...invalid, fetchImpl }), /Invalid publishing context/);
    assert.equal(calls.length, 0);
  }
});

for (const race of ['forward', 'reset']) {
  test(`a concurrent ${race} rejects the expected head atomically and preserves the competing source changes`, async () => {
    const { calls, fetchImpl, state, afterRace } = scenario({ race });
    await assert.rejects(publishActivity({ ...options, fetchImpl }), /main may have changed/);
    assert.equal(calls.length, 2);
    assert.equal(calls[1].body.variables.input.expectedHeadOid, sha);
    assert.equal(state.commits.length, 0);
    assert.deepEqual({ head: state.head, files: state.files }, afterRace());
  });
}

for (const phase of ['query', 'mutation']) {
  for (const failure of ['httpAt', 'invalidJsonAt', 'graphqlErrorAt', 'networkAt']) {
    test(`${phase} ${failure} aborts without changing committed files or echoing credentials`, async () => {
      const { fetchImpl, state, initial } = scenario({ [failure]: phase });
      await assert.rejects(publishActivity({ ...options, fetchImpl }), error => {
        assert.doesNotMatch(error.message, /test-only|Sensitive/);
        return true;
      });
      assert.equal(state.head, sha);
      assert.equal(state.commits.length, 0);
      assert.deepEqual(state.files, initial);
    });
  }
}

test('an incomplete mutation response is not reported as a successful commit', async () => {
  const { fetchImpl, state } = scenario({ malformedMutation: true });
  await assert.rejects(publishActivity({ ...options, fetchImpl }), /did not confirm/);
  assert.equal(state.head, sha);
  assert.equal(state.commits.length, 0);
});
