// /recruiters — renders agent/web/recruiters.json (agent/publish_recruiters_page.py).
// Every number shown here comes from that file; nothing is typed into the page.
// Links to pages that exist on this branch but are not yet deployed are marked
// "pending deploy" and point at the page source; at view time a HEAD request
// upgrades them to the real route if it is served.
(function () {
  "use strict";
  const main = document.getElementById("rc-main");

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else node.setAttribute(k, v);
    }
    for (const c of [].concat(children || [])) {
      if (c === null || c === undefined || c === false) continue;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return node;
  }

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function day(iso) {
    if (!iso) return "unknown date";
    const d = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso);
    return d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear();
  }
  function score(x) { return Number(x).toFixed(3).replace(/0+$/, "").replace(/\.$/, ".0"); }

  const pending = [];
  function badge(status) {
    if (status === "live") return el("span", { class: "rc-badge live", text: "Live" });
    if (status === "pending_deploy") return el("span", { class: "rc-badge pending", text: "Pending deploy", title: "Built on this branch, not yet deployed. The link opens the page source until it is." });
    if (status === "source" || status === "source_pending") return el("span", { class: "rc-badge source", text: "Source code" });
    return null;
  }
  // A link record from the build: {url, status, fallback_url?}
  function link(rec, text, extraClass) {
    const external = rec.status !== "live" && rec.status !== "pending_deploy";
    const href = rec.status === "pending_deploy" ? rec.fallback_url : rec.url;
    const a = el("a", { href: href, class: extraClass || null, target: external || rec.status === "pending_deploy" ? "_blank" : null, rel: external || rec.status === "pending_deploy" ? "noopener" : null, text: text });
    const b = badge(rec.status);
    const wrap = el("span", {}, [a, b]);
    if (rec.status === "pending_deploy") pending.push({ rec: rec, a: a, b: b });
    return wrap;
  }
  function upgradePending() {
    for (const p of pending) {
      fetch(p.rec.url, { method: "HEAD" }).then(function (r) {
        if (!r.ok) return;
        p.a.href = p.rec.url;
        p.a.removeAttribute("target");
        p.a.removeAttribute("rel");
        if (p.b) { p.b.className = "rc-badge live"; p.b.textContent = "Live"; p.b.removeAttribute("title"); }
      }).catch(function () {});
    }
  }

  function header(d) {
    const p = d.profile;
    return el("header", {}, [
      el("p", { class: "rc-eyebrow", text: "For recruiters and hiring managers" }),
      el("h1", { text: p.name }),
      el("p", { class: "rc-role", text: p.headline }),
      el("ul", { class: "rc-meta" }, [
        el("li", {}, [el("b", { text: p.location })]),
        el("li", { text: p.work_mode }),
        el("li", { text: p.languages }),
        el("li", { text: p.education }),
      ]),
      el("p", { class: "rc-nrg", text: p.nrg }),
      el("p", { class: "rc-links" }, p.links.map(function (l) { return el("a", { href: l.url, target: l.status === "external" ? "_blank" : null, rel: l.status === "external" ? "noopener" : null, text: l.label }); })),
    ]);
  }

  function headline(d) {
    const m = d.metrics, byKey = {};
    for (const h of d.headline) byKey[h.metric] = h.link;
    const recall = m.eval.metrics.find(function (x) { return x.key === "recall_at_3"; });
    const cs = m.case_study.banner;
    const t = m.triage;
    const cards = [
      el("div", { class: "rc-card" }, [
        el("span", { class: "rc-big", text: score(recall.score) }),
        el("span", { class: "rc-what", text: "Retrieval quality, measured" }),
        el("span", { class: "rc-sub", text: "Recall@3 on " + m.eval.labelled_set.retrieval_cases + " hand-labelled questions. Pass mark " + score(recall.threshold) + ". Recorded " + day(m.eval.generated_at) + "." }),
        el("span", { class: "rc-go" }, [link(byKey.eval, "See every score and question")]),
      ]),
      el("div", { class: "rc-card" }, [
        el("span", { class: "rc-big", text: cs[0].value }),
        el("span", { class: "rc-what", text: cs[0].label + ": the process is killed mid-change" }),
        el("span", { class: "rc-sub", text: cs[0].note + ". " + cs[2].label + ": " + cs[2].value.toLowerCase() + " (" + cs[2].note + ")." }),
        el("span", { class: "rc-go" }, [link(byKey.case_study, "Read the case study")]),
      ]),
      el("div", { class: "rc-card" }, [
        el("span", { class: "rc-big", text: t.java_passed + " of " + t.java_tests }),
        el("span", { class: "rc-what", text: "Defect-triage scenario tests passed" }),
        el("span", { class: "rc-sub", text: t.java_failed + " failed, " + t.java_skipped + " skipped" + (t.skip_reason ? " (" + t.skip_reason + ")" : "") + ". " + t.scenarios + " scenarios. Recorded " + day(t.generated_at) + "." }),
        el("span", { class: "rc-go" }, [link(byKey.triage, "See what ran and what did not")]),
      ]),
    ];
    return el("section", { "aria-labelledby": "rc-h-check" }, [
      el("h2", { id: "rc-h-check", text: "Three things you can check in a minute" }),
      el("p", { class: "rc-lead", text: "Each number comes from a recorded run in the repository and links to the page or file that shows it." }),
      el("div", { class: "rc-cards" }, cards),
    ]);
  }

  function postingName(d, id) {
    const p = d.postings.find(function (x) { return x.id === id; });
    return p;
  }
  function quotes(d, askedBy, count) {
    return el("details", { class: "rc-quotes" }, [
      el("summary", { text: "What the postings say (" + count + ")" }),
      el("ul", {}, askedBy.map(function (a) {
        const p = postingName(d, a.posting);
        return el("li", {}, [
          el("a", { href: p.url, target: "_blank", rel: "noopener", text: p.company }),
          ": ", el("q", { text: a.quote }),
        ]);
      })),
    ]);
  }

  function figure(d, kind) {
    const m = d.metrics;
    if (kind === "eval") {
      const rows = m.eval.metrics.map(function (x) {
        return el("tr", {}, [el("td", { text: x.label }), el("td", { class: "num", text: score(x.score) + " (pass " + (x.comparator === "==" ? "= " : "≥ ") + score(x.threshold) + ")" }), el("td", { text: x.passed ? "pass" : "FAIL" })]);
      });
      const ci = m.eval.ci_eval_step_on_master;
      const ad = m.eval.agent_decision;
      return el("span", { class: "rc-figure" }, [
        el("table", { class: "rc-metrics" }, [el("tbody", {}, rows)]),
        ad ? el("span", { class: "rc-figure", text: "Agent decision eval: " + ad.passed + " of " + ad.total + " cases passed (" + ad.label + ")." }) : null,
        el("span", { class: "rc-figure", text: "CI eval step on master: " + (ci.latest_status || "unknown") + " in the latest run (observed " + day(ci.observed_at) + "); last passed " + day(ci.last_success_at) + "." }),
      ]);
    }
    if (kind === "triage") {
      const t = m.triage;
      return el("span", { class: "rc-figure", text: t.java_passed + " of " + t.java_tests + " Java scenario tests passed, " + t.java_failed + " failed, " + t.java_skipped + " skipped." });
    }
    if (kind === "ask") {
      const a = m.ask;
      return el("span", { class: "rc-figure", text: a.strong_evidence + " of " + a.examples + " example questions answered with strong evidence; " + a.llm_calls + " model calls." });
    }
    if (kind === "case_study") {
      return el("span", { class: "rc-figure", text: m.case_study.banner.map(function (b) { return b.label + ": " + b.value; }).join(" · ") });
    }
    return null;
  }

  function requirements(d) {
    const total = d.postings_total;
    return el("section", { "aria-labelledby": "rc-h-req" }, [
      el("h2", { id: "rc-h-req", text: "What " + total + " AI engineering job postings ask for, and where to check it here" }),
      el("p", { class: "rc-lead", text: "Counts are how many of the " + total + " postings ask for each thing, in their own words (open “What the postings say”). The right-hand side links to where this portfolio shows it, and what it does not show." }),
    ].concat(d.requirements.map(function (r) {
      return el("article", { class: "rc-req" }, [
        el("div", {}, [
          el("h3", { text: r.title }),
          el("span", { class: "rc-count" }, [el("b", { text: String(r.asked_count) }), " of " + total + " postings"]),
          el("div", { class: "rc-bar", "aria-hidden": "true" }, [el("span", { style: "width:" + Math.round(100 * r.asked_count / total) + "%" })]),
        ]),
        el("ul", { class: "rc-evidence" }, r.evidence.map(function (e) {
          return el("li", {}, [link(e, e.label), e.metrics ? figure(d, e.metrics) : null]);
        })),
        quotes(d, r.asked_by, r.asked_count),
        el("p", { class: "rc-limit" }, [el("b", { text: "Limit: " }), r.limits]),
      ]);
    })));
  }

  function gaps(d) {
    return el("section", { "aria-labelledby": "rc-h-gaps" }, [
      el("h2", { id: "rc-h-gaps", text: "Not in this portfolio" }),
      el("p", { class: "rc-lead", text: "Things some of these postings ask for that this portfolio does not show. Listed so you do not have to find out later." }),
      el("div", { class: "rc-gaps" }, d.gaps.map(function (g) {
        return el("div", { class: "rc-gap" }, [
          el("h3", { text: g.title }),
          el("p", { text: g.detail }),
          quotes(d, g.asked_by, g.asked_count),
        ]);
      })),
    ]);
  }

  function postings(d) {
    return el("section", { "aria-labelledby": "rc-h-post" }, [
      el("h2", { id: "rc-h-post", text: "The " + d.postings_total + " postings" }),
      el("p", { class: "rc-lead", text: d.postings_note + " Accessed " + day(d.postings_accessed) + "; postings close, so some links may stop working." }),
      el("table", { class: "rc-table" }, [
        el("thead", {}, [el("tr", {}, [el("th", { text: "Company" }), el("th", { text: "Role" }), el("th", { text: "Where" }), el("th", { class: "rc-hide-sm", text: "Listed on" })])]),
        el("tbody", {}, d.postings.map(function (p) {
          return el("tr", {}, [
            el("td", {}, [el("a", { href: p.url, target: "_blank", rel: "noopener", text: p.company })]),
            el("td", { text: p.title }), el("td", { text: p.where }), el("td", { class: "rc-hide-sm", text: p.source }),
          ]);
        })),
      ]),
    ]);
  }

  function footer(d) {
    const online = d.link_check && d.link_check.online;
    return el("p", { class: "rc-foot" }, [
      "Built from the repository at commit " + d.commit_sha.slice(0, 7) + " on " + day(d.generated_at) + ". ",
      "Links were checked when the page was built" + (online ? " (" + day(online.checked_at) + ")" : "") + ". ",
      "Profile facts: " + d.profile.facts_source,
    ]);
  }

  fetch("/recruiters.json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (d) {
      main.textContent = "";
      [header(d), headline(d), requirements(d), gaps(d), postings(d), footer(d)].forEach(function (n) { main.appendChild(n); });
      upgradePending();
    })
    .catch(function (e) {
      main.textContent = "";
      main.appendChild(el("p", { class: "rc-hint", text: "Could not load recruiters.json (" + e.message + ")." }));
    });
})();
