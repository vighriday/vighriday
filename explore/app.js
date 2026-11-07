import { PROJECTS, PROJECT_IDS, LENSES, normalizeState, stateFromUrl, urlForState, transitionState, nextTabId } from './model.mjs';

export function mountExplorer(document, environment = window) {
  const get = id => document.getElementById(id);
  const projectTabs = [...document.querySelectorAll('[data-project]')];
  const lensTabs = [...document.querySelectorAll('[data-lens]')];
  const nodes = [...document.querySelectorAll('[data-node]')];
  let state = stateFromUrl(environment.location.href);
  let shareAttempt = 0;

  function render(announce = true) {
    const project = PROJECTS[state.project];
    const view = project.views[state.lens];
    for (const button of projectTabs) {
      const selected = button.dataset.project === state.project;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
    }
    for (const button of lensTabs) {
      const selected = button.dataset.lens === state.lens;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
    }
    get('project-panel').setAttribute('aria-labelledby', `project-${state.project}`);
    get('lens-panel').setAttribute('aria-labelledby', `lens-${state.lens}`);
    get('project-category').textContent = project.category.toUpperCase();
    const name = document.createElement('span');
    name.setAttribute('aria-hidden', 'true');
    name.textContent = '.';
    get('project-name').replaceChildren(document.createTextNode(project.name), name);
    get('project-description').textContent = project.description;
    get('project-index').textContent = `${project.marker} / 04`;
    get('project-fact').textContent = project.fact.toUpperCase();
    get('view-title').textContent = view.title;
    get('view-copy').textContent = view.copy;
    nodes.forEach((node, index) => {
      node.setAttribute('aria-pressed', String(index === state.node));
      node.querySelector('.node-label').textContent = project.nodes[index];
      node.setAttribute('aria-label', `Explore ${project.nodes[index]}`);
    });
    get('active-route').setAttribute('stroke-dashoffset', String(600 * (1 - state.node / 2)));
    get('node-note-title').textContent = `0${state.node + 1} / ${project.nodes[state.node].toUpperCase()}`;
    get('node-note-copy').textContent = view.notes[state.node];
    const links = project.links.map(([label, href]) => {
      const link = document.createElement('a');
      link.href = href;
      link.textContent = `${label} ↗`;
      return link;
    });
    get('project-links').replaceChildren(...links);
    get('project-links').setAttribute('aria-label', `${project.name} links`);
    document.title = `${project.name} / ${state.lens} / Hriday Vig`;
    get('share-fallback').hidden = true;
    get('share-status').textContent = '';
    ++shareAttempt;
    if (announce) get('view-announcement').textContent = `${project.name}. ${state.lens}. ${project.nodes[state.node]}. ${view.notes[state.node]}`;
  }

  function navigate(patch) {
    const next = transitionState(state, patch);
    if (JSON.stringify(next) === JSON.stringify(state)) return;
    state = next;
    environment.history.pushState(null, '', urlForState(environment.location.href, state));
    render();
  }

  function bindTabs(buttons, ids, property) {
    for (const button of buttons) {
      button.disabled = false;
      button.addEventListener('click', () => navigate({ [property]: button.dataset[property] }));
      button.addEventListener('keydown', event => {
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        const nextId = nextTabId(ids, button.dataset[property], event.key);
        if (!nextId) return;
        event.preventDefault();
        navigate({ [property]: nextId });
        buttons.find(item => item.dataset[property] === nextId).focus();
      });
    }
  }

  bindTabs(projectTabs, PROJECT_IDS, 'project');
  bindTabs(lensTabs, LENSES, 'lens');
  nodes.forEach(node => {
    node.disabled = false;
    node.addEventListener('click', () => navigate({ node: Number(node.dataset.node) }));
  });
  environment.addEventListener('popstate', () => { state = stateFromUrl(environment.location.href); render(); });
  get('share-view').disabled = false;
  get('share-view').addEventListener('click', async () => {
    const attempt = ++shareAttempt;
    const url = urlForState(environment.location.href, state);
    get('share-status').textContent = '';
    get('share-fallback').hidden = true;
    try {
      if (!environment.navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await environment.navigator.clipboard.writeText(url);
      if (attempt === shareAttempt) get('share-status').textContent = 'View link copied.';
    } catch {
      if (attempt !== shareAttempt) return;
      get('share-fallback').hidden = false;
      get('share-url').value = url;
      get('share-url').focus();
      get('share-url').select();
      get('share-status').textContent = 'Select and copy the link below.';
    }
  });
  render(false);
  return { getState: () => normalizeState(state) };
}

if (typeof document !== 'undefined') mountExplorer(document);
