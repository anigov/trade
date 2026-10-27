const STRATEGIES_KEY = "trade-lab-strategies-v1";
const DRAFT_KEY = "trade-lab-strategy-draft-v1";
const RESULTS_KEY = "trade-lab-backtest-results-v1";
const PENDING_KEY = "trade-lab-pending-backtest-v1";
const form = document.querySelector("#strategy-form");
const savedList = document.querySelector("#saved-list");
const emptyState = document.querySelector("#empty-state");
const toast = document.querySelector("#toast");
const draftStatus = document.querySelector("#draft-status");
let toastTimer;
let activeStrategyId = null;

function readForm() {
  const values = Object.fromEntries(new FormData(form).entries());
  const selectedUniverses = Array.from(
    document.querySelectorAll('input[name="universeSelection"]:checked'),
  ).map((input) => input.value);

  const universe = selectedUniverses.length ? selectedUniverses.join(', ') : 'No universe selected';

  return {
    schemaVersion: 1,
    name: values.name.trim(),
    market: {
      exchange: values.exchange,
      universe,
      universeSelection: selectedUniverses,
      customSymbols: values.customSymbols.trim(),
      timeframe: values.timeframe,
      tradeStyle: values.tradeStyle,
    },
    rules: {
      entry: values.entryRule.trim(),
      exit: values.exitRule.trim(),
    },
    risk: {
      capitalInr: Number(values.capitalInr),
      riskPerTradePct: Number(values.riskPerTradePct),
      stopLossPct: values.stopLossPct === "" ? null : Number(values.stopLossPct),
      targetPct: values.targetPct === "" ? null : Number(values.targetPct),
      maxOpenPositions: Number(values.maxOpenPositions),
    },
    assumptions: {
      brokeragePerOrderInr: Number(values.brokeragePerOrderInr),
      slippageBps: Number(values.slippageBps),
    },
    evaluation: {
      startDate: values.startDate || null,
      endDate: values.endDate || null,
      benchmark: values.benchmark,
    },
  };
}

function readSavedStrategies() {
  try {
    const saved = JSON.parse(localStorage.getItem(STRATEGIES_KEY) || "[]");
    return Array.isArray(saved) ? saved : [];
  } catch {
    return [];
  }
}

function writeSavedStrategies(strategies) {
  localStorage.setItem(STRATEGIES_KEY, JSON.stringify(strategies));
}

function readBacktestResults() {
  try {
    const results = JSON.parse(localStorage.getItem(RESULTS_KEY) || "{}");
    return results && typeof results === "object" && !Array.isArray(results) ? results : {};
  } catch {
    return {};
  }
}

function formatInr(value) {
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0);
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
}

function setSummaryText(id, value) {
  document.getElementById(id).textContent = value;
}

function updateSummary() {
  const strategy = readForm();
  setSummaryText("summary-title", strategy.name || "Untitled strategy");
  setSummaryText(
    "summary-market",
    `${strategy.market.exchange} · ${strategy.market.universe} · ${strategy.market.timeframe}`,
  );
  setSummaryText("summary-entry", strategy.rules.entry || "No entry conditions yet.");
  setSummaryText("summary-exit", strategy.rules.exit || "No exit conditions yet.");
  setSummaryText("summary-capital", `₹${formatInr(strategy.risk.capitalInr)}`);
  setSummaryText("summary-risk", `${strategy.risk.riskPerTradePct || 0}%`);
  setSummaryText("summary-positions", String(strategy.risk.maxOpenPositions || "—"));
  setSummaryText("summary-cost", `₹${formatInr(strategy.assumptions.brokeragePerOrderInr)} / order`);
}

function makeSavedItem(record, results) {
  const item = document.createElement("li");
  item.className = "saved-item";

  const copy = document.createElement("div");
  copy.className = "saved-item-copy";
  const title = document.createElement("h3");
  title.textContent = record.strategy.name || "Untitled strategy";
  const details = document.createElement("p");
  details.textContent = `${record.strategy.market.exchange} · ${record.strategy.market.universe} · ${record.strategy.market.timeframe} · ${new Date(record.savedAt).toLocaleDateString()}`;
  copy.append(title, details);

  const result = results[record.id];
  if (result) {
    const resultSummary = document.createElement("p");
    resultSummary.className = "saved-result-summary";
    resultSummary.textContent = `Last test: ₹${formatInr(result.metrics.netPnl)} net · ${result.metrics.tradeCount} trades`;
    copy.appendChild(resultSummary);
  }

  const actions = document.createElement("div");
  actions.className = "saved-item-actions";
  const loadButton = document.createElement("button");
  loadButton.type = "button";
  loadButton.dataset.action = "load";
  loadButton.dataset.id = record.id;
  loadButton.textContent = "Load";
  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.dataset.action = "remove";
  removeButton.dataset.id = record.id;
  removeButton.textContent = "Remove";
  const testButton = document.createElement("button");
  testButton.type = "button";
  testButton.dataset.action = "test";
  testButton.dataset.id = record.id;
  testButton.textContent = "Test";
  const resultsButton = document.createElement("button");
  resultsButton.type = "button";
  resultsButton.dataset.action = "results";
  resultsButton.dataset.id = record.id;
  resultsButton.textContent = results[record.id] ? "Results" : "No results";
  resultsButton.disabled = !results[record.id];
  actions.append(loadButton, testButton, resultsButton, removeButton);
  item.append(copy, actions);
  return item;
}

