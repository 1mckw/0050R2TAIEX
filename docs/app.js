const REFRESH_SEC = 60;
const DATA_URL = "data.json";
const IS_FILE_PROTOCOL = location.protocol === "file:";

let data = null;
let inputMode = "taiex";
let countdown = REFRESH_SEC;
let timer = null;

const els = {
  status: document.getElementById("status"),
  countdown: document.getElementById("countdown"),
  liveTaiex: document.getElementById("live-taiex"),
  live0050: document.getElementById("live-0050"),
  live0050inv: document.getElementById("live-0050inv"),
  input: document.getElementById("price-input"),
  implied0050: document.getElementById("implied-0050"),
  implied0050inv: document.getElementById("implied-0050inv"),
  inputLabel: document.getElementById("input-label"),
  basisWrap: document.getElementById("basis-wrap"),
  basis: document.getElementById("basis"),
  impliedTaiexLine: document.getElementById("implied-taiex-line"),
  impliedTaiex: document.getElementById("implied-taiex"),
  modeTabs: document.querySelectorAll(".mode-tab"),
  method: document.getElementById("method"),
  chartProduct: document.getElementById("chart-product"),
  model0050: document.getElementById("model-0050"),
  model0050inv: document.getElementById("model-0050inv"),
  scenarioTable: document.getElementById("scenario-table"),
  chartTitle: document.getElementById("chart-title"),
  chart: document.getElementById("chart"),
  refreshBtn: document.getElementById("refresh-btn"),
};

function fmt(n, digits = 2) {
  return Number(n).toLocaleString("zh-TW", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function isTxMode() {
  return inputMode === "tx";
}

function impliedPrice(taiex, model, method) {
  const { alpha, beta, ratio, ref_taiex, ref_etf } = model;
  if (method === "ratio") return taiex * ratio;
  if (method === "regression") return alpha + beta * taiex;
  return ref_etf + beta * (taiex - ref_taiex);
}

function getRawInput() {
  const raw = parseFloat(els.input.value);
  return Number.isNaN(raw) ? null : raw;
}

function getInputTaiex() {
  const raw = getRawInput();
  if (raw === null) return data?.latest.taiex ?? 0;
  if (isTxMode()) {
    const basis = parseFloat(els.basis.value) || 0;
    return raw - basis;
  }
  return raw;
}

function applyModeUi() {
  const tx = isTxMode();
  els.modeTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.mode === inputMode);
  });
  els.inputLabel.textContent = tx ? "台指期 價格" : "TAIEX 點位";
  els.input.placeholder = tx ? "例如 22100" : "例如 44500";
  els.basisWrap.classList.toggle("hidden", !tx);
  els.impliedTaiexLine.classList.toggle("hidden", !tx);
}

function setInputMode(mode) {
  inputMode = mode;
  applyModeUi();
  render();
}

function modelTableHtml(name, model, method) {
  return `
    <tr><td>方法</td><td class="num">${method}</td></tr>
    <tr><td>參考 TAIEX</td><td class="num">${fmt(model.ref_taiex)}</td></tr>
    <tr><td>參考 ${name}</td><td class="num">${fmt(model.ref_etf)}</td></tr>
    <tr><td>倍率 (${name}/TAIEX)</td><td class="num">${model.ratio.toFixed(6)}</td></tr>
    <tr><td>α</td><td class="num">${model.alpha.toFixed(4)}</td></tr>
    <tr><td>β</td><td class="num">${model.beta.toFixed(6)}</td></tr>
  `;
}

function renderChart(productName) {
  const hist = data.products[productName].history.slice(-30);
  const maxEtf = Math.max(...hist.map((h) => h.etf));
  const minEtf = Math.min(...hist.map((h) => h.etf));
  const span = maxEtf - minEtf || 1;
  els.chartTitle.textContent = `${productName} 近期走勢`;
  els.chart.innerHTML = hist
    .map((h) => {
      const hPct = ((h.etf - minEtf) / span) * 100;
      return `<div class="bar" style="height:${Math.max(hPct, 4)}%" title="${h.date}: ${h.etf}"></div>`;
    })
    .join("");
}

