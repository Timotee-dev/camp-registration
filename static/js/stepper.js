/* One-question-per-page registration form.
 *
 * The server renders every question in one normal <form>; this script shows them one at a time.
 * Without JavaScript the form still works (all questions on one page). The server re-validates
 * everything, so nothing here is trusted — it only makes the experience smooth.
 */
(function () {
  'use strict';

  var form = document.getElementById('stepper');
  if (!form) return;

  var code = form.getAttribute('data-code');
  var STORE_KEY = 'nexform:' + code;
  var steps = Array.prototype.slice.call(form.querySelectorAll('.step'));
  var qSteps = steps.filter(function (s) { return s.hasAttribute('data-qid'); });
  var reviewIdx = steps.length - 1;
  var total = qSteps.length;
  var progress = document.getElementById('progress');
  var stepCount = document.getElementById('stepCount');
  var reviewList = document.getElementById('reviewList');
  var submitBtn = document.getElementById('submitBtn');
  var idx = 0;
  var returnToReview = false;
  var pointerChoice = false;
  var autoTimer = null;
  var finePointer = window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  // ------------------------------------------------------------------ helpers
  function typeOf(step) { return step.getAttribute('data-type'); }
  function isChoiceType(t) { return t === 'single_choice' || t === 'yes_no' || t === 'multi_choice'; }
  function controls(step) { return Array.prototype.slice.call(step.querySelectorAll('.q-input input, .q-input textarea, .q-input select')); }

  function valueOf(step) {
    var t = typeOf(step);
    var els = controls(step);
    if (t === 'multi_choice') return els.filter(function (e) { return e.checked; }).map(function (e) { return e.value; });
    if (t === 'single_choice' || t === 'yes_no') {
      var c = els.filter(function (e) { return e.checked; })[0];
      return c ? c.value : '';
    }
    return els[0] ? els[0].value : '';
  }

  function setValue(step, v) {
    var t = typeOf(step);
    var els = controls(step);
    if (isChoiceType(t)) {
      var vals = Array.isArray(v) ? v : [v];
      els.forEach(function (e) { e.checked = vals.indexOf(e.value) !== -1; });
    } else if (els[0] && typeof v === 'string') {
      if (els[0].tagName === 'SELECT' && !Array.prototype.some.call(els[0].options, function (o) { return o.value === v; })) return;
      els[0].value = v;
    }
  }

  function digits(s) { return (s.match(/\d/g) || []).length; }

  function validate(step) {
    var t = typeOf(step);
    var required = step.getAttribute('data-required') === '1';
    var v = valueOf(step);
    var empty = Array.isArray(v) ? v.length === 0 : !String(v).trim();
    if (empty) {
      if (!required) return '';
      if (t === 'multi_choice') return 'Please choose at least one option.';
      if (isChoiceType(t) || t === 'dropdown') return 'Please choose an option.';
      if (t === 'date') {
        var d = controls(step)[0];
        if (d && d.validity && d.validity.badInput) return 'Enter a valid date.';
      }
      return 'This question is required.';
    }
    v = String(v).trim();
    if (t === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v)) return 'Enter a valid email address, e.g. name@example.com.';
    if (t === 'phone' && (!/^[\d\s+\-().]+$/.test(v) || digits(v) < 7 || digits(v) > 15)) return 'Enter a valid phone number, e.g. 08031234567.';
    if (t === 'number' && !/^-?\d+(\.\d+)?$/.test(v.replace(/,/g, ''))) return 'Enter a number.';
    if (t === 'short_text' && v.length > 300) return 'Please keep this under 300 characters.';
    if (t === 'long_text' && v.length > 3000) return 'Please keep this under 3000 characters.';
    return '';
  }

  function showError(step, msg) {
    var p = step.querySelector('.q-error');
    if (p) p.textContent = msg || '';
    step.classList.toggle('has-error', !!msg);
    controls(step).forEach(function (e) {
      if (msg) e.setAttribute('aria-invalid', 'true'); else e.removeAttribute('aria-invalid');
    });
  }

  function focusStep(step) {
    if (!step.hasAttribute('data-qid')) {
      var b = step.querySelector('[data-next], [type=submit]');
      if (b && finePointer) b.focus({ preventScroll: true });
      return;
    }
    var els = controls(step);
    var target = els.filter(function (e) { return e.checked; })[0] || els[0];
    if (target) {
      try { target.focus({ preventScroll: true }); } catch (e) { target.focus(); }
    }
  }

  // ------------------------------------------------------------------ navigation
  function show(i, direction) {
    i = Math.max(0, Math.min(i, steps.length - 1));
    clearTimeout(autoTimer);
    steps.forEach(function (s, k) {
      var on = k === i;
      s.classList.toggle('active', on);
      s.classList.toggle('back', on && direction === 'back');
      s.setAttribute('aria-hidden', on ? 'false' : 'true');
    });
    idx = i;
    if (i === reviewIdx) buildReview();
    var pct = Math.round((i / (steps.length - 1)) * 100);
    if (progress) progress.style.width = pct + '%';
    if (stepCount) {
      var s = steps[i];
      stepCount.textContent = s.hasAttribute('data-qid') ? (qSteps.indexOf(s) + 1) + ' of ' + total
        : (i === reviewIdx ? 'Review' : '');
    }
    window.scrollTo(0, 0);
    focusStep(steps[i]);
  }

  function goTo(i, direction) {
    if (i === idx) return;
    show(i, direction);
    try { history.pushState({ nexStep: i }, ''); } catch (e) { /* ignore */ }
  }

  function next() {
    var step = steps[idx];
    if (step.hasAttribute('data-qid')) {
      var err = validate(step);
      showError(step, err);
      if (err) { focusStep(step); return; }
      save();
    }
    if (returnToReview && idx !== reviewIdx) { returnToReview = false; goTo(reviewIdx); return; }
    goTo(idx + 1);
  }

  function back() {
    returnToReview = false;
    if (idx > 0) goTo(idx - 1, 'back');
  }

  window.addEventListener('popstate', function (e) {
    var i = e.state && typeof e.state.nexStep === 'number' ? e.state.nexStep : 0;
    show(i, i < idx ? 'back' : null);
  });

  // ------------------------------------------------------------------ review
  function formatAnswer(step, v) {
    var t = typeOf(step);
    if (Array.isArray(v)) return v.join(', ');
    if (t === 'date' && v) {
      var parts = v.split('-');
      if (parts.length === 3) {
        var d = new Date(+parts[0], +parts[1] - 1, +parts[2]);
        if (!isNaN(d)) return d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' });
      }
    }
    return v;
  }

  function buildReview() {
    if (!reviewList) return;
    reviewList.innerHTML = '';
    qSteps.forEach(function (step) {
      var v = valueOf(step);
      var text = formatAnswer(step, v);
      var empty = Array.isArray(v) ? !v.length : !String(v).trim();
      var item = document.createElement('div');
      item.className = 'review-item';
      var q = document.createElement('div');
      q.className = 'rq';
      q.textContent = step.getAttribute('data-label');
      var a = document.createElement('div');
      a.className = 'ra' + (empty ? ' empty' : '');
      a.textContent = empty ? 'No answer' : text;
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn btn-sm btn-ghost edit';
      b.textContent = 'Edit';
      b.setAttribute('aria-label', 'Edit answer to: ' + step.getAttribute('data-label'));
      b.addEventListener('click', function () { returnToReview = true; goTo(steps.indexOf(step), 'back'); });
      item.appendChild(q); item.appendChild(a); item.appendChild(b);
      reviewList.appendChild(item);
    });
  }

  // ------------------------------------------------------------------ saving progress locally
  function save() {
    var data = {};
    qSteps.forEach(function (s) { data[s.getAttribute('data-qid')] = valueOf(s); });
    try { localStorage.setItem(STORE_KEY, JSON.stringify({ t: Date.now(), v: data })); } catch (e) { /* private mode etc. */ }
  }

  function restore() {
    var raw = null;
    try { raw = localStorage.getItem(STORE_KEY); } catch (e) { return false; }
    if (!raw) return false;
    try {
      var saved = JSON.parse(raw);
      if (!saved || !saved.v || Date.now() - saved.t > 7 * 864e5) return false;
      var any = false;
      qSteps.forEach(function (s) {
        var v = saved.v[s.getAttribute('data-qid')];
        if (v != null && (Array.isArray(v) ? v.length : String(v).length)) { setValue(s, v); any = true; }
      });
      return any;
    } catch (e) { return false; }
  }

  // ------------------------------------------------------------------ events
  form.addEventListener('click', function (e) {
    if (e.target.closest('[data-next]')) { e.preventDefault(); next(); }
    else if (e.target.closest('[data-back]')) { e.preventDefault(); back(); }
  });

  form.addEventListener('input', function (e) {
    var step = e.target.closest('.step');
    if (step && step.classList.contains('has-error')) showError(step, '');
    save();
  });

  form.addEventListener('pointerdown', function (e) { pointerChoice = !!e.target.closest('.choice'); }, true);

  form.addEventListener('change', function (e) {
    var step = e.target.closest('.step');
    if (!step) return;
    if (step.classList.contains('has-error')) showError(step, '');
    save();
    var t = typeOf(step);
    if ((t === 'single_choice' || t === 'yes_no') && pointerChoice && steps[idx] === step) {
      pointerChoice = false;
      clearTimeout(autoTimer);
      autoTimer = setTimeout(function () { if (steps[idx] === step) next(); }, 320);
    }
  });

  form.addEventListener('keydown', function (e) {
    var step = steps[idx];
    if (!step) return;
    var tag = e.target.tagName;
    if (e.key === 'Enter' && !e.isComposing) {
      if (tag === 'BUTTON' || tag === 'A') return;          // let buttons work normally
      if (tag === 'TEXTAREA' && (e.shiftKey || !finePointer)) return; // newline
      e.preventDefault();
      if (idx === reviewIdx) return;
      next();
      return;
    }
    // Letter shortcuts for choice questions (A, B, C…), desktop only
    var t = typeOf(step) || '';
    if (finePointer && isChoiceType(t) && /^[a-zA-Z]$/.test(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey &&
        tag !== 'TEXTAREA' && !(tag === 'INPUT' && /text|email|tel|number|date/.test(e.target.type))) {
      var k = e.key.toUpperCase().charCodeAt(0) - 65;
      var inputs = controls(step);
      var target = inputs[k];
      if (!target) return;
      e.preventDefault();
      if (t === 'multi_choice') target.checked = !target.checked;
      else target.checked = true;
      target.focus();
      showError(step, '');
      save();
      if (t !== 'multi_choice') {
        clearTimeout(autoTimer);
        autoTimer = setTimeout(function () { if (steps[idx] === step) next(); }, 320);
      }
    }
  });

  form.addEventListener('submit', function (e) {
    for (var k = 0; k < qSteps.length; k++) {
      var err = validate(qSteps[k]);
      if (err) {
        e.preventDefault();
        showError(qSteps[k], err);
        returnToReview = true;
        goTo(steps.indexOf(qSteps[k]), 'back');
        return;
      }
    }
    save();
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Submitting…'; }
  });

  // Coming back via the browser's back/forward cache: re-enable the button.
  window.addEventListener('pageshow', function (e) {
    if (e.persisted && submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Submit registration'; }
  });

  // ------------------------------------------------------------------ start
  var start = 0;
  if (form.getAttribute('data-has-errors') === '1') {
    var firstErr = qSteps.filter(function (s) { return s.classList.contains('has-error'); })[0];
    start = firstErr ? steps.indexOf(firstErr) : reviewIdx;
    if (firstErr) returnToReview = true;
    save();
  } else if (restore()) {
    var startBtn = steps[0].querySelector('[data-next]');
    if (startBtn) startBtn.textContent = 'Continue registration →';
  }
  try { history.replaceState({ nexStep: start }, ''); } catch (e) { /* ignore */ }
  show(start);
})();
