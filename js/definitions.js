/* ==========================================================================
   Definitions page. Content lives in data/definitions.json:
   terms -> { term, definition, thresholds }, shown alphabetically.
   ========================================================================== */

(function () {
  const D = window.SFCSData;
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  function term(t) {
    const def = t.definition?.trim();
    const thr = t.thresholds?.trim();
    return `<div class="def-item">
        <dt>${esc(t.term)}</dt>
        <dd>
          ${def ? `<p>${esc(def)}</p>` : `<p class="def-empty">Coming soon.</p>`}
          ${thr ? `<p class="def-thresholds"><span>Thresholds</span>${esc(thr)}</p>` : ""}
        </dd>
      </div>`;
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const el = document.getElementById("definitions");
    try {
      const res = await fetch(D.url("data/definitions.json"), { cache: "no-cache" });
      const terms = (await res.json()).terms
        .filter((t) => t.term?.trim())
        .sort((a, b) => a.term.localeCompare(b.term, "en", { sensitivity: "base" }));
      el.innerHTML = `<dl class="def-list">${terms.map(term).join("")}</dl>`;
    } catch (err) {
      console.error(err);
      el.innerHTML = `<div class="placeholder"><strong>Coming soon</strong>Definitions will appear here.</div>`;
    }
  });
})();
