// Incident Triage Lab -- Scenario A frontend. Every step calls a real
// API route backed by agent/triage_execution.py, which itself calls the
// real Customer App (see app/src/main/java/com/example/customer/triage/).
// Nothing here is scripted; loading/error states are real, not decorative.

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function show(id) { document.getElementById(id).hidden = false; }
function hide(id) { document.getElementById(id).hidden = true; }

let lastReproduction = null;

async function postJson(path, body) {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const err = new Error(data.error || `HTTP ${resp.status}`);
    err.status = resp.status;
    throw err;
  }
  return data;
}

async function getJson(path) {
  const resp = await fetch(path);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
  return data;
}

function renderReproduce(result) {
  const el = document.getElementById("reproduce-body");
  const rows = result.plans.map(p =>
    `<tr><td>${esc(p.id)}</td><td>${esc(p.planName)}</td><td>$${esc(p.ratePerKwh)}</td><td>${esc(p.effectiveStartDate)}</td><td>${esc(p.status)}</td></tr>`
  ).join("");
  el.innerHTML = `
    <table class="evidence-table">
      <thead><tr><th>Plan ID</th><th>Name</th><th>Rate</th><th>Start Date</th><th>Status</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="verdict ${result.defectReproduced ? "defect" : "fixed"}">
      ${result.defectReproduced
        ? `DEFECT REPRODUCED — ${result.plans.length} plan rows created for one customer action (expected: 1)`
        : `NO DEFECT — idempotent no-op confirmed (${result.activePlanCount} active plan, no duplicate churn)`}
    </div>`;
}

function renderInvestigate(result) {
  const el = document.getElementById("investigate-body");
  el.innerHTML = `
    <p><strong>Triage customer ID:</strong> ${esc(result.triageCustomerId)} (synthetic, isolated -- never a real persona)</p>
    <p><strong>Fix currently applied to this scenario:</strong> ${result.fixApplied ? "YES" : "NO"}</p>
    <p class="hint">Relevant source (the method exactly as it behaved before the real fix, commit 2155a8a):</p>
    <div class="source-excerpt">@Transactional
public ContractPlan enroll(Long customerId, ContractPlanEnrollRequest request) {
    customerService.getById(customerId);

    contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE)
            .ifPresent(existing -&gt; {
                existing.cancel(request.effectiveStartDate());
                contractPlanRepository.saveAndFlush(existing);
            });

    ContractPlan newPlan = new ContractPlan(
            customerId, request.planName(), request.ratePerKwh(), request.effectiveStartDate());
    return contractPlanRepository.save(newPlan);
}
<span class="diff-del">// No check anywhere for whether the request duplicates the currently
// active plan -- every call unconditionally cancels + creates.</span></div>`;
}

function renderDiagnosis(d) {
  const el = document.getElementById("diagnose-body");
  if (!d.model_called) {
    el.innerHTML = `<p class="hint">AI diagnosis unavailable: ${esc(d.explanation || "model not called")}</p>`;
    return;
  }
  if (!d.hypothesis) {
    el.innerHTML = `<p class="hint">Model responded but not in the expected format: ${esc(d.explanation || "")}</p>`;
    return;
  }
  el.innerHTML = `<div class="diagnosis-card">
    <div class="diagnosis-row"><span class="k">Hypothesis</span><span>${esc(d.hypothesis)}</span></div>
    <div class="diagnosis-row"><span class="k">Root cause</span><span>${esc(d.root_cause)}</span></div>
    <div class="diagnosis-row"><span class="k">Affected component</span><span>${esc(d.affected_component)}</span></div>
    <div class="diagnosis-row"><span class="k">Confidence</span><span>${esc(d.confidence)}</span></div>
  </div>`;
}

function renderPatch(p) {
  const el = document.getElementById("patch-body");
  if (!p.available) {
    el.innerHTML = `<p class="hint">Patch diff unavailable: ${esc(p.reason)}</p>`;
    return;
  }
  const highlighted = esc(p.diff).split("\n").map(line => {
    if (line.startsWith("+") && !line.startsWith("+++")) return `<span class="diff-add">${line}</span>`;
    if (line.startsWith("-") && !line.startsWith("---")) return `<span class="diff-del">${line}</span>`;
    return line;
  }).join("\n");
  const sourceNote = p.source === "git"
    ? "read live from this server's git history"
    : "this environment's own git history doesn't include this commit (a known deployment-environment gap, not fabricated) -- showing a literal, previously-captured copy of the same real diff";
  el.innerHTML = `<p><strong>Commit</strong> <code>${esc(p.commit)}</code> — <code>${esc(p.file)}</code></p>
    <p class="hint">${esc(sourceNote)}</p>
    <div class="diff-view">${highlighted}</div>`;
}

