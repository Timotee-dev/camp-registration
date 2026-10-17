/* Small helpers shared by every page: toast, copy-to-clipboard, clickable table rows, menus. */
(function () {
  'use strict';

  var toastTimer;
  window.toast = function (msg, isError) {
    var t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.toggle('err', !!isError);
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove('show'); }, 2600);
  };

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy') ? resolve() : reject(); } catch (e) { reject(e); }
      document.body.removeChild(ta);
    });
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy]');
    if (btn) {
      var src = document.querySelector(btn.getAttribute('data-copy'));
      if (!src) return;
      copyText(src.value || src.textContent).then(function () {
        var old = btn.textContent;
        btn.textContent = 'Copied ✓';
        window.toast('Copied to clipboard');
        setTimeout(function () { btn.textContent = old; }, 1600);
      }, function () {
        src.select && src.select();
        window.toast('Press Ctrl+C to copy', true);
      });
      return;
    }
    var row = e.target.closest('tr[data-href]');
    if (row && !e.target.closest('a, button, input')) {
      window.location.href = row.getAttribute('data-href');
    }
    // close the account menu when clicking elsewhere
    document.querySelectorAll('details.usermenu[open]').forEach(function (d) {
      if (!d.contains(e.target)) d.removeAttribute('open');
    });
  });

  // Stop double submissions (double taps, impatient clicks on a slow connection).
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented || form.hasAttribute('data-allow-resubmit') || form.id === 'stepper') return;
    if (form.dataset.submitting === '1') { e.preventDefault(); return; }
    form.dataset.submitting = '1';
    var buttons = form.querySelectorAll('button[type=submit], button:not([type])');
    setTimeout(function () {           // after the browser has captured the form data
      buttons.forEach(function (b) {
        b.disabled = true;
        if (!b.dataset.label) { b.dataset.label = b.textContent; }
        if (b.textContent.trim().length > 2) b.textContent = 'Please wait…';
      });
    }, 0);
    // Safety: re-enable after 15s in case the request never completes.
    setTimeout(function () { unlock(form); }, 15000);
  });

  function unlock(form) {
    form.dataset.submitting = '';
    form.querySelectorAll('button[disabled]').forEach(function (b) {
      b.disabled = false;
      if (b.dataset.label) b.textContent = b.dataset.label;
    });
  }

  // Back/forward cache: forms come back unlocked.
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) document.querySelectorAll('form[data-submitting="1"]').forEach(unlock);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('details.usermenu[open]').forEach(function (d) { d.removeAttribute('open'); });
    }
  });
})();
