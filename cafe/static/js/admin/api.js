/* Shared helpers for the admin inventory pages (ES module). */
const CSRF = document.querySelector('meta[name=csrf]').content;

export const $ = id => document.getElementById(id);
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
export const qty = n => (+n).toLocaleString('en-PH', {maximumFractionDigits: 2});
export const peso = n => '₱' + (+n).toLocaleString('en-PH', {maximumFractionDigits: 2});

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

/** Request with the CSRF header; body is sent as JSON, or as-is when it's FormData (file uploads).
    Throws ApiError with the server's {error} message on failure. */
export async function api(method, url, body) {
  const opts = {method, headers: {'X-CSRFToken': CSRF}};
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const r = await fetch(url, opts);
  if (r.status === 204) return null;
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(data.error || `Request failed (${r.status})`, r.status);
  return data;
}

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
