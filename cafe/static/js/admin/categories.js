/* Admin › Menu items › "Manage categories" dialog, plus the grouping helper the page uses for chips and the dropdown. */
import {$, esc, write, toast} from './api.js';

const API = '/admin/api/categories';
const plural = n => `${n} item${n === 1 ? '' : 's'}`;

/** [{name, cats}] with categories in `sort` order and groups ordered by their first category. */
export function grouped(cats) {
  const groups = new Map();
  [...cats].sort((a, b) => a.sort - b.sort || a.name.localeCompare(b.name))
    .forEach(c => { if (!groups.has(c.group)) groups.set(c.group, []); groups.get(c.group).push(c); });
  return [...groups].map(([name, list]) => ({name, cats: list}));
}

/**
 * getCats/getItems read the page's current data; onChange(newCats) is called after every successful save or delete.
 * Returns {open}.
 */
export function initCategories({getCats, getItems, onChange}) {
  const dlg = $('cats'), form = $('cat-form'), F = name => form.elements[name];
  const count = id => getItems().filter(it => it.cat_id === id).length;
  const err = msg => { $('cat-err').hidden = !msg; $('cat-err').textContent = msg || ''; };
  let editing = null;

  function renderList() {
    const groups = grouped(getCats());
    $('group-list').innerHTML = groups.map(g => `<option value="${esc(g.name)}">`).join('');
    $('cat-list').innerHTML = groups.length ? groups.map(g => `<h3 class="cat-group">${esc(g.name)}</h3>` + g.cats.map(c => `
      <div class="cat-row${editing === c.id ? ' editing' : ''}" data-id="${esc(c.id)}">
        <span class="swatch" style="--c:${esc(c.color)}" aria-hidden="true">${esc(c.emoji)}</span>
        <b>${esc(c.name)}</b><span class="dim">${plural(count(c.id))}</span>
        <span class="acts">
          <button type="button" class="btn small ghost" data-act="edit" aria-label="Edit ${esc(c.name)}">Edit</button>
          <button type="button" class="xbtn" data-act="delete" aria-label="Delete ${esc(c.name)}" title="Delete">×</button>
        </span></div>`).join('')).join('') : '<p class="note">No categories yet. Add one below.</p>';
  }

  function preview() {
    const tile = $('cat-preview');
    tile.style.setProperty('--c', F('color').value);
    tile.querySelector('em').textContent = F('group').value.trim() || 'Group';
    tile.querySelector('.emo').textContent = F('emoji').value.trim();
    tile.querySelector('b').textContent = F('name').value.trim() || 'Category name';
    tile.querySelector('small').textContent = plural(editing ? count(editing) : 0);
  }
  form.oninput = preview;

  function startEdit(c) {
    editing = c.id;
    F('name').value = c.name; F('group').value = c.group; F('color').value = c.color; F('emoji').value = c.emoji;
    $('cat-form-title').textContent = 'Edit category · ' + c.name; $('cat-save').textContent = 'Save changes'; $('cat-cancel').hidden = false;
    err(); renderList(); preview(); F('name').focus();
  }
  function resetForm() {
    editing = null; form.reset();
    $('cat-form-title').textContent = 'Add category'; $('cat-save').textContent = 'Add category'; $('cat-cancel').hidden = true;
    err(); renderList(); preview();
  }
  $('cat-cancel').onclick = resetForm;

  async function remove(c) {
    const n = count(c.id);
    if (n) return err(`Move or delete the ${plural(n)} in ${c.name} first.`);
    if (!confirm(`Delete the ${c.name} category?`)) return;
    try {
      await write('DELETE', `${API}/${encodeURIComponent(c.id)}`);
      onChange(getCats().filter(x => x.id !== c.id));
      toast('Category deleted'); if (editing === c.id) resetForm(); else { err(); renderList(); }
    } catch (ex) { err(ex.message); }
  }

  $('cat-list').onclick = e => {
    const b = e.target.closest('[data-act]'); if (!b) return;
    const c = getCats().find(x => x.id === b.closest('.cat-row').dataset.id);
    (b.dataset.act === 'edit' ? startEdit : remove)(c);
  };

  form.onsubmit = async e => {
    e.preventDefault();
    const body = {name: F('name').value.trim(), group: F('group').value.trim(), color: F('color').value, emoji: F('emoji').value.trim()};
    if (!body.name) return err('Give the category a name.');
    if (getCats().some(c => c.id !== editing && c.name.toLowerCase() === body.name.toLowerCase())) return err('A category with that name already exists.');
    if (!body.group) return err('Pick a group or type a new one.');
    if (!body.emoji || [...body.emoji].length > 4) return err('Add an emoji (up to 4 characters).');
    try {
      const saved = editing ? await write('PUT', `${API}/${encodeURIComponent(editing)}`, body) : await write('POST', API, body);
      onChange(editing ? getCats().map(c => c.id === editing ? saved : c) : [...getCats(), saved]);
      toast(editing ? 'Category updated' : 'Category added'); resetForm();
    } catch (ex) { err(ex.message); }
  };

  $('cats-close').onclick = () => dlg.close();

  return {
    open() { resetForm(); dlg.showModal(); F('name').focus(); },
  };
}
