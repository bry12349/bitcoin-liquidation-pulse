const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const number = new Intl.NumberFormat("en-US");
const charts = {};

const palette = {
  red: "#ff6b7a",
  green: "#42d392",
  blue: "#6bb9ff",
  gold: "#ffd166",
  muted: "rgba(245, 247, 251, 0.54)",
  grid: "rgba(255, 255, 255, 0.08)",
};

Chart.defaults.color = palette.muted;
Chart.defaults.font.family =
  '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", Inter, Arial, sans-serif';
Chart.defaults.plugins.legend.labels.usePointStyle = true;

function formatUsd(value) {
  return currency.format(Math.round(value || 0));
}

function formatTime(ms) {
  if (!ms) return "--";
  return new Date(ms).toLocaleTimeString("zh-CN", { hour12: false });
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function makeGradient(ctx, color) {
  const gradient = ctx.createLinearGradient(0, 0, 0, 320);
  gradient.addColorStop(0, `${color}aa`);
  gradient.addColorStop(1, `${color}12`);
  return gradient;
}

function initCharts() {
  const liquidationCtx = document.getElementById("liquidationChart").getContext("2d");
  charts.liquidations = new Chart(liquidationCtx, {
    type: "bar",
    data: {
      labels: [],
      datasets: [
        {
          label: "多头爆仓",
          data: [],
          backgroundColor: makeGradient(liquidationCtx, palette.red),
          borderColor: palette.red,
          borderWidth: 1,
          borderRadius: 9,
        },
        {
          label: "空头爆仓",
          data: [],
          backgroundColor: makeGradient(liquidationCtx, palette.green),
          borderColor: palette.green,
          borderWidth: 1,
          borderRadius: 9,
        },
      ],
    },
    options: chartOptions({ stacked: false }),
  });

  charts.split = new Chart(document.getElementById("splitChart"), {
    type: "doughnut",
    data: {
      labels: ["多头爆仓", "空头爆仓"],
      datasets: [
        {
          data: [0, 0],
          backgroundColor: [palette.red, palette.green],
          borderWidth: 0,
          hoverOffset: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 520, easing: "easeOutQuart" },
      cutout: "68%",
      plugins: { legend: { position: "bottom" } },
    },
  });

  charts.fees = new Chart(document.getElementById("feeChart"), {
    type: "line",
    data: {
      labels: ["最快", "30m", "1h", "经济", "最低"],
      datasets: [
        {
          label: "sat/vB",
          data: [],
          borderColor: palette.gold,
          backgroundColor: "rgba(255, 209, 102, 0.16)",
          fill: true,
          tension: 0.42,
          pointRadius: 4,
        },
      ],
    },
    options: chartOptions(),
  });

  charts.blocks = new Chart(document.getElementById("blockChart"), {
    type: "bar",
    data: {
      labels: [],
      datasets: [
        {
          label: "MB",
          data: [],
          backgroundColor: "rgba(107, 185, 255, 0.58)",
          borderColor: palette.blue,
          borderWidth: 1,
          borderRadius: 9,
        },
      ],
    },
    options: chartOptions(),
  });
}

function chartOptions(extra = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 520, easing: "easeOutQuart" },
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "bottom" },
      tooltip: {
        backgroundColor: "rgba(16, 19, 27, 0.94)",
        borderColor: "rgba(255,255,255,0.12)",
        borderWidth: 1,
        padding: 12,
      },
    },
    scales: {
      x: {
        stacked: extra.stacked || false,
        grid: { color: "transparent" },
      },
      y: {
        stacked: extra.stacked || false,
        beginAtZero: true,
        grid: { color: palette.grid },
        ticks: {
          callback: (value) => (value >= 1000 ? `${Math.round(value / 1000)}k` : value),
        },
      },
    },
  };
}

