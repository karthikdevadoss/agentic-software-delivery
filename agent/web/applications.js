// /applications — owner-facing application pack review.
// Gate: page and data require ?k=<APPLICATIONS_REVIEW_TOKEN>. No public nav link.
// Approve records Owner yes + timestamp into the apply queue; this page never
// submits an application to an employer.
(function () {
  "use strict";
  const main = document.getElementById("ap-main");
  const params = new URLSearchParams(window.location.search);
  const key = params.get("k") || "";
  const queueById = {};

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "html") node.innerHTML = v;
      else node.setAttribute(k, v);
    }
    for (const c of [].concat(children || [])) {
      if (c === null || c === undefined || c === false) continue;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return node;
  }

  function withKey(path) {
    const u = new URL(path, window.location.origin);
    if (key) u.searchParams.set("k", key);
    return u.pathname + u.search;
  }

  function downloadText(filename, text) {
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  function statusLabel(item) {
    if (!item) return "";
    const st = item.status || "";
    if (st === "pending_apply" || st === "approved") {
      return "Approved · queued for Mahadeva";
    }
    if (st === "applied") return "Applied";
    if (st === "failed") return "Apply failed";
    return st;
  }

  function statusClass(item) {
    if (!item) return "";
    const st = item.status || "";
    if (st === "applied") return "ap-status ap-status-ok";
    if (st === "failed") return "ap-status ap-status-fail";
    return "ap-status ap-status-queued";
  }

  function setStatusEl(statusEl, item) {
    statusEl.textContent = statusLabel(item);
    statusEl.className = statusClass(item);
    statusEl.hidden = !item;
  }

  function render(data) {
    main.textContent = "";
    main.appendChild(el("p", { class: "ap-eyebrow", text: "Owner only · direct URL" }));
    main.appendChild(el("h1", { text: data.title || "Applications Review" }));
    main.appendChild(el("p", { class: "ap-lead", text: data.description || "" }));
    main.appendChild(el("p", {
      class: "ap-meta",
      text: data.count + " packs · as of " + (data.as_of || "") +
        " · newest posted first. Tap Approve once to queue; Mahadeva applies later. This page never submits."
    }));

    const list = el("div", { class: "ap-list", role: "list" });
    data.packs.forEach(function (p) {
      const qItem = queueById[p.id] || null;
      const row = el("div", { class: "ap-row", role: "listitem", "data-id": p.id });
      const statusBadge = el("span", {
        class: statusClass(qItem) || "ap-status",
        text: statusLabel(qItem),
        hidden: !qItem
      });
      const btn = el("button", { class: "ap-row-btn", type: "button", "aria-expanded": "false" }, [
        el("span", { class: "ap-rank", text: String(p.rank) }),
        el("span", { class: "ap-co", text: p.company }),
        el("span", { class: "ap-title", text: p.title }),
        el("span", { class: "ap-loc", text: p.location }),
        el("span", { class: "ap-posted", text: p.posted || "—" }),
        el("span", { class: "ap-age", text: (p.age_days == null ? "—" : p.age_days + "d") }),
        el("span", { class: "ap-fit", text: p.fit_oneliner || "" }),
      ]);
      const approveBtn = el("button", {
        type: "button",
        class: "ap-approve",
        text: qItem && qItem.owner_approved ? "Approved" : "Approve",
        disabled: !!(qItem && qItem.owner_approved)
      });
      const statusEl = el("span", {
        class: statusClass(qItem) || "ap-status",
        text: statusLabel(qItem),
        hidden: !qItem
      });
      const detail = el("div", { class: "ap-detail" }, [
        el("div", {}, [
          el("h3", { text: "Job posting" }),
          p.url ? el("p", { class: "ap-ext" }, [el("a", { href: p.url, target: "_blank", rel: "noopener", text: "Open employer posting" })]) : null,
          el("div", { class: "ap-block", text: p.posting || "(no posting text)" }),
        ]),
        el("div", {}, [
          el("h3", { text: "Cover letter" }),
          el("div", { class: "ap-block", text: p.cover_letter || "(no cover letter)" }),
        ]),
        el("div", {}, [
          el("h3", { text: "Fit / gaps" }),
          el("div", { class: "ap-block", text: p.fit_gaps || "(none)" }),
        ]),
        el("div", { class: "ap-actions" }, [
          p.cv_pdf ? el("a", { href: withKey("/applications_pdf/" + encodeURIComponent(p.cv_pdf)), text: "Download CV (PDF)" }) : null,
          el("button", { type: "button", class: "secondary ap-cover", text: "Download cover letter" }),
          approveBtn,
          statusEl,
        ]),
        el("p", {
          class: "ap-approve-hint",
          text: "Approve = Owner yes. Mahadeva then applies via the employer careers form or email apply link in the pack. No LinkedIn Easy Apply. Nothing is sent from this tap."
        }),
      ]);
      const coverBtn = detail.querySelector("button.ap-cover");
      if (coverBtn) {
        coverBtn.addEventListener("click", function (ev) {
          ev.stopPropagation();
          downloadText((p.slug || p.id) + "-cover-letter.md", p.cover_letter || "");
        });
      }
      approveBtn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        if (approveBtn.disabled) return;
        approveBtn.disabled = true;
        approveBtn.textContent = "Saving…";
        fetch(withKey("/applications/approve"), {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pack_id: p.id })
        })
          .then(function (r) {
            if (!r.ok) throw new Error("approve failed");
            return r.json();
          })
          .then(function (payload) {
            const item = payload.item || null;
            if (item) queueById[p.id] = item;
            approveBtn.textContent = "Approved";
            approveBtn.disabled = true;
            setStatusEl(statusEl, item);
            setStatusEl(statusBadge, item);
            if (!statusBadge.parentNode) {
              btn.appendChild(statusBadge);
            }
          })
          .catch(function () {
            approveBtn.disabled = false;
            approveBtn.textContent = "Approve";
            statusEl.hidden = false;
            statusEl.className = "ap-status ap-status-fail";
            statusEl.textContent = "Could not record Approve — try again";
          });
      });
      if (qItem) {
        btn.appendChild(statusBadge);
      }
      btn.addEventListener("click", function () {
        const open = row.classList.toggle("open");
        btn.setAttribute("aria-expanded", open ? "true" : "false");
      });
      row.appendChild(btn);
      row.appendChild(detail);
      list.appendChild(row);
    });
    main.appendChild(list);
    main.appendChild(el("p", {
      class: "ap-foot",
      text: "Private review surface. Not linked from the public nav. PDFs include contact details — keep the URL to yourself. Apply queue is separate; this page never submits to employers."
    }));
  }

  if (!key) {
    // Server should already 404; keep client quiet with no hint.
    main.textContent = "";
    return;
  }

  Promise.all([
    fetch(withKey("/applications.json"), { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error("not found");
      return r.json();
    }),
    fetch(withKey("/applications/queue"), { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) return { items: [] };
      return r.json();
    }).catch(function () { return { items: [] }; })
  ])
    .then(function (pair) {
      const data = pair[0];
      const queue = pair[1] || {};
      (queue.items || []).forEach(function (item) {
        if (item && item.pack_id) queueById[item.pack_id] = item;
      });
      render(data);
    })
    .catch(function () {
      main.textContent = "";
      main.appendChild(el("p", { class: "ap-hint", text: "Not found." }));
    });
})();
