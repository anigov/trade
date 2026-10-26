const STORAGE_KEY = 'trade-lab-last-strategy';
const tradeBody = document.getElementById('trades-body');
const finalCapitalEl = document.getElementById('final-capital');
const netPnlEl = document.getElementById('net-pnl');
const tradeCountEl = document.getElementById('trade-count');
const winRateEl = document.getElementById('win-rate');
const maxDrawdownEl = document.getElementById('max-drawdown');
const engineUniverseEl = document.getElementById('engine-universe');
const engineTitleEl = document.getElementById('engine-title');
const errorBox = document.getElementById('error-box');

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove('hidden');
}

function clearError() {
  errorBox.textContent = '';
  errorBox.classList.add('hidden');
}

function formatMoney(value) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(value || 0);
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(2)}%`;
}

function loadStrategy() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      throw new Error('No saved strategy found. Go back to Strategy Builder and save one first.');
    }

    const strategy = JSON.parse(raw);
    if (!strategy || !strategy.name) {
      throw new Error('The saved strategy is incomplete.');
    }
    return strategy;
  } catch (error) {
    throw new Error(error.message || 'Unable to load the saved strategy.');
  }
}

async function loadSampleDataset() {
  const response = await fetch('/api/ohlcv');
  if (!response.ok) {
    throw new Error('Could not load historical data from the database.');
  }

  const rows = await response.json();
  const datasetBySymbol = new Map();

  if (!Array.isArray(rows) || rows.length === 0) {
    throw new Error('No historical market data is available in the database yet.');
  }

  rows.forEach((row) => {
    const record = {
      date: row.date,
      symbol: row.symbol,
      open: Number(row.open),
      high: Number(row.high),
      low: Number(row.low),
      close: Number(row.close),
      volume: Number(row.volume),
    };

    if (!datasetBySymbol.has(record.symbol)) {
      datasetBySymbol.set(record.symbol, []);
    }

    datasetBySymbol.get(record.symbol).push(record);
  });

  return datasetBySymbol;
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function runSampleBacktest(strategy, datasetBySymbol) {
  const capital = Number(strategy.risk.capitalInr || 100000);
  const brokerage = Number(strategy.assumptions.brokeragePerOrderInr || 20);
  const maxPositions = Number(strategy.risk.maxOpenPositions || 5);
  const riskPct = Number(strategy.risk.riskPerTradePct || 1);
  const stopLossPct = Number(strategy.risk.stopLossPct || 2);
  const targetPct = Number(strategy.risk.targetPct || 4);

  const universeSelection = Array.isArray(strategy.market.universeSelection) && strategy.market.universeSelection.length
    ? strategy.market.universeSelection
    : [strategy.market.universe].filter(Boolean);

  const customSymbols = (strategy.market.customSymbols || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  const symbolList = customSymbols.length ? customSymbols : Array.from(datasetBySymbol.keys()).filter((symbol) => {
    if (!universeSelection.length || universeSelection.includes('No universe selected')) {
      return true;
    }
    return universeSelection.some((item) => item === 'NIFTY 50' || item === 'NIFTY 500' || item === 'NIFTY 100' || item === 'Midcap' || item === 'Smallcap' || item === 'Banking' || item === 'IT');
  });

  let cash = capital;
  let positions = [];
  let trades = [];

  for (const symbol of symbolList) {
    const records = datasetBySymbol.get(symbol) || [];
    if (!records.length) continue;

    for (let i = 9; i < records.length; i += 1) {
      const current = records[i];
      const window = records.slice(Math.max(0, i - 9), i + 1);
      const fastSma = average(window.slice(-5).map((entry) => entry.close));
      const slowSma = average(window.map((entry) => entry.close));
      const prevClose = records[i - 1]?.close ?? current.close;

      const openSignal = current.close > fastSma && fastSma > slowSma && current.close > prevClose;

      if (openSignal && positions.length < maxPositions) {
        const maxRisk = capital * (riskPct / 100);
        const qty = Math.max(1, Math.floor(maxRisk / (current.close * (stopLossPct / 100))));
        const tradeCost = (qty * current.close) + brokerage;
        if (tradeCost <= cash) {
          cash -= tradeCost;
          positions.push({
            symbol,
            qty,
            entryPrice: current.close,
            stopLoss: current.close * (1 - stopLossPct / 100),
            target: current.close * (1 + targetPct / 100),
            entryDate: current.date,
          });
        }
      }

      for (let j = positions.length - 1; j >= 0; j -= 1) {
        const pos = positions[j];
        if (pos.symbol !== symbol) continue;

        const currentClose = current.close;
        const shouldExit = currentClose <= pos.stopLoss || currentClose >= pos.target || i === records.length - 1;
        if (!shouldExit) continue;

        const exitValue = currentClose;
        const tradePnl = ((exitValue - pos.entryPrice) * pos.qty) - brokerage;
        cash += exitValue * pos.qty;
        trades.push({
          symbol: pos.symbol,
          side: 'LONG',
          entry: pos.entryPrice,
          exit: exitValue,
          qty: pos.qty,
          pnl: tradePnl,
          date: current.date,
        });
        positions.splice(j, 1);
      }
    }
  }

  const netPnl = trades.reduce((sum, trade) => sum + trade.pnl, 0);
  const winCount = trades.filter((trade) => trade.pnl > 0).length;
  const equityCurve = [capital];
  for (let i = 0; i < trades.length; i += 1) {
    equityCurve.push((equityCurve[equityCurve.length - 1] + trades[i].pnl) || capital);
  }
  const peak = Math.max(...equityCurve, capital);
  const trough = Math.min(...equityCurve, capital);
  const maxDrawdown = peak === 0 ? 0 : ((peak - trough) / peak) * 100;

  const resultRows = trades.map((trade) => {
    const row = document.createElement('tr');
    const pnlClass = trade.pnl >= 0 ? 'positive' : 'negative';
    row.innerHTML = `
      <td>${trade.symbol}</td>
      <td>${trade.side}</td>
      <td>₹${formatMoney(trade.entry)}</td>
      <td>₹${formatMoney(trade.exit)}</td>
      <td>${trade.qty}</td>
      <td class="${pnlClass}">₹${formatMoney(trade.pnl)}</td>
    `;
    return row;
  });

  tradeBody.replaceChildren(...resultRows);

  finalCapitalEl.textContent = `₹${formatMoney(capital + netPnl)}`;
  netPnlEl.textContent = `₹${formatMoney(netPnl)}`;
  tradeCountEl.textContent = String(trades.length);
  winRateEl.textContent = formatPercent(trades.length ? (winCount / trades.length) * 100 : 0);
  maxDrawdownEl.textContent = formatPercent(maxDrawdown);
  engineUniverseEl.textContent = universeSelection.length ? universeSelection.join(', ') : 'N/A';
  engineTitleEl.textContent = strategy.name || 'Strategy Engine';
}

async function main() {
  try {
    clearError();
    const strategy = loadStrategy();
    const datasetBySymbol = await loadSampleDataset();
    runSampleBacktest(strategy, datasetBySymbol);
  } catch (error) {
    showError(error.message || 'Unable to run the sample backtest.');
    finalCapitalEl.textContent = '₹0';
    netPnlEl.textContent = '₹0';
    tradeCountEl.textContent = '0';
    winRateEl.textContent = '0%';
    maxDrawdownEl.textContent = '0%';
    engineUniverseEl.textContent = '—';
  }
}

document.getElementById('rerun-button').addEventListener('click', () => {
  main();
});
main();
