/* Admin › Menu items: the photo picker in the item form (choose or drop a file, preview, change, remove, or paste a URL).
   Nothing is uploaded here; menu_items.js sends the pending change when the form is saved. */
import {$} from './api.js';

const MAX_BYTES = 5 * 1024 * 1024;
const TYPES = ['image/jpeg', 'image/png', 'image/webp'];
// Same wording as the server (cafe/images.py)
const TOO_LARGE = 'Photo is too large, max 5 MB.';
const NOT_IMAGE = "That file isn't a JPEG, PNG or WebP image.";

/** onError(message) shows a message in the form. Returns {load, pending}. */
export function createPhotoPicker(onError) {
  const input = $('photo-file'), drop = $('photo-drop'), preview = $('photo-preview'), empty = $('photo-empty'),
        acts = $('photo-acts'), urlInput = $('img-url'), urlField = $('url-field'), showUrl = $('show-url'), note = $('photo-note');
  let file = null, objectUrl = null, removing = false, current = null;   // current = the saved item's photo {hasPhoto, src}

  const hasUpload = () => !!file || (current?.hasPhoto && !removing);

  function paint() {
    const src = file ? objectUrl : hasUpload() ? current.src : urlInput.value.trim();
    preview.hidden = !src; empty.hidden = !!src;
    if (src && preview.getAttribute('src') !== src) preview.src = src;
    drop.classList.toggle('has', !!src);
    acts.hidden = !hasUpload();
    note.textContent = file ? `New photo: ${file.name} (uploads when you save)`
      : removing ? 'The photo will be removed when you save.'
      : hasUpload() && urlInput.value.trim() ? 'The uploaded photo is shown instead of the URL.' : '';
  }
  preview.onerror = () => { preview.hidden = true; empty.hidden = false; };

  function pick(f) {
    if (!f) return;
    const typeOk = TYPES.includes(f.type) || (!f.type && /\.(jpe?g|png|webp)$/i.test(f.name));
    if (!typeOk) return onError(NOT_IMAGE);
    if (f.size > MAX_BYTES) return onError(TOO_LARGE);
    onError('');
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    file = f; objectUrl = URL.createObjectURL(f); removing = false;
    paint();
  }

  input.onchange = () => { pick(input.files[0]); input.value = ''; };
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); pick(e.dataTransfer.files[0]); };
  $('photo-change').onclick = () => input.click();
  $('photo-remove').onclick = () => {
    if (file) { URL.revokeObjectURL(objectUrl); file = objectUrl = null; } else removing = true;
    paint(); input.focus();
  };
  showUrl.onclick = () => {
    const open = urlField.hidden;
    urlField.hidden = !open; showUrl.setAttribute('aria-expanded', open);
    if (open) urlInput.focus();
  };
  urlInput.oninput = paint;

  return {
    /** Show an item's saved photo (or nothing for a new item). keepFile keeps a chosen-but-not-uploaded file. */
    load(item, {keepFile = false} = {}) {
      if (!keepFile && file) { URL.revokeObjectURL(objectUrl); file = objectUrl = null; }
      removing = false;
      current = item ? {hasPhoto: item.has_photo, src: item.img} : null;
      urlInput.value = item?.img_url || '';
      urlField.hidden = !urlInput.value; showUrl.setAttribute('aria-expanded', !urlField.hidden);
      paint();
    },
    /** What Save should do with the photo: {file} to upload, {remove: true} to delete, or {} for nothing. */
    pending() {
      if (file) return {file};
      if (removing && current?.hasPhoto) return {remove: true};
      return {};
    },
  };
}
