import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

export const managedPaths = Object.freeze(['data/activity.json', 'assets/activity.svg']);
export const blobSha = bytes => createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex');

const headQuery = `query ActivityHead($snapshot: String!, $chart: String!) {
  repository(owner: "vighriday", name: "vighriday") {
    ref(qualifiedName: "refs/heads/main") { target { oid } }
    snapshot: object(expression: $snapshot) { ... on Blob { oid } }
    chart: object(expression: $chart) { ... on Blob { oid } }
  }
}`;
const commitMutation = `mutation PublishActivity($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) { commit { oid } }
}`;

/**
 * Commit exactly two files with an atomic expected-head check. A separate
 * read/check followed by REST update-ref is insufficient if main is reset.
 * https://docs.github.com/en/graphql/reference/commits#createcommitonbranch
 */
export async function publishActivity({ repository, token, expectedSha, files, fetchImpl = fetch }) {
  if (repository !== 'vighriday/vighriday' || typeof token !== 'string' || !token.trim() || typeof expectedSha !== 'string' || !/^[a-f0-9]{40}$/i.test(expectedSha)) throw new Error('Invalid publishing context.');
  if (!files || Array.isArray(files) || Object.keys(files).sort().join('|') !== [...managedPaths].sort().join('|')) throw new Error('Only the snapshot and activity SVG may be published.');
  if (managedPaths.some(path => typeof files[path] !== 'string' || !files[path])) throw new Error('Activity files must contain UTF-8 text.');
  expectedSha = expectedSha.toLowerCase();
  async function graphql(query, variables) {
    let response;
    try {
      response = await fetchImpl('https://api.github.com/graphql', {
        method: 'POST',
        headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28' },
        body: JSON.stringify({ query, variables }),
        redirect: 'error',
        signal: AbortSignal.timeout(30_000),
      });
    } catch {
      // Do not echo request details, a token-bearing URL, or server messages.
      throw new Error('GitHub publishing request could not be completed. No successful activity commit was confirmed.');
    }
    if (!response.ok) throw new Error(`GitHub publishing request failed: HTTP ${response.status}. No successful activity commit was confirmed.`);
    let payload;
    try { payload = await response.json(); }
    catch { throw new Error('GitHub returned an invalid publishing response. No successful activity commit was confirmed.'); }
    if (!payload || typeof payload !== 'object' || Array.isArray(payload) || payload.errors || !payload.data) {
      throw new Error('GitHub rejected the activity request. main may have changed during refresh; no successful activity commit was confirmed.');
    }
    return payload.data;
  }
  const state = (await graphql(headQuery, {
    snapshot: `${expectedSha}:${managedPaths[0]}`,
    chart: `${expectedSha}:${managedPaths[1]}`,
  })).repository;
  if (!state?.ref?.target?.oid) throw new Error('GitHub did not return the expected main branch.');
  if (state.ref.target.oid !== expectedSha) throw new Error('main changed during refresh. Refusing to publish from an outdated checkout.');
  const original = [state.snapshot?.oid, state.chart?.oid];
  if (managedPaths.every((path, index) => original[index] === blobSha(Buffer.from(files[path], 'utf8')))) return { changed: false, sha: expectedSha };
  const result = await graphql(commitMutation, { input: {
    branch: { repositoryNameWithOwner: repository, branchName: 'main' },
    expectedHeadOid: expectedSha,
    message: { headline: 'Refresh public activity snapshot' },
    fileChanges: { additions: managedPaths.map(path => ({ path, contents: Buffer.from(files[path], 'utf8').toString('base64') })) },
  } });
  const next = result.createCommitOnBranch?.commit?.oid;
  if (typeof next !== 'string' || !/^[a-f0-9]{40}$/i.test(next)) throw new Error('GitHub did not confirm the activity commit.');
  return { changed: true, sha: next };
}

async function main() {
  const files = Object.fromEntries(await Promise.all(managedPaths.map(async path => [path, await readFile(new URL(`../${path}`, import.meta.url), 'utf8')])));
  const result = await publishActivity({ repository: process.env.GITHUB_REPOSITORY, token: process.env.GH_TOKEN, expectedSha: process.env.GITHUB_SHA, files });
  console.log(result.changed ? `Published verified activity snapshot: ${result.sha}` : 'Activity snapshot is unchanged.');
}
if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) main().catch(error => { console.error(error.message); process.exitCode = 1; });
