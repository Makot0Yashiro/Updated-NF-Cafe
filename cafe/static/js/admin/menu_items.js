/* Admin › Menu items: list, add, edit and delete menu items with their ingredients (at least one is required). */
import {$, esc, qty, peso, load, write, toast, servings} from './api.js';
import {createDock} from './dock.js';
import {grouped, initCategories} from './categories.js';

const API = '/admin/api/menu-items';
const dock = createDock();
let cats = [], items = [], ings = [], ingById = {}, catById = {}, filter = 'all', editing = null;

/* ---------- categories: filter chips + dropdown ---------- */
const inFilter = it => filter === 'all' || it.cat_id === filter || (filter.startsWith('g:') && catById[it.cat_id]?.group === filter.slice(2));

function renderFilters() {
  const n = id => items.filter(it => it.cat_id === id).length;
  const chip = (f, label, count, cls = '') =>
    `<button type="button" data-f="${esc(f)}" class="${cls}${filter === f ? ' on' : ''}" aria-pressed="${filter === f}">${esc(label)}${count == null ? '' : ` <span class="n">${count}</span>`}</button>`;
  $('filters').innerHTML = chip('all', 'All', items.length) + grouped(cats).map(g =>
    `<span class="cgroup" role="group" aria-label="${esc(g.name)}">${chip('g:' + g.name, g.name, null, 'glabel')}${g.cats.map(c => chip(c.id, c.name, n(c.id))).join('')}</span>`).join('');
}

function fillCategorySelect() {
  const sel = F('cat_id'), cur = sel.value;
  sel.innerHTML = '<option value="">Choose…</option>' + grouped(cats).map(g =>
    `<optgroup label="${esc(g.name)}">${g.cats.map(c => `<option value="${esc(c.id)}">${esc(c.emoji)} ${esc(c.name)}</option>`).join('')}</optgroup>`).join('');
  sel.value = cur;
}

/** Call whenever `cats` changes. */
function syncCategories() {
  catById = Object.fromEntries(cats.map(c => [c.id, c]));
  const known = filter === 'all' || catById[filter] || cats.some(c => 'g:' + c.group === filter);
  if (!known) filter = 'all';
  fillCategorySelect(); renderFilters(); render();
}

$('filters').onclick = e => {
  const b = e.target.closest('button'); if (!b) return;
  filter = b.dataset.f; renderFilters(); render();
};

/* ---------- grid ---------- */
function availability(it) {
  if (!it.active) return ['Hidden', 'off'];
  const n = servings(it.recipe, ingById);
  return n <= 0 ? ['Sold out', 'out'] : n <= 10 ? [`${n} left`, 'low'] : [`Can make ${n}`, 'ok'];
}

function render() {
  const q = $('q').value.trim().toLowerCase();
  const shown = items.filter(it => inFilter(it) && it.name.toLowerCase().includes(q));
  if (!shown.length) {
    $('grid').innerHTML = `<p class="note">${items.length ? 'No items match.' : 'No menu items yet. Add your first one in the panel below.'}</p>`;
    return;
  }
  $('grid').innerHTML = shown.map(it => {
    const c = catById[it.cat_id] || {name: 'Uncategorised', group: '', color: '#8a6f52', emoji: '🍽️'}, [label, st] = availability(it);
    return `<article class="mcard${editing === it.id ? ' editing' : ''}${it.active ? '' : ' inactive'}" data-id="${esc(it.id)}" style="--c:${esc(c.color)}">
      <div class="ph" data-e="${esc(c.emoji)}">${it.img ? `<img src="${esc(it.img)}" alt="" loading="lazy" onerror="this.remove()">` : ''}<span class="sbadge ${st}">${label}</span></div>
      <div class="mbody">
        <div class="mtitle"><b>${esc(it.name)}</b><span>${peso(it.price)}</span></div>
        <small>${c.group ? esc(c.group) + ' · ' : ''}${esc(c.name)}</small>
        <ul class="ilist">${it.recipe.map(r => {
          const short = +(ingById[r.ingredient_id]?.stock || 0) < +r.qty;
          return `<li class="${short ? 'short' : ''}"${short ? ' title="Not enough in stock for one serving"' : ''}>${esc(r.name)} <em>${qty(r.qty)} ${esc(r.unit)}</em></li>`;
        }).join('')}</ul>
        <button type="button" class="btn small ghost" data-act="edit" aria-label="Edit ${esc(it.name)}">Edit</button>
      </div></article>`;
  }).join('');
}

$('grid').onclick = e => {
  if (!e.target.closest('[data-act="edit"]')) return;
  startEdit(items.find(it => it.id === e.target.closest('.mcard').dataset.id));
};
$('q').oninput = render;

/* ---------- ingredient list builder ---------- */
const recipeBox = $('recipe'), recipeRows = () => [...recipeBox.querySelectorAll('.rrow')];

