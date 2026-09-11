// Agentic Software Delivery — Learn V1: comprehensive clickable index +
// short definitions, driven entirely by learn-data.json. Deliberately no
// deep content yet (why-it-matters, interview answers, etc.) — the data
// model has room for it (see learn-data.json's per-topic shape), but
// nothing there today is fabricated just to look complete.

const sectionsRoot = document.getElementById("learn-sections");
const searchInput = document.getElementById("learn-search");
const countEl = document.getElementById("learn-count");

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

const EVIDENCE_CLASS = {
  "NOT USED": "ev-not-used",
  "LEARNED": "ev-learned",
  "IMPLEMENTED": "ev-implemented",
  "TESTED": "ev-tested",
  "RUNTIME VERIFIED": "ev-runtime-verified",
  "PRODUCTION VERIFIED": "ev-production-verified",
};

function topicId(sectionId, topicName) {
  return `${sectionId}__${topicName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

function renderTopic(sectionId, topic) {
  const badge = topic.evidence_status
    ? `<span class="ev-badge ${EVIDENCE_CLASS[topic.evidence_status] || ""}">${esc(topic.evidence_status)}</span>`
    : "";
  const related = topic.related && topic.related.length
    ? `<div class="topic-related">Related: ${topic.related.map(esc).join(", ")}</div>`
    : "";
  return `<div class="topic-card" id="${topicId(sectionId, topic.name)}" data-search="${esc((topic.name + " " + topic.definition).toLowerCase())}">
    <div class="topic-head"><span class="topic-name">${esc(topic.name)}</span>${badge}</div>
    <div class="topic-def">${esc(topic.definition)}</div>
    ${related}
  </div>`;
}

function renderSection(section) {
  return `<section class="panel learn-section" id="section-${esc(section.id)}">
    <h2>${esc(section.title)} <span class="hint">(${section.topics.length})</span></h2>
    <div class="topic-grid">
      ${section.topics.map(t => renderTopic(section.id, t)).join("")}
    </div>
  </section>`;
}

let DATA = null;

function applyFilter(query) {
  const q = query.trim().toLowerCase();
  let visibleTopics = 0;
  document.querySelectorAll(".learn-section").forEach(sectionEl => {
    let sectionHasMatch = false;
    sectionEl.querySelectorAll(".topic-card").forEach(card => {
      const match = !q || card.dataset.search.includes(q);
      card.style.display = match ? "" : "none";
      if (match) { sectionHasMatch = true; visibleTopics++; }
    });
    sectionEl.style.display = sectionHasMatch ? "" : "none";
  });
  countEl.textContent = q
    ? `${visibleTopics} topic(s) match "${query}"`
    : `${DATA.sections.reduce((n, s) => n + s.topics.length, 0)} topics across ${DATA.sections.length} areas`;
}

async function load() {
  const resp = await fetch("/learn-data.json");
  DATA = await resp.json();
  sectionsRoot.innerHTML = DATA.sections.map(renderSection).join("");
  applyFilter("");
  searchInput.addEventListener("input", () => applyFilter(searchInput.value));
}

load();

// ---- Deep Dive: recursive WHAT/WHY/HOW/WHEN topics (additive seed) -------
// Never touches or replaces the index above. Progressive disclosure via
// native <details>/<summary> — nothing renders open by default, so
// loading this page never dumps a wall of text at once (see the
// project's own "Do not load thousands of details simultaneously" rule).

const deepTopicsRoot = document.getElementById("deep-topics");

function renderEvidenceList(items) {
  if (!items || !items.length) return "";
  return `<div class="deep-evidence"><strong>Evidence:</strong> ${items.map(e => `<code>${esc(e)}</code>`).join(", ")}</div>`;
}

function renderStepList(label, items) {
  if (!items || !items.length) return "";
  return `<div class="deep-block"><strong>${esc(label)}:</strong><ul>${items.map(i => `<li>${esc(i)}</li>`).join("")}</ul></div>`;
}

function renderInterview(interview) {
  if (!interview) return "";
  return `<div class="deep-interview">
    <div class="deep-interview-q">Likely interview question: “${esc(interview.question)}”</div>
    <div class="deep-block"><strong>Short answer:</strong> ${esc(interview.short_answer)}</div>
    <div class="deep-block"><strong>Deep answer:</strong> ${esc(interview.deep_answer)}</div>
    ${interview.real_incident_story ? `<div class="deep-block"><strong>Real incident:</strong> ${esc(interview.real_incident_story)}</div>` : ""}
  </div>`;
}

function renderDeepTopic(topic) {
  return `<details class="deep-topic-card">
    <summary>
      <span class="deep-topic-name">${esc(topic.name)}</span>
      <span class="ev-badge ev-implemented">${esc(topic.experience_classification || "")}</span>
    </summary>
    <div class="deep-topic-body">
      <div class="deep-block"><strong>WHAT:</strong> ${esc(topic.what)}</div>
      <div class="deep-block"><strong>WHY:</strong> ${esc(topic.why)}</div>
      <div class="deep-block"><strong>HOW:</strong> ${esc(topic.how)}</div>
      <div class="deep-block"><strong>WHEN:</strong> ${esc(topic.when)}</div>
      <div class="deep-block"><strong>Our experience:</strong> ${esc(topic.our_experience)}</div>
      ${renderStepList("Development steps", topic.development_steps)}
      ${renderStepList("Failures / lessons", topic.failures_lessons)}
      ${topic.related_topics && topic.related_topics.length ? `<div class="deep-block"><strong>Related:</strong> ${topic.related_topics.map(esc).join(", ")}</div>` : ""}
      ${renderInterview(topic.interview)}
      ${renderEvidenceList(topic.evidence)}
    </div>
  </details>`;
}

function renderDeepDomain(domain) {
  return `<div class="deep-domain">
    <h3>${esc(domain.title)}</h3>
    ${domain.topics.map(renderDeepTopic).join("")}
  </div>`;
}

async function loadDeepTopics() {
  try {
    const resp = await fetch("/learn-deep-topics.json");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    deepTopicsRoot.innerHTML = data.domains.map(renderDeepDomain).join("");
  } catch (_) {
    deepTopicsRoot.innerHTML = `<p class="hint">Could not load deep-dive content. Try reloading the page.</p>`;
  }
}

loadDeepTopics();
