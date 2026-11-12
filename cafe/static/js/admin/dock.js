/* Docked bottom panel (like VS Code's terminal): collapse/expand, drag or keyboard resize, remembered height. */
const MIN = 160, STEP = 40;
const store = {
  get: k => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked: height just isn't remembered */ } },
};

/** Wires up the panel rendered by the `dock` macro in admin_dock.html. Returns {open, setTitle}. */
export function createDock(el = document.getElementById('dock')) {
  const head = el.querySelector('.dock-head'), grip = el.querySelector('.dock-grip'), toggle = el.querySelector('.dock-toggle');
  const title = el.querySelector('.dock-title'), main = document.querySelector('main');
  const key = 'nf-dock-height:' + el.dataset.key;
  const max = () => Math.max(MIN, Math.round(innerHeight * (innerWidth <= 700 ? 0.6 : 0.75)));
  const clamp = h => Math.min(max(), Math.max(MIN, Math.round(h)));
  let height = clamp(+store.get(key) || +el.dataset.height || 300), open = true;   // always starts open

  function apply() {
    height = clamp(height);
    el.style.setProperty('--dock-h', height + 'px');
    el.classList.toggle('collapsed', !open);
    toggle.setAttribute('aria-expanded', open);
    toggle.setAttribute('aria-label', open ? 'Collapse panel' : 'Expand panel');
    grip.setAttribute('aria-valuemin', MIN); grip.setAttribute('aria-valuemax', max()); grip.setAttribute('aria-valuenow', height);
  }

  // Keep the page's last rows clear of the panel, and let the toast sit above it.
  new ResizeObserver(() => {
    const h = el.offsetHeight;
    main.style.paddingBottom = `calc(${h}px + 2rem)`;
    document.documentElement.style.setProperty('--dock-space', h + 'px');
  }).observe(el);

  function setOpen(v) {
    if (!v && el.contains(document.activeElement) && !head.contains(document.activeElement)) toggle.focus();
    open = v; apply();
  }
  head.onclick = () => setOpen(!open);

  grip.onpointerdown = e => {
    e.preventDefault(); grip.setPointerCapture(e.pointerId); el.classList.add('resizing');
    grip.onpointermove = ev => { height = innerHeight - ev.clientY; apply(); };
    grip.onpointerup = grip.onpointercancel = () => { grip.onpointermove = null; el.classList.remove('resizing'); store.set(key, height); };
  };
  grip.onkeydown = e => {
    const step = {ArrowUp: STEP, ArrowDown: -STEP}[e.key];
    if (e.key === 'Home') height = MIN; else if (e.key === 'End') height = max(); else if (step) height += step; else return;
    e.preventDefault(); apply(); store.set(key, height);
  };
  addEventListener('resize', apply);
  apply();

  return {
    open: () => setOpen(true),
    setTitle: t => { title.textContent = t; },
  };
}