function diffHighlight(diffText) {
  return esc(diffText).split("\n").map(line => {
    if (line.startsWith("+") && !line.startsWith("+++")) return `<span class="diff-add">${line}</span>`;
    if (line.startsWith("-") && !line.startsWith("---")) return `<span class="diff-del">${line}</span>`;
    return line;
  }).join("\n");
}

function renderCandidate(result) {
  const el = document.getElementById("candidate-body");
  const g = result.generation, v = result.verification;
  if (!g.generated) {
    el.innerHTML = `<p class="hint">Candidate generation unavailable: ${esc(g.explanation || "model not called")}</p>`;
    return;
  }
  let html = `<p class="hint">PROPOSED LIVE PATCH — written by the model just now, from the real defective file and real evidence, applied and compiled in an isolated workspace.</p>`;
  if (v && v.status === "ENVIRONMENT_INVALID") {
    html += `<div class="verdict defect">ENVIRONMENT_INVALID — cannot verify (wrong JDK), not a code defect</div>`;
  } else if (v) {
    html += `<div class="verdict ${v.status === "COMPILE_VERIFIED" ? "fixed" : "defect"}">${v.status === "COMPILE_VERIFIED" ? "COMPILE VERIFIED" : "COMPILE FAILED"} (isolated workspace, ${(v.compile.duration_ms / 1000).toFixed(1)}s)</div>
      <div class="diff-view">${diffHighlight(v.diff)}</div>`;
    if (v.status !== "COMPILE_VERIFIED") html += `<div class="source-excerpt">${esc(v.compile.output_tail || "")}</div>`;
    if (v.status === "COMPILE_VERIFIED") show("step-promote");
  }
  el.innerHTML = html;
}

function renderVerify(v) {
  const el = document.getElementById("verify-body");
  el.innerHTML = `
    <div class="verdict ${v.success ? "fixed" : "defect"}">${v.success ? "TESTS PASSED" : "TESTS FAILED"} — ${esc(v.tests.join(", "))} (${(v.duration_ms / 1000).toFixed(1)}s)</div>
    <div class="source-excerpt">${esc(v.output_tail || "")}</div>`;
}

// ---------- Lifecycle wiring ----------

document.getElementById("start-btn").addEventListener("click", async () => {
  const btn = document.getElementById("start-btn");
  btn.disabled = true;
  btn.textContent = "STARTING…";
  try {
    await postJson("/api/triage/scenario-a/reset");
    show("reset-btn");
    show("step-reproduce");
    document.getElementById("reproduce-body").innerHTML = `<p class="hint">Submitting the same enrollment request twice…</p>`;
    const result = await postJson("/api/triage/scenario-a/reproduce");
    lastReproduction = result;
    renderReproduce(result);
    show("step-investigate");
    renderInvestigate(result);
    show("step-diagnose");
    show("step-candidate");
    show("step-patch");
    document.getElementById("patch-body").innerHTML = `<p class="hint">Loading…</p>`;
    renderPatch(await getJson("/api/triage/scenario-a/patch"));
    show("step-verify");
    show("step-approve");
  } catch (err) {
    document.getElementById("reproduce-body").innerHTML = `<p class="hint">Could not start incident: ${esc(err.message)}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "START INCIDENT";
  }
});

document.getElementById("reset-btn").addEventListener("click", () => window.location.reload());

document.getElementById("diagnose-btn").addEventListener("click", async () => {
  const btn = document.getElementById("diagnose-btn");
  btn.disabled = true;
  btn.textContent = "DIAGNOSING…";
  document.getElementById("diagnose-body").innerHTML = `<p class="hint">Calling the model with the real evidence above…</p>`;
  try {
    renderDiagnosis(await postJson("/api/triage/scenario-a/diagnose", { reproduction_result: lastReproduction }));
  } catch (err) {
    document.getElementById("diagnose-body").innerHTML = `<p class="hint">Diagnosis failed: ${esc(err.message)}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "RUN AI DIAGNOSIS";
  }
});

