/* ==========================================================================
   Shared header + footer.
   Edit NAV below to add/rename pages — every page picks up the change.
   Paths are relative to the site root.
   ========================================================================== */

const CONFERENCES = [
  ["big-sky", "Big Sky"],
  ["caa", "Coastal Athletic"],
  ["ivy", "Ivy"],
  ["meac", "MEAC"],
  ["mvfc", "MVFC"],
  ["nec", "NEC"],
  ["ovc", "OVC"],
  ["patriot", "Patriot"],
  ["pioneer", "Pioneer"],
  ["southern", "Southern"],
  ["southland", "Southland"],
  ["swac", "SWAC"],
  ["uac", "UAC"],
  ["independents", "FCS Independents"],
];

const NAV = [
  {
    label: "Ratings",
    items: [
      ["Power Ratings", "ratings/power.html"],
      ["Resume Rating", "ratings/resume.html"],
      ["Biggest Improvers", "ratings/improvers.html"],
    ],
  },
  {
    label: "Predictions",
    items: [
      ["Weekly Picks", "predictions/weekly.html"],
      ["Season Projections", "predictions/projections.html"],
    ],
  },
  {
    label: "Conference Races",
    wide: true,
    items: CONFERENCES.map(([id, name]) => [name, `conferences/?c=${id}`]),
  },
  { label: "Box Scores", href: "box-scores.html" },
  { label: "About SFCS", href: "about.html" },
];

(function () {
  const root = new URL("..", document.currentScript.src);
  const url = (p) => new URL(p, root).href;

  const normalize = (u) => {
    const x = new URL(u, location.href);
    return x.pathname.replace(/index\.html$/, "") + x.search;
  };
  const here = normalize(location.href);
  const isHere = (p) => normalize(url(p)) === here;

  let uid = 0;
  const navHtml = NAV.map((entry) => {
    if (entry.href) {
      const cur = isHere(entry.href) ? ' aria-current="page"' : "";
      return `<li class="nav-item"><a class="nav-link" href="${url(entry.href)}"${cur}>${entry.label}</a></li>`;
    }
    const id = `dd-${uid++}`;
    let anyCurrent = false;
    const links = entry.items
      .map(([label, href]) => {
        const cur = isHere(href);
        anyCurrent ||= cur;
        return `<li><a href="${url(href)}"${cur ? ' aria-current="page"' : ""}>${label}</a></li>`;
      })
      .join("");
    return `<li class="nav-item has-dropdown${anyCurrent ? " is-current" : ""}">
        <button class="nav-link" type="button" aria-expanded="false" aria-controls="${id}">
          ${entry.label}<span class="caret" aria-hidden="true"></span>
        </button>
        <ul class="dropdown${entry.wide ? " is-wide" : ""}" id="${id}">${links}</ul>
      </li>`;
  }).join("");

  const header = document.createElement("header");
  header.className = "site-header";
  header.innerHTML = `
    <div class="wrap header-inner">
      <a class="brand" href="${url("index.html")}" aria-label="SFCS home">
        <img src="${url("assets/brand/lockup-on-dark.png")}" alt="SFCS — FCS Football Analytics" width="190" height="44">
      </a>
      <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
      <nav class="site-nav" id="site-nav" aria-label="Main">
        <ul class="nav-list">${navHtml}</ul>
      </nav>
    </div>`;
  document.body.prepend(header);

  const footer = document.createElement("footer");
  footer.className = "site-footer";
  footer.innerHTML = `
    <div class="wrap footer-inner">
      <img src="${url("assets/brand/mark-on-dark.png")}" alt="SFCS" width="35" height="32">
      <span>© ${new Date().getFullYear()} SFCS · FCS Football Analytics</span>
    </div>`;
  document.body.append(footer);

  // ---- Behavior ----
  const closeAll = (except) => {
    header.querySelectorAll(".has-dropdown.is-open").forEach((li) => {
      if (li === except) return;
      li.classList.remove("is-open");
      li.querySelector("button").setAttribute("aria-expanded", "false");
    });
  };

  header.querySelectorAll(".has-dropdown > button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const li = btn.parentElement;
      const open = !li.classList.contains("is-open");
      closeAll(li);
      li.classList.toggle("is-open", open);
      btn.setAttribute("aria-expanded", String(open));
    });
  });

  const toggle = header.querySelector(".nav-toggle");
  const nav = header.querySelector(".site-nav");
  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(open));
    toggle.textContent = open ? "Close" : "Menu";
  });

  document.addEventListener("click", (e) => {
    if (!header.contains(e.target)) closeAll();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAll();
  });

  // Expose for the conference template page.
  window.SFCS = { CONFERENCES };
})();
