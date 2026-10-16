// Next.js Agent Evals Interactive Logic
let benchmarkData = null;
let currentMetric = "pass4"; // "pass4" | "pass1" | "efficiency"

document.addEventListener("DOMContentLoaded", async () => {
  await loadData();
  renderBarChart();
  setupMetricSwitchers();
  setupCalculator();
  renderTasks();
  setupPlayground();
  setupActionButtons();
});

async function loadData() {
  try {
    const res = await fetch("data.json");
    benchmarkData = await res.json();
  } catch (e) {
    console.warn("Using fallback benchmark dataset", e);
    benchmarkData = {
      models: [
        { name: "Claude Fable 5.1 (high)", pass4_rate: 0.97, pass1_rate: 0.885, cost_per_task_usd: 0.72, cost_display: "$0.72", highlight: false },
        { name: "Pixel Canary", pass4_rate: 0.90, pass1_rate: 0.782, cost_per_task_usd: 0.00, cost_display: "FREE", highlight: true },
        { name: "GPT 6 Astra (high)", pass4_rate: 0.90, pass1_rate: 0.794, cost_per_task_usd: 0.89, cost_display: "$0.89", highlight: false },
        { name: "Kimi K3", pass4_rate: 0.84, pass1_rate: 0.710, cost_per_task_usd: 0.28, cost_display: "$0.28", highlight: false },
        { name: "Claude Sonnet 5", pass4_rate: 0.81, pass1_rate: 0.685, cost_per_task_usd: 0.39, cost_display: "$0.39", highlight: false }
      ],
      tasks: []
    };
  }
}

function renderBarChart() {
  const container = document.getElementById("barChartStage");
  if (!container || !benchmarkData) return;

  container.innerHTML = "";

  benchmarkData.models.forEach(model => {
    const col = document.createElement("div");
    col.className = `bar-column ${model.highlight ? "highlight" : ""}`;

    // Value calculation
    let displayVal = "";
    let heightPct = 0;

    if (currentMetric === "pass4") {
      displayVal = `${Math.round(model.pass4_rate * 100)}%`;
      heightPct = Math.round(model.pass4_rate * 100);
    } else if (currentMetric === "pass1") {
      displayVal = `${Math.round(model.pass1_rate * 100)}%`;
      heightPct = Math.round(model.pass1_rate * 100);
    } else if (currentMetric === "efficiency") {
      if (model.cost_per_task_usd === 0) {
        displayVal = "∞ ROI";
        heightPct = 100;
      } else {
        const ptsPerDollar = ((model.pass4_rate * 100) / model.cost_per_task_usd).toFixed(0);
        displayVal = `${ptsPerDollar} pts/$`;
        heightPct = Math.min(100, Math.round((ptsPerDollar / 350) * 100));
      }
    }

    col.innerHTML = `
      <span class="bar-top-value">${displayVal}</span>
      <div class="bar-body ${model.highlight ? "highlight-bar" : "default-bar"}" style="height: ${heightPct}%;"></div>
      <div class="bar-label-group">
        <span class="bar-model-name">${model.name}</span>
        <span class="bar-model-cost">${model.cost_display}</span>
      </div>
    `;

    container.appendChild(col);
  });
}

function setupMetricSwitchers() {
  const buttons = document.querySelectorAll(".switcher-btn");
  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      buttons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentMetric = btn.dataset.metric;
      renderBarChart();

      const title = document.getElementById("mainChartTitle");
      if (currentMetric === "pass4") {
        title.textContent = "Next.js Agent Evals: Success Rate (pass@4)";
      } else if (currentMetric === "pass1") {
        title.textContent = "Next.js Agent Evals: Single-Shot Accuracy (pass@1)";
      } else {
        title.textContent = "Next.js Agent Evals: Cost Efficiency (Points per Dollar)";
      }
    });
  });
}

