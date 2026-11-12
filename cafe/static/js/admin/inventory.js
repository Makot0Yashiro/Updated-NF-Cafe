/* Admin › Inventory: list, add, edit, restock and delete ingredients. */
import {$, esc, qty, api, toast, stockState} from './api.js';
import {createDock} from './dock.js';

const API = '/admin/api/ingredients';
const BADGE = {low: 'Low', out: 'Out'};
const dock = createDock();
let list = [], filter = 'all', editing = null, restocking = null;

/* ---------- list ---------- */
function render() {
  const q = $('q').value.trim().toLowerCase();
  const shown = list.filter(i => (filter === 'all' || stockState(i) === filter) && i.name.toLowerCase().includes(q));
  $('k-total').textContent = list.length;
  $('k-low').textContent = list.filter(i => stockState(i) === 'low').length;
  $('k-out').textContent = list.filter(i => stockState(i) === 'out').length;

  if (!shown.length) {
    $('rows').innerHTML = `<p class="note">${list.length ? 'No ingredients match.' : 'No ingredients yet. Add your first one with the form.'}</p>`;
    return;
  }
  $('rows').innerHTML = shown.map(i => {
    const st = stockState(i), pct = Math.min(100, +i.stock / Math.max(+i.low_at * 3, 1) * 100), used = i.used_in.length;
    return `<div class="irow st-${st}${editing === i.id ? ' editing' : ''}" data-id="${esc(i.id)}">
      <span class="nm"><b>${esc(i.name)}</b>${BADGE[st] ? `<span class="sbadge ${st}">${BADGE[st]}</span>` : ''}</span>
      <span class="lvl"><span><b>${qty(i.stock)}</b> ${esc(i.unit)}</span><i class="meter" aria-hidden="true"><b style="width:${pct}%"></b></i></span>
      <span class="dim"><span class="lbl">Alert at </span>${qty(i.low_at)} ${esc(i.unit)}</span>
      <span class="dim" title="${esc(i.used_in.join(', '))}"><span class="lbl">Used in </span>${used ? `${used} item${used > 1 ? 's' : ''}` : '<em>none</em>'}</span>
      <span class="acts">
        <button type="button" class="btn small" data-act="restock">Restock</button>
        <button type="button" class="btn small ghost" data-act="edit">Edit</button>
        <button type="button" class="xbtn" data-act="delete" aria-label="Delete ${esc(i.name)}" title="Delete">×</button>
      </span></div>`;
  }).join('');
}

$('rows').onclick = e => {
  const b = e.target.closest('[data-act]'); if (!b) return;
  const ing = list.find(i => String(i.id) === b.closest('.irow').dataset.id);
  ({restock: openRestock, edit: startEdit, delete: remove})[b.dataset.act](ing);
};
$('filters').onclick = e => {
  const b = e.target.closest('button'); if (!b) return;
  filter = b.dataset.f;
  $('filters').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
  render();
};
$('q').oninput = render;

/* ---------- add / edit form ---------- */
const form = $('form'), F = name => form.elements[name];
const ferr = msg => { $('ferr').hidden = !msg; $('ferr').textContent = msg || ''; };

function startEdit(i) {
  editing = i.id;
  F('name').value = i.name; F('unit').value = i.unit; F('stock').value = i.stock; F('low_at').value = i.low_at;
  F('unit').disabled = i.used_in.length > 0;   // changing the unit would break the amounts in existing recipes
  F('unit').title = F('unit').disabled ? 'Remove it from every menu item first to change its unit' : '';
  dock.open(); dock.setTitle('Edit ingredient · ' + i.name); $('save').textContent = 'Save changes'; $('cancel').hidden = false;
  ferr(); render(); F('name').focus();
}
function resetForm() {
  editing = null; form.reset(); F('unit').disabled = false; F('unit').title = '';
  dock.setTitle('Add ingredient'); $('save').textContent = 'Add ingredient'; $('cancel').hidden = true;
  ferr(); render();
}
$('cancel').onclick = resetForm;

form.onsubmit = async e => {
  e.preventDefault();
  const body = {name: F('name').value.trim(), unit: F('unit').value, stock: F('stock').value, low_at: F('low_at').value};
  if (!body.name) return ferr('Give the ingredient a name.');
  if (body.stock === '' || +body.stock < 0) return ferr('Enter how much is in stock (0 or more).');
  if (body.low_at === '' || +body.low_at < 0) return ferr('Enter the low-stock alert amount (0 or more).');
  if (list.some(i => i.id !== editing && i.name.toLowerCase() === body.name.toLowerCase())) return ferr('An ingredient with that name already exists.');
  body.stock = +body.stock; body.low_at = +body.low_at;
  try {
    const saved = editing ? await api('PUT', `${API}/${editing}`, body) : await api('POST', API, body);
    list = editing ? list.map(i => i.id === saved.id ? saved : i) : [...list, saved].sort((a, b) => a.name.localeCompare(b.name));
    toast(editing ? 'Ingredient updated' : 'Ingredient added'); resetForm();
  } catch (err) { ferr(err.message); }
};

/* ---------- restock dialog ---------- */
const dlg = $('restock'), rsErr = msg => { $('rs-err').hidden = !msg; $('rs-err').textContent = msg || ''; };
function openRestock(i) {
  restocking = i;
  $('rs-title').textContent = 'Restock ' + i.name;
  $('rs-now').textContent = `${qty(i.stock)} ${i.unit}`; $('rs-unit').textContent = i.unit;
  $('rs-amt').value = ''; $('rs-after').textContent = '–'; rsErr();
  dlg.showModal(); $('rs-amt').focus();
}
$('rs-amt').oninput = () => {
  const a = +$('rs-amt').value;
  $('rs-after').textContent = a > 0 ? `${qty(+restocking.stock + a)} ${restocking.unit}` : '–';
};
$('rs-cancel').onclick = () => dlg.close();
$('rs-form').onsubmit = async e => {
  e.preventDefault();
  const amount = +$('rs-amt').value;
  if (!(amount > 0)) return rsErr('Enter an amount greater than 0.');
  try {
    const saved = await api('POST', `${API}/${restocking.id}/restock`, {amount});
    list = list.map(i => i.id === saved.id ? saved : i);
    dlg.close(); toast(`Added ${qty(amount)} ${saved.unit} of ${saved.name}`); render();
  } catch (err) { rsErr(err.message); }
};

/* ---------- delete ---------- */
async function remove(i) {
  if (i.used_in.length) return toast(`${i.name} is used in ${i.used_in.join(', ')}. Remove it from those items first.`, 'bad');
  if (!confirm(`Delete ${i.name}? This can't be undone.`)) return;
  try {
    await api('DELETE', `${API}/${i.id}`);
    list = list.filter(x => x.id !== i.id);
    if (editing === i.id) resetForm(); else render();
    toast('Ingredient deleted');
  } catch (err) { toast(err.message, 'bad'); }
}

/* ---------- start ---------- */
try { list = await api('GET', API); render(); }
catch (err) { $('rows').innerHTML = `<p class="note">Couldn't load ingredients: ${esc(err.message)}</p>`; }