function addRow(r = {ingredient_id: '', qty: ''}) {
  recipeBox.querySelector('.rempty')?.remove();
  const row = document.createElement('div');
  row.className = 'rrow';
  row.innerHTML = `<select aria-label="Ingredient"><option value="">Choose ingredient…</option>${
      ings.map(i => `<option value="${esc(i.id)}">${esc(i.name)}</option>`).join('')}</select>
    <span class="unitfield"><input type="number" min="0" step="any" placeholder="Qty" aria-label="Amount per serving"><em></em></span>
    <button type="button" class="xbtn" aria-label="Remove ingredient" title="Remove">×</button>`;
  const sel = row.querySelector('select');
  sel.value = String(r.ingredient_id); row.querySelector('input').value = r.qty;
  sel.onchange = syncRows;
  row.querySelector('.xbtn').onclick = () => { row.remove(); syncRows(); };
  recipeBox.appendChild(row);
  syncRows();
  return row;
}

/** Show each row's unit and stop the same ingredient being picked twice. */
function syncRows() {
  const rows = recipeRows(), picked = rows.map(r => r.querySelector('select').value);
  rows.forEach((r, n) => {
    const sel = r.querySelector('select');
    r.querySelector('em').textContent = ingById[sel.value]?.unit || '';
    [...sel.options].forEach(o => { o.disabled = o.value !== '' && o.value !== picked[n] && picked.includes(o.value); });
  });
  if (!rows.length && !recipeBox.querySelector('.rempty')) recipeBox.innerHTML = '<p class="rempty">No ingredients yet.</p>';
}
$('add-ing').onclick = () => {
  if (!ings.length) return ferr('Add ingredients on the Inventory page first.');
  if (recipeRows().length >= ings.length) return ferr('Every ingredient is already in the list.');
  const row = addRow(); row.scrollIntoView({block: 'nearest'}); row.querySelector('select').focus();
};

/* ---------- add / edit form (in the docked panel) ---------- */
const form = $('form'), F = name => form.elements[name];
const ferr = msg => { $('ferr').hidden = !msg; $('ferr').textContent = msg || ''; };

function startEdit(it) {
  editing = it.id;
  F('name').value = it.name; F('cat_id').value = it.cat_id; F('price').value = it.price; F('img').value = it.img || ''; F('active').checked = it.active;
  recipeBox.innerHTML = ''; it.recipe.forEach(r => addRow(r)); syncRows();
  dock.open(); dock.setTitle('Edit menu item · ' + it.name);
  $('save').textContent = 'Save changes'; $('cancel').hidden = false; $('delete').hidden = false;
  ferr(); render(); F('name').focus();
}
function resetForm() {
  editing = null; form.reset(); recipeBox.innerHTML = ''; syncRows();
  dock.setTitle('Add menu item');
  $('save').textContent = 'Add menu item'; $('cancel').hidden = true; $('delete').hidden = true;
  ferr(); render();
}
$('cancel').onclick = resetForm;

/** Returns [body, null] when valid, or [null, message]. */
function readForm() {
  const recipe = recipeRows().map(r => ({ingredient_id: r.querySelector('select').value, qty: r.querySelector('input').value}));
  const body = {name: F('name').value.trim(), cat_id: F('cat_id').value, price: F('price').value, img: F('img').value.trim(), active: F('active').checked};
  if (!body.name) return [null, 'Give the item a name.'];
  if (!body.cat_id) return [null, 'Choose a category.'];
  if (!(+body.price > 0)) return [null, 'Enter a price greater than 0.'];
  if (items.some(it => it.id !== editing && it.name.toLowerCase() === body.name.toLowerCase())) return [null, 'A menu item with that name already exists.'];
  if (!recipe.length) return [null, 'Add at least one ingredient. Every menu item needs one so its stock can be tracked.'];
  if (recipe.some(r => !r.ingredient_id)) return [null, 'Choose an ingredient in every row, or remove the empty row.'];
  if (recipe.some(r => !(+r.qty > 0))) return [null, 'Every ingredient needs an amount greater than 0.'];
  body.price = +body.price;
  body.recipe = recipe.map(r => ({ingredient_id: +r.ingredient_id, qty: +r.qty}));
  return [body, null];
}

form.onsubmit = async e => {
  e.preventDefault();
  const [body, err] = readForm(); if (err) return ferr(err);
  try {
    const saved = editing ? await write('PUT', `${API}/${encodeURIComponent(editing)}`, body) : await write('POST', API, body);
    items = editing ? items.map(it => it.id === editing ? saved : it) : [...items, saved];
    toast(editing ? 'Menu item updated' : 'Menu item added'); resetForm(); renderFilters();
  } catch (ex) { ferr(ex.message); }
};

$('delete').onclick = async () => {
  const it = items.find(x => x.id === editing);
  if (!it || !confirm(`Delete ${it.name} from the menu? Past orders keep their record.`)) return;
  try {
    await write('DELETE', `${API}/${encodeURIComponent(it.id)}`);
    items = items.filter(x => x.id !== it.id); toast('Menu item deleted'); resetForm(); renderFilters();
  } catch (ex) { ferr(ex.message); }
};

/* ---------- categories dialog ---------- */
const catDialog = initCategories({getCats: () => cats, getItems: () => items, onChange: next => { cats = next; syncCategories(); }});
$('manage-cats').onclick = () => catDialog.open();

/* ---------- start ---------- */
try {
  ({categories: cats, items, ingredients: ings} = await load(API, 'menuItems'));
  ingById = Object.fromEntries(ings.map(i => [String(i.id), i]));
  syncRows(); syncCategories();
} catch (ex) { $('grid').innerHTML = `<p class="note">Couldn't load menu items: ${esc(ex.message)}</p>`; }
