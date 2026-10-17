/* Form builder: edit the list of questions, then save it in one request. */
(function () {
  'use strict';

  var root = document.getElementById('builder');
  if (!root) return;

  var CFG = JSON.parse(document.getElementById('builder-config').textContent);
  var TYPES = CFG.types || {};
  var CHOICE = CFG.choiceTypes || [];
  var UNIQUE = CFG.uniqueTypes || [];
  var ICONS = {
    short_text: 'Aa', long_text: '¶', email: '@', phone: '☎', number: '#', date: '📅',
    single_choice: '◉', dropdown: '▾', multi_choice: '☑', yes_no: '✓✗'
  };
  var DEFAULT_LABELS = {
    short_text: 'Your question', long_text: 'Your question', email: 'Email address', phone: 'Phone number',
    number: 'How many?', date: 'Date', single_choice: 'Choose one', dropdown: 'Select an option',
    multi_choice: 'Select all that apply', yes_no: 'Yes or no?'
  };

  var api = root.getAttribute('data-api');
  var list = document.getElementById('qlist');
  var saveBtn = document.getElementById('saveBtn');
  var saveState = document.getElementById('saveState');
  var questions = JSON.parse(document.getElementById('questions-data').textContent);
  var uid = 0;
  questions.forEach(function (q) { q._k = ++uid; });
  var dirty = false, saving = false, errorsByKey = {};

  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k === 'class') n.className = attrs[k];
      else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] === true) n.setAttribute(k, '');
      else if (attrs[k] !== false && attrs[k] != null) n.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }

  function setDirty(v) {
    dirty = v;
    saveState.textContent = v ? 'Unsaved changes' : 'All changes saved';
    saveState.classList.toggle('dirty', v);
  }

  function isChoice(t) { return CHOICE.indexOf(t) !== -1; }

  // ------------------------------------------------------------------ render
  function render(focusKey, focusSel) {
    list.innerHTML = '';
    if (!questions.length) {
      list.appendChild(el('div', { class: 'empty-state', style: 'padding:36px 20px' }, [
        el('h3', { text: 'No questions yet' }),
        el('p', { class: 'muted small', style: 'margin:0', text: 'Add your first question below.' })
      ]));
    }
    questions.forEach(function (q, i) { list.appendChild(card(q, i)); });
    if (focusKey) {
      var c = list.querySelector('[data-k="' + focusKey + '"]');
      var f = c && c.querySelector(focusSel || '.qlabel');
      if (f) { f.focus(); if (f.select && focusSel !== '.opt-input:last-of-type') f.select(); }
      if (c && c.scrollIntoView) c.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  function card(q, i) {
    var err = errorsByKey[q._k];
    var typeSel = el('select', { class: 'qtype', 'aria-label': 'Question type' });
    Object.keys(TYPES).forEach(function (t) {
      var o = el('option', { value: t, text: TYPES[t] });
      if (t === q.qtype) o.selected = true;
      typeSel.appendChild(o);
    });
    typeSel.addEventListener('change', function () {
      var wasChoice = isChoice(q.qtype);
      q.qtype = typeSel.value;
      if (isChoice(q.qtype) && !wasChoice && (!q.options || !q.options.length)) q.options = ['Option 1', 'Option 2'];
      if (UNIQUE.indexOf(q.qtype) === -1) q.unique = false;
      setDirty(true); render(q._k, '.qtype');
    });

    var tools = el('div', { class: 'qtools' }, [
      el('button', { type: 'button', class: 'icon-btn', title: 'Move up', 'aria-label': 'Move up', disabled: i === 0, text: '↑',
        onclick: function () { move(i, -1); } }),
      el('button', { type: 'button', class: 'icon-btn', title: 'Move down', 'aria-label': 'Move down', disabled: i === questions.length - 1, text: '↓',
        onclick: function () { move(i, 1); } }),
      el('button', { type: 'button', class: 'icon-btn', title: 'Duplicate', 'aria-label': 'Duplicate question', text: '⧉',
        onclick: function () { duplicate(i); } }),
      el('button', { type: 'button', class: 'icon-btn', title: 'Delete', 'aria-label': 'Delete question', text: '✕',
        onclick: function () { remove(i); } })
    ]);

    var label = el('input', { type: 'text', class: 'qlabel', value: q.label, maxlength: 300, placeholder: 'Type your question',
      'aria-label': 'Question ' + (i + 1) + ' text' });
    label.addEventListener('input', function () { q.label = label.value; setDirty(true); clearErr(q, label); });

    var help = el('input', { type: 'text', class: 'qhelp', value: q.help_text || '', maxlength: 300,
      placeholder: 'Description or hint (optional)', 'aria-label': 'Question ' + (i + 1) + ' description' });
    help.addEventListener('input', function () { q.help_text = help.value; setDirty(true); });

    var body = [el('div', { class: 'qtop' }, [el('span', { class: 'qnum', text: String(i + 1) }), typeSel, tools]), label, help];

    if (isChoice(q.qtype)) body.push(optionsEditor(q));
    if (q.qtype === 'yes_no') body.push(el('p', { class: 'small muted', style: 'margin:0', text: 'People will choose Yes or No.' }));
    if (err) body.push(el('p', { class: 'qerr', role: 'alert', text: err }));

    var req = toggle('Required', q.required, function (v) { q.required = v; });
    var foot = [req];
    if (UNIQUE.indexOf(q.qtype) !== -1) {
      foot.push(toggle('No duplicates', q.unique, function (v) { q.unique = v; },
        'Reject a registration if someone already used this answer'));
    }
    if (q.answers) foot.push(el('span', { class: 'answered', text: q.answers + ' answer' + (q.answers === 1 ? '' : 's') }));
    body.push(el('div', { class: 'qfoot' }, foot));

    return el('div', { class: 'qcard' + (err ? ' invalid' : ''), 'data-k': q._k }, body);
  }

  function toggle(text, checked, onChange, title) {
    var input = el('input', { type: 'checkbox' });
    input.checked = !!checked;
    input.addEventListener('change', function () { onChange(input.checked); setDirty(true); });
    return el('label', { class: 'switch', title: title || null }, [input, el('span', { class: 'track' }), text]);
  }

  function optionsEditor(q) {
    var wrap = el('div', { class: 'opts' });
    var sq = q.qtype === 'multi_choice';
    (q.options || []).forEach(function (opt, j) {
      var inp = el('input', { type: 'text', class: 'opt-input', value: opt, maxlength: 200, 'aria-label': 'Option ' + (j + 1) });
      inp.addEventListener('input', function () { q.options[j] = inp.value; setDirty(true); clearErr(q, inp); });
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); q.options.splice(j + 1, 0, ''); setDirty(true); render(q._k); focusOpt(q, j + 1); }
        if (e.key === 'Backspace' && !inp.value && q.options.length > 1) { e.preventDefault(); q.options.splice(j, 1); setDirty(true); render(q._k); focusOpt(q, Math.max(0, j - 1)); }
      });
      wrap.appendChild(el('div', { class: 'opt' }, [
        el('span', { class: 'dot' + (sq ? ' sq' : '') }), inp,
        el('button', { type: 'button', class: 'icon-btn', title: 'Remove option', 'aria-label': 'Remove option ' + (j + 1),
          disabled: q.options.length <= 1, text: '✕',
          onclick: function () { q.options.splice(j, 1); setDirty(true); render(q._k); } })
      ]));
    });
    wrap.appendChild(el('div', {}, [el('button', { type: 'button', class: 'link-btn small', text: '+ Add option',
      onclick: function () { q.options.push(''); setDirty(true); render(q._k); focusOpt(q, q.options.length - 1); } })]));
    return wrap;
  }

  function focusOpt(q, j) {
    var c = list.querySelector('[data-k="' + q._k + '"]');
    var inputs = c ? c.querySelectorAll('.opt-input') : [];
    if (inputs[j]) inputs[j].focus();
  }

  function clearErr(q, input) {
    if (errorsByKey[q._k]) {
      delete errorsByKey[q._k];
      var c = input.closest('.qcard');
      c.classList.remove('invalid');
      var p = c.querySelector('.qerr');
      if (p) p.remove();
    }
  }

  // ------------------------------------------------------------------ actions
  function move(i, d) {
    var j = i + d;
    if (j < 0 || j >= questions.length) return;
    var t = questions[i]; questions[i] = questions[j]; questions[j] = t;
    setDirty(true); render();
    var c = list.querySelector('[data-k="' + t._k + '"]');
    var b = c && c.querySelectorAll('.qtools .icon-btn')[d < 0 ? 0 : 1];
    if (b && !b.disabled) b.focus(); else if (c) c.querySelector('.qlabel').focus();
  }

  function duplicate(i) {
    var src = questions[i];
    var copy = JSON.parse(JSON.stringify(src));
    delete copy.id; copy.answers = 0; copy._k = ++uid; copy.unique = false;
    questions.splice(i + 1, 0, copy);
    setDirty(true); render(copy._k);
  }

  function remove(i) {
    var q = questions[i];
    if (q.answers) {
      if (!confirm('"' + (q.label || 'This question') + '" already has ' + q.answers + ' answer(s).\n\n' +
        'It will be removed from the form, but the answers already given will stay in your registrations and Excel download.\n\nRemove it?')) return;
    }
    questions.splice(i, 1);
    delete errorsByKey[q._k];
    setDirty(true); render();
    toast('Question removed — click Save to apply');
  }

  function add(type) {
    var q = { qtype: type, label: DEFAULT_LABELS[type] || 'Your question', help_text: '', required: true, unique: false,
      options: isChoice(type) ? ['Option 1', 'Option 2'] : [], answers: 0, _k: ++uid };
    questions.push(q);
    setDirty(true); render(q._k);
  }

  document.querySelectorAll('#addq button').forEach(function (b) {
    var ico = b.querySelector('.ico');
    if (ico) ico.textContent = ICONS[b.getAttribute('data-type')] || '•';
    b.addEventListener('click', function () { add(b.getAttribute('data-type')); });
  });

  // ------------------------------------------------------------------ validation + save
  function validate() {
    errorsByKey = {};
    questions.forEach(function (q) {
      if (!String(q.label || '').trim()) { errorsByKey[q._k] = 'Every question needs a question text.'; return; }
      if (isChoice(q.qtype)) {
        var opts = (q.options || []).map(function (o) { return String(o).trim(); }).filter(Boolean);
        if (!opts.length) { errorsByKey[q._k] = 'Add at least one option.'; return; }
        var low = opts.map(function (o) { return o.toLowerCase(); });
        if (low.some(function (o, k) { return low.indexOf(o) !== k; })) errorsByKey[q._k] = 'Two options have the same text.';
      }
    });
    return Object.keys(errorsByKey).length === 0;
  }

  function payload() {
    return questions.map(function (q) {
      return { id: q.id || null, qtype: q.qtype, label: q.label, help_text: q.help_text || '', required: !!q.required,
        unique: !!q.unique, options: isChoice(q.qtype) ? (q.options || []).filter(function (o) { return String(o).trim(); }) : [] };
    });
  }

  function save() {
    if (saving) return;
    if (!validate()) {
      render();
      var first = list.querySelector('.qcard.invalid');
      if (first) { first.scrollIntoView({ block: 'center', behavior: 'smooth' }); var f = first.querySelector('.qlabel'); f && f.focus(); }
      toast('Please fix the highlighted question', true);
      return;
    }
    saving = true;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';
    fetch(api, {
      method: 'PUT', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf(), 'Accept': 'application/json' },
      body: JSON.stringify({ questions: payload() })
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) { return { ok: r.ok, status: r.status, data: data }; });
    }).then(function (res) {
      if (res.ok) {
        var fresh = res.data.questions || [];
        fresh.forEach(function (q, k) { q._k = questions[k] ? questions[k]._k : ++uid; });
        questions = fresh;
        errorsByKey = {};
        setDirty(false); render();
        toast('Saved ✓');
      } else if (res.status === 403) {
        toast('Your session expired. Please log in again.', true);
      } else {
        (res.data.errors || []).forEach(function (e) {
          var q = questions[e.index];
          if (!q) return;
          var msgs = [];
          Object.keys(e.errors || {}).forEach(function (f) { msgs = msgs.concat(e.errors[f]); });
          errorsByKey[q._k] = msgs.join(' ') || 'Please check this question.';
        });
        render();
        toast(res.data.detail || 'Could not save. Please try again.', true);
      }
    }).catch(function () {
      toast('No internet connection? Your changes are still here — try saving again.', true);
    }).then(function () {
      saving = false;
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save questions';
    });
  }

  saveBtn.addEventListener('click', save);
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) { e.preventDefault(); save(); }
  });
  window.addEventListener('beforeunload', function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });
  document.getElementById('previewBtn').addEventListener('click', function (e) {
    if (dirty && !confirm('You have unsaved changes. The preview shows the last saved version.\n\nOpen the preview anyway?')) e.preventDefault();
  });

  render();
})();
