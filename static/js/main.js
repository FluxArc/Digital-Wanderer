document.addEventListener('DOMContentLoaded', function(){
  const toggle = document.getElementById('theme-toggle');
  const currentTheme = localStorage.getItem('dw-theme') || 'light';
  document.documentElement.setAttribute('data-theme', currentTheme);
  toggle.textContent = currentTheme === 'light' ? '🌙' : '☀️';
  toggle.onclick = () => {
    const newTheme = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('dw-theme', newTheme);
    toggle.textContent = newTheme === 'light' ? '🌙' : '☀️';
  };

  const form = document.getElementById('filter-form');
  const formMobile = document.getElementById('filter-form-mobile');
  [form, formMobile].forEach(f => f.addEventListener('submit', handleSearch));

  document.getElementById('copy-all').addEventListener('click', () => {
    const urls = Array.from(document.querySelectorAll('.copy-btn')).map(btn => btn.dataset.url);
    if(urls.length) {
      navigator.clipboard.writeText(urls.join('\n'));
      alert('Copied all links!');
    }
  });

  loadHistory();
  updateHistoryUI();
});

function handleSearch(event) {
  event.preventDefault();
  const formEl = event.target;
  const data = new FormData(formEl);

  document.getElementById('spinner').classList.remove('d-none');
  document.getElementById('results').innerHTML = '';

  fetch('/search', { method: 'POST', body: data })
    .then(res => res.json())
    .then(json => {
      document.getElementById('spinner').classList.add('d-none');
      renderResults(json.results);
      saveHistory(json.params);
      updateHistoryUI();
    });
}

function renderResults(results) {
  const container = document.getElementById('results');
  results.forEach(item => {
    const card = document.createElement('div');
    card.className = 'card mb-2';
    const body = document.createElement('div');
    body.className = 'card-body';
    const title = document.createElement('h6');
    title.className = 'card-title';
    title.textContent = item.label;
    const link = document.createElement('a');
    link.href = item.url;
    link.target = '_blank';
    link.textContent = item.url;

    body.appendChild(title);
    body.appendChild(link);

    if(item.status !== null) {
      const info = document.createElement('p');
      info.className = 'small';
      info.textContent = `Status: ${item.status}` + (item.title ? ` | ${item.title}` : '');
      body.appendChild(info);
    }

    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn btn-sm btn-outline-primary copy-btn';
    copyBtn.textContent = 'Copy';
    copyBtn.dataset.url = item.url;
    copyBtn.onclick = () => navigator.clipboard.writeText(item.url);

    body.appendChild(copyBtn);
    card.appendChild(body);
    container.appendChild(card);
  });
}

function saveHistory(params) {
  let history = JSON.parse(localStorage.getItem('dw_history') || '[]');
  const entry = JSON.stringify(params);
  history = history.filter(h => JSON.stringify(h) !== entry);
  history.unshift(params);
  if(history.length > 5) history.pop();
  localStorage.setItem('dw_history', JSON.stringify(history));
}

function updateHistoryUI() {
  const list = document.getElementById('history-list');
  list.innerHTML = '';
  const history = JSON.parse(localStorage.getItem('dw_history') || '[]');
  history.forEach(params => {
    const li = document.createElement('li');
    li.className = 'list-group-item list-group-item-action';
    li.textContent = `${params.category || 'All'} | ${params.keywords} | engines: ${params.selected_engines.join(', ')}`;
    li.onclick = () => {
      const form = document.getElementById('filter-form');
      form.category.value = params.category;
      form.keywords.value = params.keywords;
      ['check_live','discover','require_frontend'].forEach(name => {
        form[name].checked = params[name];
      });
      document.querySelectorAll('[name="engines"]').forEach(e => {
        e.checked = params.selected_engines.includes(e.value);
      });
      handleSearch({target:form, preventDefault: () => {}});
    };
    list.appendChild(li);
  });
}

function loadHistory() {
  if(!localStorage.getItem('dw_theme')) localStorage.setItem('dw_theme', 'light');
}
