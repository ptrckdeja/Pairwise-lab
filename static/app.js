'use strict';
const $ = (s) => document.querySelector(s);
const criteria = {correctness: 'Correctness', clarity: 'Clarity', instruction_following: 'Instruction following'};
let selected = null;
let current = null;
let loading = false;
function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (cls) el.className = cls;
  return el;
}
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function message(value, error = false) {
  $('#message').textContent = value;
  $('#message').className = error ? 'error' : 'success';
}
async function refresh() {
  const [queue, summary] = await Promise.all([api('/api/comparisons'), api('/api/summary')]);
  $('#metrics').replaceChildren();
  for (const [label, value] of [['Comparisons', summary.total], ['Reviewed', summary.reviewed], ['Remaining', summary.total-summary.reviewed]]) {
    const card = node('div'); card.append(node('strong', String(value)), node('span', label)); $('#metrics').append(card);
  }
  $('#count').textContent = queue.length;
  $('#queue').replaceChildren();
  const filter = $('#filter').value;
  for (const row of queue.filter(r => filter === 'all' || (filter === 'done' ? r.reviewed : !r.reviewed))) {
    const button = node('button', undefined, row.id === selected ? 'active' : '');
    button.append(node('small', `${row.reviewed ? '✓ REVIEWED' : '○ NEEDS REVIEW'} · ${row.category}`), node('span', row.prompt));
    button.addEventListener('click', () => openComparison(row.id).catch(e => message(e.message, true)));
    $('#queue').append(button);
  }
  if (!$('#queue').children.length) $('#queue').append(node('p', 'No comparisons in this view.', 'hint'));
  $('#results').replaceChildren();
  for (const [name, stats] of Object.entries(summary.models)) {
    const row = node('tr');
    for (const value of [name, stats.appearances, stats.wins, stats.ties, stats.neither, stats.mean_score]) row.append(node('td', String(value)));
    $('#results').append(row);
  }
  if (!summary.reviewed) { const tr=node('tr'); const td=node('td','Complete a review to see results.'); td.colSpan=6; tr.append(td); $('#results').append(tr); }
}
async function openComparison(id) {
  if (loading) return;
  loading = true;
  try {
    current = await api(`/api/comparisons/${id}`); selected = id;
    $('#empty').hidden = true; $('#comparison').hidden = false;
    $('#review').reset(); $('#category').textContent = current.category;
    $('#prompt').textContent = current.prompt;
    $('#blind').textContent = current.review ? 'REVIEW SAVED · MODELS REVEALED' : 'BLIND REVIEW';
    $('#responses').replaceChildren();
    for (const side of ['a', 'b']) {
      const card = node('section', undefined, 'response');
      card.append(node('h3', `Response ${side.toUpperCase()}`));
      if (current.review) card.append(node('p', current[`model_${side}`], 'model'));
      card.append(node('pre', current[`response_${side}`]));
      for (const [key, title] of Object.entries(criteria)) {
        const label = node('label', title); const select = node('select');
        select.name = `${side}_${key}`; select.required = true;
        const placeholder=node('option', 'Choose score'); placeholder.value=''; select.append(placeholder);
        for (let i=1; i<=5; i++) { const option=node('option', String(i)); option.value=i; select.append(option); }
        select.value = current.review ? current.review.scores[side][key] : '';
        label.append(select); card.append(label);
      }
      $('#responses').append(card);
    }
    for (const el of $('#review').elements) el.disabled = Boolean(current.review);
    if (current.review) {
      for (const radio of document.querySelectorAll('[name=preference]')) radio.checked = radio.value === current.review.preference;
      $('[name=reason]').value = current.review.reason;
      message('Saved reviews are locked to preserve your original blind judgment.');
    } else message('Model identities stay hidden until your review is saved.');
    await refresh();
  } finally { loading = false; }
}
$('#review').addEventListener('submit', async event => {
  event.preventDefault();
  const id = selected;
  const data = new FormData(event.target);
  const scores = {};
  for (const side of ['a','b']) scores[side] = Object.fromEntries(Object.keys(criteria).map(key => [key, Number(data.get(`${side}_${key}`))]));
  const button = $('#review button'); button.disabled = true;
  try {
    await api(`/api/reviews/${id}`, {preference:data.get('preference'), reason:data.get('reason'), scores});
    await openComparison(id);
  } catch(e) { message(e.message,true); button.disabled=false; }
});
$('#filter').addEventListener('change', () => refresh().catch(e=>message(e.message,true)));
$('#import').addEventListener('change', async event => {
  const file=event.target.files[0]; if (!file) return;
  try {
    if (file.size > 2000000) throw new Error('Import file exceeds 2 MB');
    const result = await api('/api/import', JSON.parse(await file.text()));
    await refresh(); message(`Imported ${result.imported} comparisons. Select one from the queue.`);
  } catch(e) { message(e.message,true); }
  finally { event.target.value=''; }
});
$('#export').addEventListener('click', async () => {
  try {
    const result=await api('/api/export');
    const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
    const a=node('a'); a.href=url; a.download='pairwise-reviews.json'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  } catch(e) { message(e.message,true); }
});
refresh().catch(e=>message(e.message,true));