async function fetchSnapshot(force = false) {
  const button = document.getElementById("refreshButton");
  button.classList.add("loading");
  try {
    const response = await fetch(force ? "/api/refresh" : "/api/snapshot", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    setText("streamStatus", "离线");
    setText("coverage", error.message);
  } finally {
    setTimeout(() => button.classList.remove("loading"), 220);
  }
}

function render(data) {
  const liquidations = data.liquidations || {};
  const onchain = data.onchain || {};
  const fees = onchain.fees || {};
  const collector = data.collector || {};
  const long = liquidations.long || {};
  const short = liquidations.short || {};

  setText("streamStatus", statusLabel(collector.state));
  setText("coverage", `${liquidations.coverage?.label || "waiting"} · ${collector.message || ""}`);
  setText("longUsd", formatUsd(long.usd));
  setText("longCount", `${number.format(long.count || 0)} 笔`);
  setText("shortUsd", formatUsd(short.usd));
  setText("shortCount", `${number.format(short.count || 0)} 笔`);
  setText("netBias", biasLabel(liquidations.net_bias));
  setText("netUsd", formatUsd(Math.abs(liquidations.net_usd || 0)));
  setText("fastestFee", `${fees.fastest || 0} sat/vB`);
  setText("feePressure", onchain.fee_pressure || "quiet");
  setText("totalLiquidation", formatUsd(liquidations.total_usd || 0));
  setText("splitLabel", `${formatUsd(long.usd)} / ${formatUsd(short.usd)}`);
  setText("feeLabel", onchain.fee_pressure || "quiet");
  setText("blockLabel", `${(onchain.mempool_blocks || []).length} blocks`);
  setText("largeTxLabel", `${(onchain.large_transactions || []).length} tx`);
  setText("updatedAt", `更新 ${formatTime(data.generated_at_ms)}`);

  updateCharts(liquidations, onchain);
  renderTransactions(onchain.large_transactions || []);
}

function updateCharts(liquidations, onchain) {
  const hourly = liquidations.hourly || [];
  charts.liquidations.data.labels = hourly.map((item) => item.label);
  charts.liquidations.data.datasets[0].data = hourly.map((item) => item.long_usd);
  charts.liquidations.data.datasets[1].data = hourly.map((item) => item.short_usd);
  charts.liquidations.update();

  charts.split.data.datasets[0].data = [liquidations.long?.usd || 0, liquidations.short?.usd || 0];
  charts.split.update();

  const fees = onchain.fees || {};
  charts.fees.data.datasets[0].data = [
    fees.fastest || 0,
    fees.half_hour || 0,
    fees.hour || 0,
    fees.economy || 0,
    fees.minimum || 0,
  ];
  charts.fees.update();

  const blocks = onchain.mempool_blocks || [];
  charts.blocks.data.labels = blocks.map((item) => `#${item.index}`);
  charts.blocks.data.datasets[0].data = blocks.map((item) => item.size_mb);
  charts.blocks.update();
}

function renderTransactions(items) {
  const list = document.getElementById("largeTxList");
  if (!items.length) {
    list.innerHTML = '<div class="empty">暂无大额异动</div>';
    return;
  }
  list.innerHTML = items
    .map(
      (item) => `
        <div class="tx-item">
          <div class="tx-hash">${item.txid}</div>
          <div class="tx-btc">${item.btc} BTC</div>
          <div class="tx-meta">fee ${number.format(item.fee_sat)} sats · ${item.vsize} vB</div>
        </div>
      `,
    )
    .join("");
}

function statusLabel(state) {
  const labels = {
    idle: "待启动",
    connecting: "连接中",
    connected: "实时",
    reconnecting: "重连中",
  };
  return labels[state] || "等待中";
}

function biasLabel(value) {
  const labels = {
    "shorts squeezed": "空头挤压",
    "longs flushed": "多头踩踏",
    balanced: "均衡",
    neutral: "中性",
  };
  return labels[value] || value || "中性";
}

document.getElementById("refreshButton").addEventListener("click", () => fetchSnapshot(true));
initCharts();
fetchSnapshot(true);
setInterval(() => fetchSnapshot(false), 12_000);
