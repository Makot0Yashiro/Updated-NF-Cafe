/* Admin › Menu items: list, add, edit and delete menu items with their ingredients (at least one is required). */
import {$, esc, qty, peso, load, write, toast, servings} from './api.js';

const API = '/admin/api/menu-items';
let cats = [], items = [], ings = [], ingById = {}, catById = {}, filter = 'all', editing = null;

/* ---------- grid ---------- */
function availability(it) {
  if (!it.active) return ['Hidden', 'off'];
  const n = servings(it.recipe, ingById);
  return n <= 0 ? ['Sold out', 'out'] : n <= 10 ? [`${n} left`, 'low'] : [`Can make ${n}`, 'ok'];
}

function render() {
  const q = $('q').value.trim().toLowerCase();
  const shown = items.filter(it => (filter === 'all' || it.cat_id === filter) && it.name.toLowerCase().includes(q));
  if (!shown.length) {
    $('grid').innerHTML = `<p class="note">${items.length ? 'No items match.' : 'No menu items yet. Add your first one with the form.'}</p>`;
    return;
  }
  $('grid').innerHTML = shown.map(it => {
    const c = catById[it.cat_id] || {name: 'Uncategorised', color: '#8a6f52', emoji: '🍽️'}, [label, st] = availability(it);
    return `<article class="mcard${editing === it.id ? ' editing' : ''}${it.active ? '' : ' inactive'}" data-id="${esc(it.id)}" style="--c:${esc(c.color)}">
      <div class="ph" data-e="${esc(c.emoji)}">${it.img ? `<img src="${esc(it.img)}" alt="" loading="lazy" onerror="this.remove()">` : ''}<span class="sbadge ${st}">${label}</span></div>
      <div class="mbody">
        <div class="mtitle"><b>${esc(it.name)}</b><span>${peso(it.price)}</span></div>
        <small>${esc(c.name)}</small>
        <ul class="ilist">${it.recipe.map(r => {
          const short = +(ingById[r.ingredient_id]?.stock || 0) < +r.qty;
          return `<li class="${short ? 'short' : ''}"${short ? ' title="Not enough in stock for one serving"' : ''}>${esc(r.name)} <em>${qty(r.qty)} ${esc(r.unit)}</em></li>`;
        }).join('')}</ul>
        <button type="button" class="btn small ghost" data-act="edit" aria-label="Edit ${esc(it.name)}">Edit</button>
      </div></article>`;
  }).join('');
}

function renderFilters() {
  $('filters').innerHTML = `<button type="button" data-f="all" class="${filter === 'all' ? 'on' : ''}">All</button>` +
    cats.map(c => `<button type="button" data-f="${esc(c.id)}" class="${filter === c.id ? 'on' : ''}">${esc(c.name)}</button>`).join('');
}

$('grid').onclick = e => {
  if (!e.target.closest('[data-act="edit"]')) return;
  startEdit(items.find(it => it.id === e.target.closest('.mcard').dataset.id));
};
$('filters').onclick = e => {
  const b = e.target.closest('button'); if (!b) return;
  filter = b.dataset.f; renderFilters(); render();
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
  addRow().querySelector('select').focus();
};

/* ---------- add / edit form ---------- */
const form = $('form'), F = name => form.elements[name];
const ferr = msg => { $('ferr').hidden = !msg; $('ferr').textContent = msg || ''; };

function startEdit(it) {
  editing = it.id;
  F('name').value = it.name; F('cat_id').value = it.cat_id; F('price').value = it.price; F('img').value = it.img || ''; F('active').checked = it.active;
  recipeBox.innerHTML = ''; it.recipe.forEach(r => addRow(r)); syncRows();
  $('form-title').textContent = 'Edit menu item'; $('save').textContent = 'Save changes'; $('edit-acts').hidden = false;
  ferr(); render(); F('name').focus();
}
function resetForm() {
  editing = null; form.reset(); recipeBox.innerHTML = ''; syncRows();
  $('form-title').textContent = 'Add menu item'; $('save').textContent = 'Add menu item'; $('edit-acts').hidden = true;
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
    toast(editing ? 'Menu item updated' : 'Menu item added'); resetForm();
  } catch (ex) { ferr(ex.message); }
};

$('delete').onclick = async () => {
  const it = items.find(x => x.id === editing);
  if (!it || !confirm(`Delete ${it.name} from the menu? Past orders keep their record.`)) return;
  try {
    await write('DELETE', `${API}/${encodeURIComponent(it.id)}`);
    items = items.filter(x => x.id !== it.id); toast('Menu item deleted'); resetForm();
  } catch (ex) { ferr(ex.message); }
};

/* ---------- start ---------- */
try {
  ({categories: cats, items, ingredients: ings} = await load(API, 'menuItems'));
  ingById = Object.fromEntries(ings.map(i => [String(i.id), i]));
  catById = Object.fromEntries(cats.map(c => [c.id, c]));
  F('cat_id').innerHTML = '<option value="">Choose…</option>' + cats.map(c => `<option value="${esc(c.id)}">${esc(c.emoji)} ${esc(c.name)}</option>`).join('');
  renderFilters(); syncRows(); render();
} catch (ex) { $('grid').innerHTML = `<p class="note">Couldn't load menu items: ${esc(ex.message)}</p>`; }
