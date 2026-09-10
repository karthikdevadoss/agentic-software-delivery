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
