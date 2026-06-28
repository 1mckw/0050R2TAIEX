const REFRESH_SEC = 60;
const DATA_URL = "data.json";
const IS_FILE_PROTOCOL = location.protocol === "file:";

let data = null;
let countdown = REFRESH_SEC;
let timer = null;

const els = {
  status: document.getElementById("status"),
  countdown: document.getElementById("countdown"),
  liveTaiex: document.getElementById("live-taiex"),
  liveEtf: document.getElementById("live-etf"),
  input: document.getElementById("price-input"),
  implied: document.getElementById("implied"),
  inputLabel: document.getElementById("input-label"),
  txMode: document.getElementById("tx-mode"),
  basis: document.getElementById("basis"),
  method: document.getElementById("method"),
  modelTable: document.getElementById("model-table"),
  scenarioTable: document.getElementById("scenario-table"),
  chart: document.getElementById("chart"),
  refreshBtn: document.getElementById("refresh-btn"),
};

function fmt(n, digits = 2) {
  return Number(n).toLocaleString("zh-TW", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function impliedPrice(taiex, model, method) {
  const { alpha, beta, ratio, ref_taiex, ref_etf } = model;
  if (method === "ratio") return taiex * ratio;
  if (method === "regression") return alpha + beta * taiex;
  return ref_etf + beta * (taiex - ref_taiex);
}

function getInputTaiex() {
  const raw = parseFloat(els.input.value);
  if (Number.isNaN(raw)) return data.latest.taiex;
  if (els.txMode.checked) {
    const basis = parseFloat(els.basis.value) || 0;
    return raw - basis;
  }
  return raw;
}

function render() {
  if (!data) return;

  const method = els.method.value;
  const model = data.model;
  const inputTaiex = getInputTaiex();

  els.liveTaiex.textContent = fmt(data.latest.taiex);
  els.liveEtf.textContent = fmt(data.latest.etf);
  els.implied.textContent = fmt(impliedPrice(inputTaiex, model, method));
  els.inputLabel.textContent = els.txMode.checked ? "輸入 台指期" : "輸入 TAIEX";

  const updated = new Date(data.updated_at);
  els.status.textContent = `最後更新 ${updated.toLocaleString("zh-TW")}（樣本 ${data.sample.start} ~ ${data.sample.end}）`;

  els.modelTable.innerHTML = `
    <tr><td>方法</td><td class="num">${method}</td></tr>
    <tr><td>參考 TAIEX</td><td class="num">${fmt(model.ref_taiex)}</td></tr>
    <tr><td>參考 0050反</td><td class="num">${fmt(model.ref_etf)}</td></tr>
    <tr><td>倍率 (0050反/TAIEX)</td><td class="num">${model.ratio.toFixed(6)}</td></tr>
    <tr><td>α</td><td class="num">${model.alpha.toFixed(4)}</td></tr>
    <tr><td>β</td><td class="num">${model.beta.toFixed(6)}</td></tr>
  `;

  els.scenarioTable.innerHTML = data.scenarios
    .map((row) => {
      const etf = impliedPrice(row.taiex, model, method);
      return `<tr>
        <td>${row.label}</td>
        <td class="num">${fmt(row.taiex)}</td>
        <td class="num">${fmt(etf)}</td>
      </tr>`;
    })
    .join("");

  const hist = data.history.slice(-30);
  const maxEtf = Math.max(...hist.map((h) => h.etf));
  const minEtf = Math.min(...hist.map((h) => h.etf));
  const span = maxEtf - minEtf || 1;
  els.chart.innerHTML = hist
    .map((h) => {
      const hPct = ((h.etf - minEtf) / span) * 100;
      return `<div class="bar" style="height:${Math.max(hPct, 4)}%" title="${h.date}: ${h.etf}"></div>`;
    })
    .join("");
}

async function loadData() {
  if (IS_FILE_PROTOCOL) {
    throw new Error("請執行 preview.bat 啟動本機伺服器，不要直接開啟 HTML 檔");
  }
  const res = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  data = await res.json();
  if (!els.input.value) {
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

["input", "change"].forEach((evt) => {
  els.input.addEventListener(evt, render);
  els.txMode.addEventListener(evt, render);
  els.basis.addEventListener(evt, render);
  els.method.addEventListener(evt, render);
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