function render() {
  if (!data) return;

  const method = els.method.value;
  const inputTaiex = getInputTaiex();
  const p0050 = data.products["0050"];
  const pInv = data.products["0050反"];

  els.liveTaiex.textContent = fmt(data.latest.taiex);
  els.live0050.textContent = fmt(data.latest["0050"]);
  els.live0050inv.textContent = fmt(data.latest["0050反"]);
  els.implied0050.textContent = fmt(impliedPrice(inputTaiex, p0050.model, method));
  els.implied0050inv.textContent = fmt(impliedPrice(inputTaiex, pInv.model, method));

  if (isTxMode()) {
    els.impliedTaiex.textContent = fmt(inputTaiex);
  }

  const updated = new Date(data.updated_at);
  els.status.textContent = `最後更新 ${updated.toLocaleString("zh-TW")}（樣本 ${data.sample.start} ~ ${data.sample.end}）`;

  els.model0050.innerHTML = modelTableHtml("0050", p0050.model, method);
  els.model0050inv.innerHTML = modelTableHtml("0050反", pInv.model, method);

  els.scenarioTable.innerHTML = p0050.scenarios
    .map((row) => {
      const etf50 = impliedPrice(row.taiex, p0050.model, method);
      const etfInv = impliedPrice(row.taiex, pInv.model, method);
      return `<tr>
        <td>${row.label}</td>
        <td class="num">${fmt(row.taiex)}</td>
        <td class="num">${fmt(etf50)}</td>
        <td class="num">${fmt(etfInv)}</td>
      </tr>`;
    })
    .join("");

  renderChart(els.chartProduct.value);
}

function readUrlParams() {
  const params = new URLSearchParams(location.search);
  if (params.get("mode") === "tx") inputMode = "tx";
  const price = params.get("price");
  const basis = params.get("basis");
  if (price) els.input.value = price;
  if (basis) els.basis.value = basis;
  applyModeUi();
}

async function loadData() {
  if (IS_FILE_PROTOCOL) {
    throw new Error("請執行 preview.bat 啟動本機伺服器，不要直接開啟 HTML 檔");
  }
  const res = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  data = await res.json();
  if (!getRawInput()) {
    els.input.value = data.latest.taiex;
  }
  render();
}

function startCountdown() {
  countdown = REFRESH_SEC;
  els.countdown.textContent = `${countdown}s 後更新`;
  if (timer) clearInterval(timer);
  timer = setInterval(async () => {
    countdown -= 1;
    els.countdown.textContent = `${countdown}s 後更新`;
    if (countdown <= 0) {
      try {
        await loadData();
      } catch (err) {
        els.status.textContent = `更新失敗：${err.message}`;
      }
      countdown = REFRESH_SEC;
    }
  }, 1000);
}

els.modeTabs.forEach((tab) => {
  tab.addEventListener("click", () => setInputMode(tab.dataset.mode));
});

["input", "change"].forEach((evt) => {
  els.input.addEventListener(evt, render);
  els.basis.addEventListener(evt, render);
  els.method.addEventListener(evt, render);
  els.chartProduct.addEventListener(evt, render);
});

els.refreshBtn.addEventListener("click", async () => {
  els.refreshBtn.disabled = true;
  try {
    await loadData();
    startCountdown();
  } catch (err) {
    els.status.textContent = `更新失敗：${err.message}`;
  } finally {
    els.refreshBtn.disabled = false;
  }
});

readUrlParams();

(async () => {
  if (IS_FILE_PROTOCOL) {
    els.status.innerHTML =
      '無法預覽：請回到專案資料夾，雙擊執行 <strong>preview.bat</strong>（會開啟 http://localhost:8080）';
    els.countdown.textContent = "";
    return;
  }
  try {
    await loadData();
    startCountdown();
  } catch (err) {
    els.status.textContent = `載入失敗：${err.message}`;
  }
})();
