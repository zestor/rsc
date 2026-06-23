// Talent Pool preview client behavior.
// 1. Smooth-scrolls section jump links.
// 2. Drives an in-memory dark theme toggle, initialized from prefers-color-scheme.
//    State lives on document.documentElement (data-theme); no localStorage / cookies.
(function () {
  var root = document.documentElement;
  var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function applyTheme(theme) {
    if (theme === 'dark') {
      root.setAttribute('data-theme', 'dark');
    } else {
      root.setAttribute('data-theme', 'light');
    }
    var toggle = document.querySelector('.theme-toggle');
    if (toggle) {
      var isDark = theme === 'dark';
      toggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
      var label = toggle.querySelector('.theme-toggle-label');
      if (label) label.textContent = isDark ? 'Light' : 'Dark';
    }
  }

  var initial = media && media.matches ? 'dark' : 'light';
  applyTheme(initial);

  if (media && typeof media.addEventListener === 'function') {
    media.addEventListener('change', function (event) {
      applyTheme(event.matches ? 'dark' : 'light');
    });
  }

  var toggle = document.querySelector('.theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var current = root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
      applyTheme(current === 'dark' ? 'light' : 'dark');
    });
  }

  var links = document.querySelectorAll('.section-jump');
  links.forEach(function (link) {
    link.addEventListener('click', function (event) {
      var href = link.getAttribute('href') || '';
      var target = document.getElementById(href.replace(/^#/, ''));
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (typeof history.replaceState === 'function') {
        history.replaceState(null, '', href);
      }
    });
  });

  var drawer = document.querySelector('.candidate-drawer');
  var backdrop = document.querySelector('.drawer-backdrop');
  var panels = document.querySelectorAll('[data-candidate-panel]');
  var openers = document.querySelectorAll('.candidate-open');
  var closers = document.querySelectorAll('[data-candidate-close]');
  var lastOpener = null;

  function setActiveRow(candidateId) {
    document.querySelectorAll('.candidate-row').forEach(function (row) {
      row.classList.toggle('is-active', row.getAttribute('data-id') === candidateId);
    });
  }

  function openCandidate(candidateId) {
    if (!drawer || !candidateId) return;
    lastOpener = document.activeElement;
    var matched = false;
    panels.forEach(function (panel) {
      var isMatch = panel.getAttribute('data-candidate-panel') === candidateId;
      panel.hidden = !isMatch;
      if (isMatch) matched = true;
    });
    if (!matched) return;
    drawer.hidden = false;
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    if (backdrop) backdrop.hidden = false;
    document.body.classList.add('drawer-open');
    setActiveRow(candidateId);
    var closeButton = drawer.querySelector('.drawer-close');
    if (closeButton) closeButton.focus({ preventScroll: true });
  }

  function closeCandidate() {
    if (!drawer) return;
    drawer.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    drawer.hidden = true;
    if (backdrop) backdrop.hidden = true;
    document.body.classList.remove('drawer-open');
    panels.forEach(function (panel) {
      panel.hidden = true;
    });
    setActiveRow('');
    if (lastOpener && typeof lastOpener.focus === 'function') {
      lastOpener.focus({ preventScroll: true });
    }
    lastOpener = null;
  }

  openers.forEach(function (opener) {
    opener.addEventListener('click', function (event) {
      event.preventDefault();
      openCandidate(opener.getAttribute('data-candidate-id'));
    });
  });

  closers.forEach(function (closer) {
    closer.addEventListener('click', closeCandidate);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeCandidate();
    if (event.key !== 'Tab' || !drawer || drawer.hidden) return;
    var focusable = drawer.querySelectorAll(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable.length) return;
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
})();
