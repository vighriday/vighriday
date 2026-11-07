export const LENSES = Object.freeze(['problem', 'decisions', 'evidence']);
export const PROJECT_IDS = Object.freeze(['veris', 'hive', 'offside', 'pulse']);

export const PROJECTS = Object.freeze({
  veris: {
    name: 'Veris', category: 'Developer infrastructure', marker: '01', fact: '17 MCP tools + a CLI',
    description: 'A local-first behavioral diff for JavaScript and TypeScript.',
    nodes: ['Change', 'Reach', 'Evidence'],
    links: [['Source', 'https://github.com/vighriday/Veris'], ['Published package', 'https://www.npmjs.com/package/veris-core'], ['Case study', 'https://hridayvig.xyz/projects/veris']],
    views: {
      problem: { title: 'A diff shows the edit. What follows it?', copy: 'The interesting question is how a change travels, what deserves checking, and what evidence is available.', notes: ['Start with the local code change rather than asking a model to guess the whole system.', 'A resolution-aware call graph helps connect changed code with its likely reach.', 'Keep verification plans separate from evidence that a check actually happened.'] },
      decisions: { title: 'Make the reasoning inspectable.', copy: 'Connect local analysis, explicit verification plans, and recorded evidence through tools people and coding agents can inspect.', notes: ['Keep the analysis local to the JavaScript or TypeScript repository.', 'Expose the workflow through 17 MCP tools and a CLI, rather than one opaque answer.', 'Record evidence in an append-only, hash-linked ledger. A plan is not a passed test.'] },
      evidence: { title: 'Open the mechanism, not just the pitch.', copy: 'The source and published veris-core package make the implementation available for inspection.', notes: ['Read the implementation and its supported analysis paths in the source.', 'Inspect how the graph represents dependencies and where its resolution limits apply.', 'Veris records evidence and proposes checks. It does not execute your tests or certify a deployment.'] },
    },
  },
  hive: {
    name: 'HIVE', category: 'Agent security research', marker: '02', fact: 'Graph-based security prototype',
    description: 'Study unsafe capabilities that emerge between individually authorised agents.',
    nodes: ['Agents', 'Paths', 'Controls'],
    links: [['Source', 'https://github.com/vighriday/hive-agent-security'], ['Replay console', 'https://vighriday.github.io/hive-agent-security/console/'], ['Case study', 'https://hridayvig.xyz/projects/hive']],
    views: {
      problem: { title: 'Safe alone can become unsafe together.', copy: 'A permission check on one agent can miss a capability assembled through a chain of authorised interactions.', notes: ['The prototype uses fictional actors and scenarios to make the threat model inspectable.', 'Look at the relationships between agents, not only each agent in isolation.', 'Compare how simulated containment choices interrupt the capability path.'] },
      decisions: { title: 'Put the path at the centre.', copy: 'Use a graph to connect the finding, possible interventions, and the verification of those interventions.', notes: ['Represent actors and their capabilities explicitly in the model.', 'Trace the unsafe path so a finding has an explanation that can be followed.', 'Treat containment as a simulated intervention with an inspectable verification step.'] },
      evidence: { title: 'Inspect a recorded engine replay.', copy: 'The public console presents recorded engine output. It is a research prototype, not a live security enforcement service.', notes: ['Read the fictional scenario and the capability assumptions in the source.', 'Follow the recorded finding through the graph in the replay console.', 'Inspect the simulated containment and verification. No real agent is being contained by this page.'] },
    },
  },
  offside: {
    name: 'OFFSIDE', category: 'Evidence and decision systems', marker: '03', fact: 'Sources → audit → explicit routing',
    description: 'Explain why a disputed football decision remains disputed.',
    nodes: ['Read', 'Audit', 'Route'],
    links: [['Source', 'https://github.com/vighriday/offside-june-2026'], ['Evidence reader', 'https://offside-june-2026.vercel.app/'], ['Case study', 'https://hridayvig.xyz/projects/offside']],
    views: {
      problem: { title: 'The disagreement deserves an explanation.', copy: 'Different interpretations of an incident can persist even when people have access to the same match evidence.', notes: ['Begin with the source material behind the disputed football decision.', 'Check the reading before turning it into a confident explanation.', 'Distinguish the reasons for disagreement through explicit diagnostic rules.'] },
      decisions: { title: 'Give each part a clear responsibility.', copy: 'IBM Granite reads sources, Granite Guardian audits the reading, and deterministic routing assembles the diagnosis.', notes: ['Use Granite for source reading, with evidence connected to the account.', 'Give Guardian a distinct audit step rather than asking the same reading to approve itself.', 'Keep the final routing explicit so the diagnosis has an inspectable decision path.'] },
      evidence: { title: 'Read the analysis and its boundaries.', copy: 'The public evidence reader contains precomputed analyses. The live engine is separate from that reading experience.', notes: ['Open the reader to inspect the source-grounded account of an incident.', 'Follow the audit and the evidence supporting the interpretation.', 'Inspect the source for the deterministic rules. This explorer is not running a live match analysis.'] },
    },
  },
  pulse: {
    name: 'Pulse', category: 'Tools for working with AI', marker: '04', fact: 'Monitor · steer · approve',
    description: 'Keep a Claude Code session within reach from a phone.',
    nodes: ['Monitor', 'Steer', 'Approve'],
    links: [['Source', 'https://github.com/vighriday/Pulse'], ['Case study', 'https://hridayvig.xyz/projects/pulse']],
    views: {
      problem: { title: 'Leaving the desk should not lose the thread.', copy: 'A coding session can need attention, direction, or a tool approval while its owner is away from the computer.', notes: ['See what is happening in a Claude Code session from a phone.', 'Send direction back to the task without returning to the desk.', 'Review tool approval requests when the session needs a decision.'] },
      decisions: { title: 'Build around moments that need a person.', copy: 'Monitoring, task direction, and tool approvals form a small, practical remote-control workflow.', notes: ['Keep session monitoring close to the task being worked on.', 'Make steering the active task a distinct action from watching its progress.', 'Bring tool approvals into the phone workflow instead of treating them as background status.'] },
      evidence: { title: 'Follow the implementation.', copy: 'The source and case study describe the phone-to-session workflow. There is no hosted session or live terminal in this explorer.', notes: ['Inspect the source to understand how session information reaches the phone.', 'Read the case study for the task-steering workflow and its context.', 'Check the implementation of tool approvals. This page cannot access or approve a running session.'] },
    },
  },
});

