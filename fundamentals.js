const companyForm = document.querySelector('#company-form');
const companyList = document.querySelector('#company-list');
const qualifiedList = document.querySelector('#qualified-list');
const companyCount = document.querySelector('#company-count');
const qualifiedCount = document.querySelector('#qualified-count');
const companyEmpty = document.querySelector('#company-empty');
const qualifiedEmpty = document.querySelector('#qualified-empty');
const formStatus = document.querySelector('#form-status');
const screenSummary = document.querySelector('#screen-summary');
const toast = document.querySelector('#toast');
const metricFields = [
  'market_cap_cr',
  'pe_ratio',
  'roe_pct',
  'roce_pct',
  'debt_equity',
  'revenue_growth_pct',
  'profit_growth_pct',
  'promoter_holding_pct',
];
let companies = [];
let toastTimer;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('is-visible');
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove('is-visible'), 2800);
}

function formatMetric(value, suffix = '') {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toLocaleString('en-IN', { maximumFractionDigits: 2 })}${suffix}` : '—';
}

function makeCell(value, className = '') {
  const cell = document.createElement('td');
  if (className) cell.className = className;
  cell.textContent = value ?? '—';
  return cell;
}

function makeCompanyRow(company) {
  const row = document.createElement('tr');
  const companyCell = makeCell(company.company_name, 'company-name');
  companyCell.title = company.symbol;
  row.append(
    companyCell,
    makeCell(company.exchange),
    makeCell(company.sector || '—'),
    makeCell(formatMetric(company.roe_pct, '%')),
    makeCell(formatMetric(company.roce_pct, '%')),
    makeCell(formatMetric(company.pe_ratio)),
  );

  const sourceCell = document.createElement('td');
  sourceCell.className = 'source-cell';
  sourceCell.textContent = company.source;
  const date = document.createElement('span');
  date.textContent = `As of ${company.as_of_date}`;
  sourceCell.appendChild(date);
  row.appendChild(sourceCell);

  const actionCell = document.createElement('td');
  const edit = document.createElement('button');
  edit.className = 'row-actions';
  edit.type = 'button';
  edit.dataset.action = 'edit';
  edit.dataset.symbol = company.symbol;
  edit.dataset.exchange = company.exchange;
  edit.textContent = 'Edit';
  const remove = document.createElement('button');
  remove.className = 'row-actions';
  remove.type = 'button';
  remove.dataset.action = 'delete';
  remove.dataset.symbol = company.symbol;
  remove.dataset.exchange = company.exchange;
  remove.textContent = 'Delete';
  actionCell.append(edit, document.createTextNode(' '), remove);
  row.appendChild(actionCell);
  return row;
}

function getActiveFilters() {
  return Array.from(document.querySelectorAll('[data-filter]'))
    .filter((input) => input.value !== '')
    .map((input) => ({
      field: input.dataset.filter,
      operation: input.dataset.op,
      value: Number(input.value),
    }));
}

function matchesFilters(company, filters) {
  return filters.every((filter) => {
    const value = company[filter.field];
    if (value === null || value === undefined || value === '') return false;
    return filter.operation === 'min'
      ? Number(value) >= filter.value
      : Number(value) <= filter.value;
  });
}

function renderCompanies() {
  const filters = getActiveFilters();
  const qualified = companies.filter((company) => matchesFilters(company, filters));
  companyList.replaceChildren(...companies.map(makeCompanyRow));
  qualifiedList.replaceChildren(...qualified.map((company) => {
    const row = document.createElement('tr');
    const name = makeCell(company.company_name, 'company-name');
    name.title = `${company.symbol} · ${company.exchange}`;
    row.append(
      name,
      makeCell(company.sector || '—'),
      makeCell(formatMetric(company.market_cap_cr)),
      makeCell(formatMetric(company.pe_ratio)),
      makeCell(formatMetric(company.roe_pct, '%')),
      makeCell(formatMetric(company.roce_pct, '%')),
      makeCell(formatMetric(company.debt_equity)),
      makeCell(formatMetric(company.revenue_growth_pct, '%')),
      makeCell(formatMetric(company.profit_growth_pct, '%')),
    );
    const source = document.createElement('td');
    source.className = 'source-cell';
    source.textContent = company.source;
    const date = document.createElement('span');
    date.textContent = `As of ${company.as_of_date}`;
    source.appendChild(date);
    row.appendChild(source);
    return row;
  }));

  companyCount.textContent = String(companies.length);
  qualifiedCount.textContent = String(qualified.length);
  companyEmpty.hidden = companies.length > 0;
  qualifiedEmpty.hidden = qualified.length > 0;
  screenSummary.textContent = `${filters.length} active filter${filters.length === 1 ? '' : 's'} · ${companies.length} stored record${companies.length === 1 ? '' : 's'}`;
}

async function loadCompanies() {
  screenSummary.textContent = 'Loading company records…';
  try {
    const response = await fetch('/api/fundamentals', { cache: 'no-store' });
    if (!response.ok) throw new Error('Could not load fundamentals from the local database.');
    companies = await response.json();
    renderCompanies();
  } catch (error) {
    screenSummary.textContent = error.message;
    companies = [];
    renderCompanies();
  }
}

function readCompanyForm() {
  const values = Object.fromEntries(new FormData(companyForm).entries());
  const record = {
    symbol: values.symbol.trim().toUpperCase(),
    company_name: values.company_name.trim(),
    exchange: values.exchange,
    sector: values.sector.trim(),
    source: values.source.trim(),
    as_of_date: values.as_of_date,
  };
  for (const field of metricFields) {
    record[field] = values[field] === '' ? null : Number(values[field]);
  }
  return record;
}

function populateForm(company) {
  for (const [key, value] of Object.entries(company)) {
    const control = companyForm.elements.namedItem(key);
    if (control) control.value = value ?? '';
  }
  document.querySelector('#symbol').focus();
  formStatus.textContent = `Editing ${company.symbol}`;
}

companyForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!companyForm.reportValidity()) return;

  const record = readCompanyForm();
  for (const field of metricFields) {
    if (record[field] !== null && !Number.isFinite(record[field])) {
      showToast(`Enter a valid number for ${field.replaceAll('_', ' ')}.`);
      return;
    }
  }

  formStatus.textContent = 'Saving…';
  try {
    const response = await fetch('/api/fundamentals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(record),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not save company data.');
    companyForm.reset();
    formStatus.textContent = 'Saved to SQLite';
    showToast(`${record.symbol} saved to the local database.`);
    await loadCompanies();
  } catch (error) {
    formStatus.textContent = 'Save failed';
    showToast(error.message);
  }
});

document.querySelectorAll('[data-filter]').forEach((input) => {
  input.addEventListener('input', renderCompanies);
});

document.querySelector('#clear-filters').addEventListener('click', () => {
  document.querySelectorAll('[data-filter]').forEach((input) => { input.value = ''; });
  renderCompanies();
});

companyList.addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const company = companies.find((item) => item.symbol === button.dataset.symbol && item.exchange === button.dataset.exchange);
  if (!company) return;

  if (button.dataset.action === 'edit') {
    populateForm(company);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  if (button.dataset.action === 'delete' && window.confirm(`Delete ${company.company_name} (${company.exchange}:${company.symbol})?`)) {
    try {
      const params = new URLSearchParams({ symbol: company.symbol, exchange: company.exchange });
      const response = await fetch(`/api/fundamentals?${params}`, { method: 'DELETE' });
      const result = await response.json();
      if (!response.ok || !result.deleted) throw new Error(result.error || 'Could not delete company.');
      showToast(`${company.symbol} removed.`);
      await loadCompanies();
    } catch (error) {
      showToast(error.message);
    }
  }
});

loadCompanies();
