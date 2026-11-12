/* Shared helpers for the admin inventory pages (ES module). */
const CSRF = document.querySelector('meta[name=csrf]').content;

export const $ = id => document.getElementById(id);
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
export const qty = n => (+n).toLocaleString('en-PH', {maximumFractionDigits: 2});
export const peso = n => '₱' + (+n).toLocaleString('en-PH', {maximumFractionDigits: 2});

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

/** JSON request with the CSRF header. Throws ApiError with the server's {error} message on failure. */
export async function api(method, url, body) {
  const opts = {method, headers: {'X-CSRFToken': CSRF}};
  if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const r = await fetch(url, opts);
  if (r.status === 204) return null;
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(data.error || `Request failed (${r.status})`, r.status);
  return data;
}

/* ===== PREVIEW MODE (remove with preview_data.js once the backend API exists) =====
   While the API answers 404, pages render sample data and every write is refused. */
export let preview = false;
export async function load(url, previewKey) {
  try { return await api('GET', url); }
  catch (e) {
    if (e.status !== 404) throw e;
    preview = true;
    const banner = $('preview');
    banner.hidden = false;
    banner.textContent = 'Preview: showing sample data because the inventory backend isn’t connected yet. Changes are not saved.';
    return (await import('./preview_data.js'))[previewKey]();
  }
}
/** Use for every write. In preview mode it refuses instead of calling the missing API. */
export function write(method, url, body) {
  if (preview) return Promise.reject(new ApiError('Preview only: saving works once the backend is connected.', 0));
  return api(method, url, body);
}
/* ===== END PREVIEW MODE ===== */

/** Short status message in the corner. kind: 'ok' | 'bad' */
export function toast(msg, kind = 'ok') {
  let t = $('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
  t.textContent = msg; t.className = 'toast show ' + kind;
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 3500);
}

/** Ingredient stock state for badges, meters and filters: 'ok' | 'low' | 'out'. */
export const stockState = i => +i.stock <= 0 ? 'out' : +i.stock <= +i.low_at ? 'low' : 'ok';

/** How many servings of an item the current stock can make (0 = sold out). ingById is keyed by ingredient id. */
export function servings(recipe, ingById) {
  if (!recipe.length) return 0;
  return Math.min(...recipe.map(r => Math.floor((+ingById[r.ingredient_id]?.stock || 0) / +r.qty)));
}