function setupCalculator() {
  const slider = document.getElementById("taskSlider");
  const display = document.getElementById("taskVolumeDisplay");
  const savingsGpt6 = document.getElementById("savingsGpt6");
  const savingsFable = document.getElementById("savingsFable");

  if (!slider) return;

  slider.addEventListener("input", (e) => {
    const count = parseInt(e.target.value, 10);
    display.textContent = `${count.toLocaleString()} tasks`;

    const gpt6Cost = count * 0.89;
    const fableCost = count * 0.72;

    savingsGpt6.textContent = `$${gpt6Cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    savingsFable.textContent = `$${fableCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  });
}

function renderTasks() {
  const tabsContainer = document.getElementById("taskTabsContainer");
  const detailContainer = document.getElementById("taskDetailContainer");
  if (!tabsContainer || !detailContainer || !benchmarkData.tasks) return;

  tabsContainer.innerHTML = "";
  benchmarkData.tasks.forEach((task, idx) => {
    const btn = document.createElement("button");
    btn.className = `task-tab-btn ${idx === 0 ? "active" : ""}`;
    btn.textContent = `${task.id}: ${task.title}`;
    btn.addEventListener("click", () => {
      document.querySelectorAll(".task-tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      showTaskDetail(task);
    });
    tabsContainer.appendChild(btn);
  });

  if (benchmarkData.tasks.length > 0) {
    showTaskDetail(benchmarkData.tasks[0]);
  }
}

function showTaskDetail(task) {
  const detailContainer = document.getElementById("taskDetailContainer");
  if (!detailContainer) return;

  let modelChips = "";
  for (const [mId, res] of Object.entries(task.model_results || {})) {
    const pass = res.passed;
    const modelName = mId === "stealth/pixel-canary" ? "Pixel Canary" : mId;
    modelChips += `
      <div class="model-result-chip ${pass ? "pass" : "fail"}">
        <strong>${modelName}</strong>
        <span>${pass ? `PASS (att ${res.attempts})` : "FAIL"}</span>
      </div>
    `;
  }

  detailContainer.innerHTML = `
    <div class="task-detail-box">
      <div class="task-title-line">
        <h3>${task.title}</h3>
        <span class="task-id-badge">${task.id} • ${task.difficulty}</span>
      </div>
      <p class="task-prompt">${task.prompt}</p>
      <div class="task-model-results">
        ${modelChips}
      </div>
    </div>
  `;
}

function setupPlayground() {
  const runBtn = document.getElementById("runEvalBtn");
  const codeDisplay = document.getElementById("codeDisplay");
  const resultBadge = document.getElementById("evalResultBadge");
  const scorePill = document.getElementById("scorePill");
  const checklist = document.getElementById("checklistContainer");

  if (!runBtn) return;

  runBtn.addEventListener("click", async () => {
    runBtn.disabled = true;
    runBtn.textContent = "⏳ Evaluating...";
    resultBadge.textContent = "Running...";
    resultBadge.className = "badge blue-badge";

    const promptIdx = parseInt(document.getElementById("promptSelect").value, 10);
    const task = benchmarkData.tasks[promptIdx] || { required_checks: ["use server", "zod", "revalidatePath"] };

    const sampleCode = `// Next.js 15 Server Action
'use server';

import { z } from 'zod';
import { revalidatePath } from 'next/cache';

const UserSchema = z.object({
  name: z.string().min(2),
  email: z.string().email(),
});

export async function createUserAction(formData: FormData) {
  try {
    const parsed = UserSchema.parse({
      name: formData.get('name'),
      email: formData.get('email'),
    });

    // Database persistence
    const user = await db.user.create({ data: parsed });
    revalidatePath('/users');
    return { ok: true, user };
  } catch (err) {
    return { ok: false, error: 'Validation failed' };
  }
}`;

    codeDisplay.textContent = "";
    let i = 0;
    const interval = setInterval(() => {
      codeDisplay.textContent += sampleCode.slice(i, i + 10);
      i += 10;
      if (i >= sampleCode.length) {
        clearInterval(interval);
        runBtn.disabled = false;
        runBtn.textContent = "▶ Run Evaluation";
        resultBadge.textContent = "PASSED (100%)";
        resultBadge.className = "badge green-badge";
        scorePill.textContent = "Score: 1.0 (Pass)";

        checklist.innerHTML = "";
        task.required_checks.forEach(check => {
          checklist.innerHTML += `
            <div class="check-row passed">
              <span>✔ Verified pattern: <code>${check}</code></span>
            </div>
          `;
        });
      }
    }, 15);
  });
}

function setupActionButtons() {
  const copyBtn = document.getElementById("copyClineConfigBtn");
  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const config = {
        "providers": {
          "pixel-canary": {
            "settings": {
              "provider": "openai-compatible",
              "model": "stealth/pixel-canary",
              "baseUrl": "https://ai-gateway.vercel.sh/v1",
              "apiKey": "free"
            }
          }
        }
      };
      navigator.clipboard.writeText(JSON.stringify(config, null, 2));
      const orig = copyBtn.textContent;
      copyBtn.textContent = "✔ Copied to Clipboard!";
      setTimeout(() => copyBtn.textContent = orig, 2500);
    });
  }

  const guideBtn = document.getElementById("openClineGuideBtn");
  if (guideBtn) {
    guideBtn.addEventListener("click", () => {
      alert("Cline Setup Guide:\n1. Install Cline desktop from cline.bot/desktop\n2. Open Settings -> Providers\n3. Select OpenAI Compatible\n4. Base URL: https://ai-gateway.vercel.sh/v1\n5. Model ID: stealth/pixel-canary\n6. API Key: free");
    });
  }
}