function renderSavedStrategies() {
  const strategies = readSavedStrategies();
  const results = readBacktestResults();
  savedList.replaceChildren(...strategies.map((record) => makeSavedItem(record, results)));
  emptyState.hidden = strategies.length > 0;
  document.querySelector("#saved-count").textContent = String(strategies.length);
}

function populateForm(strategy) {
  const values = {
    name: strategy.name,
    exchange: strategy.market.exchange,
    customSymbols: strategy.market.customSymbols,
    timeframe: strategy.market.timeframe,
    tradeStyle: strategy.market.tradeStyle,
    entryRule: strategy.rules.entry,
    exitRule: strategy.rules.exit,
    capitalInr: strategy.risk.capitalInr,
    riskPerTradePct: strategy.risk.riskPerTradePct,
    stopLossPct: strategy.risk.stopLossPct ?? "",
    targetPct: strategy.risk.targetPct ?? "",
    maxOpenPositions: strategy.risk.maxOpenPositions,
    brokeragePerOrderInr: strategy.assumptions.brokeragePerOrderInr,
    slippageBps: strategy.assumptions.slippageBps,
    startDate: strategy.evaluation.startDate ?? "",
    endDate: strategy.evaluation.endDate ?? "",
    benchmark: strategy.evaluation.benchmark,
  };

  for (const [name, value] of Object.entries(values)) {
    const control = form.elements.namedItem(name);
    if (control) control.value = value;
  }

  const selectedUniverseValues = Array.isArray(strategy.market.universeSelection)
    ? strategy.market.universeSelection
    : [strategy.market.universe].filter(Boolean);

  document.querySelectorAll('input[name="universeSelection"]').forEach((checkbox) => {
    checkbox.checked = selectedUniverseValues.includes(checkbox.value);
  });

  updateSummary();
}

function exportStrategy() {
  if (!form.reportValidity()) return;
  const payload = {
    ...readForm(),
    exportedAt: new Date().toISOString(),
    status: "definition_only",
  };
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const filename = payload.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "strategy";
  link.href = url;
  link.download = `${filename}.json`;
  link.click();
  URL.revokeObjectURL(url);
  showToast("Strategy JSON exported.");
}

form.addEventListener("input", () => {
  updateSummary();
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(readForm()));
    draftStatus.textContent = "Draft saved locally";
  } catch {
    draftStatus.textContent = "Local storage unavailable";
  }
});

form.addEventListener("change", updateSummary);

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;

  const strategy = readForm();
  const record = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    savedAt: new Date().toISOString(),
    strategy,
  };

  try {
    writeSavedStrategies([record, ...readSavedStrategies()]);
    activeStrategyId = record.id;
    localStorage.setItem(DRAFT_KEY, JSON.stringify(strategy));
    renderSavedStrategies();
    draftStatus.textContent = "Saved in this browser";
    showToast("Strategy definition saved locally.");
  } catch {
    showToast("Could not save. Check browser storage settings.");
  }
});

savedList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const strategies = readSavedStrategies();
  const record = strategies.find((item) => item.id === button.dataset.id);

  if (button.dataset.action === "load" && record) {
    activeStrategyId = record.id;
    populateForm(record.strategy);
    draftStatus.textContent = "Loaded from this browser";
    showToast("Strategy loaded into the form.");
  }

  if ((button.dataset.action === "test" || button.dataset.action === "results") && record) {
    const mode = button.dataset.action === "results" ? "view" : "run";
    localStorage.setItem(PENDING_KEY, JSON.stringify({
      strategyId: record.id,
      strategy: record.strategy,
      mode,
    }));
    window.location.href = "strategy-engine.html";
  }

  if (button.dataset.action === "remove") {
    try {
      writeSavedStrategies(strategies.filter((item) => item.id !== button.dataset.id));
      const results = readBacktestResults();
      delete results[button.dataset.id];
      localStorage.setItem(RESULTS_KEY, JSON.stringify(results));
      renderSavedStrategies();
      showToast("Saved strategy removed.");
    } catch {
      showToast("Could not update browser storage.");
    }
  }
});

document.querySelector("#export-button").addEventListener("click", exportStrategy);

document.querySelector("#backtest-button").addEventListener("click", () => {
  if (!form.reportValidity()) return;
  const strategy = readForm();
  try {
    const strategies = readSavedStrategies();
    let record = strategies.find((item) => item.id === activeStrategyId);
    if (!record || JSON.stringify(record.strategy) !== JSON.stringify(strategy)) {
      record = {
        id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
        savedAt: new Date().toISOString(),
        strategy,
      };
      writeSavedStrategies([record, ...strategies]);
      activeStrategyId = record.id;
      renderSavedStrategies();
    }
    localStorage.setItem(PENDING_KEY, JSON.stringify({
      strategyId: record.id,
      strategy: record.strategy,
      mode: "run",
    }));
    window.location.href = "strategy-engine.html";
  } catch {
    showToast("Could not start the backtest engine from this browser.");
  }
});

document.querySelector("#reset-button").addEventListener("click", () => {
  window.setTimeout(() => {
    document.querySelectorAll('input[name="universeSelection"]').forEach((checkbox) => {
      checkbox.checked = false;
    });
    updateSummary();
    draftStatus.textContent = "Form cleared";
    try {
      localStorage.removeItem(DRAFT_KEY);
    } catch {
      // The form still clears when browser storage is unavailable.
    }
  }, 0);
});

try {
  const draft = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
  if (draft?.schemaVersion === 1) {
    populateForm(draft);
    draftStatus.textContent = "Draft restored from this browser";
  }
} catch {
  draftStatus.textContent = "Local storage unavailable";
}

renderSavedStrategies();
updateSummary();