export function normalizeState(value = {}) {
  const project = PROJECT_IDS.includes(value.project) ? value.project : 'veris';
  const lens = LENSES.includes(value.lens) ? value.lens : 'problem';
  const node = Number.isInteger(value.node) && value.node >= 0 && value.node < 3 ? value.node : LENSES.indexOf(lens);
  return { project, lens, node };
}

export function stateFromUrl(input) {
  const url = new URL(input);
  const rawNode = url.searchParams.get('node');
  return normalizeState({ project: url.searchParams.get('project'), lens: url.searchParams.get('lens'), node: /^[0-2]$/.test(rawNode ?? '') ? Number(rawNode) : undefined });
}

export function urlForState(input, value) {
  const url = new URL(input);
  const state = normalizeState(value);
  url.search = '';
  url.hash = '';
  url.searchParams.set('project', state.project);
  url.searchParams.set('lens', state.lens);
  if (state.node !== LENSES.indexOf(state.lens)) url.searchParams.set('node', String(state.node));
  return url.href;
}

export function transitionState(current, patch) {
  const next = { ...normalizeState(current), ...patch };
  if (patch.lens && !Object.hasOwn(patch, 'node')) next.node = LENSES.indexOf(patch.lens);
  return normalizeState(next);
}

export function nextTabId(ids, current, key) {
  const index = Math.max(0, ids.indexOf(current));
  if (key === 'Home') return ids[0];
  if (key === 'End') return ids.at(-1);
  if (key === 'ArrowRight' || key === 'ArrowDown') return ids[(index + 1) % ids.length];
  if (key === 'ArrowLeft' || key === 'ArrowUp') return ids[(index + ids.length - 1) % ids.length];
  return null;
}