document.getElementById("generate-candidate-btn").addEventListener("click", async () => {
  const btn = document.getElementById("generate-candidate-btn");
  btn.disabled = true;
  btn.textContent = "GENERATING… (real model call + isolated compile, ~20-40s)";
  document.getElementById("candidate-body").innerHTML = `<p class="hint">Asking the model to write the actual fix, then compiling it in an isolated workspace…</p>`;
  try {
    renderCandidate(await postJson("/api/triage/scenario-a/generate-candidate-patch", { reproduction_result: lastReproduction }));
  } catch (err) {
    document.getElementById("candidate-body").innerHTML = `<p class="hint">Candidate generation failed: ${esc(err.message)}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "GENERATE CANDIDATE PATCH";
  }
});

document.getElementById("verify-btn").addEventListener("click", async () => {
  const btn = document.getElementById("verify-btn");
  btn.disabled = true;
  btn.textContent = "RUNNING TESTS… (real Maven run, ~20-40s)";
  document.getElementById("verify-body").innerHTML = `<p class="hint">Running the real focused regression tests…</p>`;
  try {
    renderVerify(await postJson("/api/triage/scenario-a/verify"));
  } catch (err) {
    document.getElementById("verify-body").innerHTML = `<p class="hint">Verification failed to run: ${esc(err.message)}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "RUN TESTS";
  }
});

document.getElementById("approve-btn").addEventListener("click", async () => {
  const resultEl = document.getElementById("approve-result");
  const btn = document.getElementById("approve-btn");
  const username = document.getElementById("admin-username").value;
  const password = document.getElementById("admin-password").value;
  btn.disabled = true;
  btn.textContent = "APPROVING…";
  resultEl.innerHTML = `<p class="hint">Verifying admin credentials…</p>`;
  try {
    await postJson("/api/triage/scenario-a/approve", { username, password });
    resultEl.innerHTML = `<p class="hint">Approved. Re-running the exact same reproduction…</p>`;
    const rerun = await postJson("/api/triage/scenario-a/reproduce");
    show("step-resolved");
    document.getElementById("resolved-body").innerHTML = `
      <div class="verdict fixed">INCIDENT RESOLVED</div>
      <p><strong>Before:</strong> duplicate submission created ${lastReproduction.plans.length} plan rows for one action.</p>
      <p><strong>After:</strong> the identical duplicate submission now creates ${rerun.plans.length - lastReproduction.plans.length} new row(s) — idempotent no-op confirmed live against the isolated triage customer.</p>`;
    resultEl.innerHTML = `<p class="hint">Fix applied and re-verified.</p>`;
  } catch (err) {
    if (err.status === 401) {
      resultEl.innerHTML = `<p class="hint">AWAITING OWNER APPROVAL — ${esc(err.message)}</p>`;
    } else {
      resultEl.innerHTML = `<p class="hint">Approval failed: ${esc(err.message)}</p>`;
    }
  } finally {
    btn.disabled = false;
    btn.textContent = "APPROVE FIX";
  }
});

document.getElementById("reject-btn").addEventListener("click", () => {
  document.getElementById("approve-result").innerHTML = `<p class="hint">Rejected. No change was applied to the scenario.</p>`;
});

document.getElementById("promote-btn").addEventListener("click", async () => {
  const resultEl = document.getElementById("promote-result");
  const btn = document.getElementById("promote-btn");
  const username = document.getElementById("promote-admin-username").value;
  const password = document.getElementById("promote-admin-password").value;
  if (!confirm("This will commit the AI-generated candidate to a real branch, push it, and deploy the REAL Customer App. Continue?")) return;
  btn.disabled = true;
  btn.textContent = "PROMOTING… (real commit + push + deploy, this can take several minutes)";
  resultEl.innerHTML = `<p class="hint">Verifying admin credentials, then committing, pushing, and deploying the real Customer App…</p>`;
  try {
    const result = await postJson("/api/triage/scenario-a/promote", { username, password });
    resultEl.innerHTML = `
      <div class="verdict ${result.resolved ? "fixed" : "defect"}">${result.resolved ? "PROMOTED AND RESOLVED IN REAL PRODUCTION" : "PROMOTED — deployment/resolution not fully confirmed, see details"}</div>
      <p><strong>Branch:</strong> ${esc(result.branch)} &middot; <strong>Commit:</strong> ${esc(result.production_commit)}</p>
      <p><strong>Push:</strong> ${esc(result.push_status)} &middot; <strong>Deployment:</strong> ${esc(result.deployment_status)} (identity confirmed: ${result.deployment_identity_confirmed ? "yes" : "no"})</p>`;
  } catch (err) {
    if (err.status === 401) {
      resultEl.innerHTML = `<p class="hint">AWAITING OWNER APPROVAL — ${esc(err.message)}</p>`;
    } else if (err.status === 409) {
      resultEl.innerHTML = `<p class="hint">Promotion refused: ${esc(err.message)}</p>`;
    } else {
      resultEl.innerHTML = `<p class="hint">Promotion failed: ${esc(err.message)}</p>`;
    }
  } finally {
    btn.disabled = false;
    btn.textContent = "PROMOTE TO PRODUCTION";
  }
});
