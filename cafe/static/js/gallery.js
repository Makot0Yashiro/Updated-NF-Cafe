/* New Found Cafe — gallery carousel (needs vendor/splide/splide.min.js loaded first) */
(function () {
  var root = document.getElementById('nf-gallery');
  if (!root || typeof Splide === 'undefined') return;

  /* ---- carousel ---- */
  var splide = new Splide('#nf-splide', {
    type: 'loop',
    perPage: 3,
    perMove: 1,
    focus: 'center',          // active slide sits in the middle
    gap: '1rem',
    speed: 800,
    easing: 'cubic-bezier(.65,0,.35,1)',
    arrows: false,            // we use our own round buttons
    pagination: false,
    keyboard: 'focused',
    breakpoints: { 767: { perPage: 1, gap: '.75rem' } }
  }).mount();

  root.querySelector('[data-nf-prev]').addEventListener('click', function () { splide.go('<'); });
  root.querySelector('[data-nf-next]').addEventListener('click', function () { splide.go('>'); });

  /* ---- click a photo 3 times to open the menu ---- */
  var toast = document.createElement('div');
  toast.className = 'nf-toast'; toast.setAttribute('role', 'status'); root.appendChild(toast);
  var taps = 0, lastSlide = null, tapTimer = 0, hideTimer = 0;
  root.addEventListener('click', function (e) {
    var a = e.target.closest('.splide__slide a');
    if (!a) return;
    e.preventDefault();
    var slide = a.parentNode;
    taps = (slide === lastSlide) ? taps + 1 : 1;           // a different photo restarts the count
    lastSlide = slide;
    clearTimeout(tapTimer); tapTimer = setTimeout(function () { taps = 0; lastSlide = null; }, 2000);
    if (taps >= 3) { toast.textContent = 'Opening the menu…'; toast.classList.add('is-on'); window.location.href = a.href; return; }
    toast.textContent = 'Click ' + (3 - taps) + ' more time' + (3 - taps > 1 ? 's' : '') + ' to open the menu';
    toast.classList.add('is-on'); clearTimeout(hideTimer);
    hideTimer = setTimeout(function () { toast.classList.remove('is-on'); }, 1800);
  });

  /* ---- scroll-in animation ---- */
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if ('IntersectionObserver' in window && !reduced) {
    root.classList.add('nf-reveal-ready');
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    root.querySelectorAll('[data-nf-reveal]').forEach(function (el) { io.observe(el); });
  }

  /* ---- custom DRAG cursor (mouse devices only) ---- */
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;

  var dot = root.querySelector('.nf-cursor__dot');
  var ring = root.querySelector('.nf-cursor__ring');
  var track = root.querySelector('.splide__track');
  var controls = root.querySelector('.nf-controls');
  var m = { x: 0, y: 0 }, d = { x: 0, y: 0 }, r = { x: 0, y: 0 }, raf = 0;

  root.classList.add('nf-has-cursor');

  function tick() {
    d.x += (m.x - d.x) * 0.35; d.y += (m.y - d.y) * 0.35;    // dot follows closely
    r.x += (m.x - r.x) * 0.14; r.y += (m.y - r.y) * 0.14;    // ring trails behind
    dot.style.left = d.x + 'px'; dot.style.top = d.y + 'px';
    ring.style.left = r.x + 'px'; ring.style.top = r.y + 'px';
    raf = requestAnimationFrame(tick);
  }
  function flag(cls, on) { root.classList.toggle(cls, on); }

  root.addEventListener('mouseenter', function (e) {
    m.x = d.x = r.x = e.clientX; m.y = d.y = r.y = e.clientY;
    flag('is-active', true);
    if (!raf) tick();
  });
  root.addEventListener('mouseleave', function () {
    flag('is-active', false); flag('is-drag', false); flag('is-control', false);
    cancelAnimationFrame(raf); raf = 0;
  });
  root.addEventListener('mousemove', function (e) { m.x = e.clientX; m.y = e.clientY; });

  track.addEventListener('mouseenter', function () { flag('is-drag', true); });
  track.addEventListener('mouseleave', function () { flag('is-drag', false); });
  controls.addEventListener('mouseenter', function () { flag('is-control', true); flag('is-drag', false); });
  controls.addEventListener('mouseleave', function () { flag('is-control', false); });
  track.addEventListener('pointerdown', function () { flag('is-down', true); });
  window.addEventListener('pointerup', function () { flag('is-down', false); });
})();
