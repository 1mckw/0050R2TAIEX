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
  liveEtf50: document.getElementById("live-etf50"),
  liveEtfInv: document.getElementById("live-etf-inv"),
  input: document.getElementById("price-input"),
  impliedEtf50: document.getElementById("implied-etf50"),
  impliedEtfInv: document.getElementById("implied-etf-inv"),
  inputLabel: document.getElementById("input-label"),
  basisWrap: document.getElementById("basis-wrap"),
  basis: document.getElementById("basis"),
  impliedTaiexLine: document.getElementById("implied-taiex-line"),
  impliedTaiex: document.getElementById("implied-taiex"),
  modeTabs: document.querySelectorAll(".mode-tab"),
  method: document.getElementById("method"),
  refreshBtn: document.getElementById("refresh-btn"),
};

function assertElements() {
  const missing = Object.entries(els)
    .filter(([key, node]) => key !== "modeTabs" && !node)
    .map(([key]) => key);
  if (missing.length) {
    throw new Error(`頁面元素缺失：${missing.join(", ")}，請重新整理或清除快取`);
  }
}

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

function normalizeData(raw) {
  if (raw.products) return raw;

  const inv = {
    symbol: raw.symbols?.etf || "00632R.TW",
    latest: raw.latest?.etf ?? raw.latest?.["0050反"],
    model: raw.model,
    scenarios: raw.scenarios,
    history: raw.history,
  };

  return {
    ...raw,
    latest: {
      taiex: raw.latest.taiex,
      "0050": raw.latest["0050"] ?? null,
      "0050反": raw.latest.etf ?? raw.latest["0050反"],
    },
    products: {
      "0050反": inv,
      ...(raw.latest["0050"] != null ? { "0050": inv } : {}),
    },
  };
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

function render() {
  if (!data?.products) return;

  const method = els.method.value;
  const inputTaiex = getInputTaiex();
  const p0050 = data.products["0050"];
  const pInv = data.products["0050反"];

  els.liveTaiex.textContent = fmt(data.latest.taiex);
  if (data.latest["0050"] != null) els.liveEtf50.textContent = fmt(data.latest["0050"]);
  if (data.latest["0050反"] != null) els.liveEtfInv.textContent = fmt(data.latest["0050反"]);

  if (p0050?.model) {
    els.impliedEtf50.textContent = fmt(impliedPrice(inputTaiex, p0050.model, method));
  }

  if (pInv?.model) {
    els.impliedEtfInv.textContent = fmt(impliedPrice(inputTaiex, pInv.model, method));
  }

  if (isTxMode()) {
    els.impliedTaiex.textContent = fmt(inputTaiex);
  }

  const updated = new Date(data.updated_at);
  els.status.textContent = `最後更新 ${updated.toLocaleString("zh-TW")}（樣本 ${data.sample.start} ~ ${data.sample.end}）`;
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
  data = normalizeData(await res.json());
  if (!data.products?.["0050"] && !data.products?.["0050反"]) {
    throw new Error("data.json 格式錯誤，請重新執行 preview.bat 更新資料");
  }
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

try {
  assertElements();

  els.modeTabs.forEach((tab) => {
    tab.addEventListener("click", () => setInputMode(tab.dataset.mode));
  });

  ["input", "change"].forEach((evt) => {
    els.input.addEventListener(evt, render);
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
      els.countdown.textContent = "";
    }
  })();
} catch (err) {
  if (els.status) {
    els.status.textContent = `初始化失敗：${err.message}`;
  }
}
