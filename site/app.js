// Calibre Zen Margin's website: fills the download button and the version list from GitHub Releases,
// and opens screenshots in a lightbox. Everything else on the page is static HTML.
(() => {
  "use strict";

  const REPO = "Star69995/calibre-zen";
  const RELEASES_PAGE = `https://github.com/${REPO}/releases`;
  const API = `https://api.github.com/repos/${REPO}/releases?per_page=100`;
  const CACHE_KEY = "margin-releases-v1";
  const CACHE_MS = 10 * 60 * 1000;
  const SHOWN_AT_FIRST = 4;

  // UI strings by page language (<html lang>): English is the default page, /he/ is Hebrew.
  const STRINGS = {
    en: {
      locale: "en-US",
      soon: "The first version is coming soon",
      heroMeta: (v, os, size) => `Version ${v} · ${os} · ${size}`,
      otherSystems: "Other systems and formats",
      latest: "Latest",
      download: "Download",
      releasePage: "Release page",
      whatsNew: "What's new in this version",
      published: (d) => `Published ${d}`,
      none: "No version has been published yet. It will show up here as soon as it's out.",
      follow: "Follow the project on GitHub",
      showMore: (n) => `Show ${n} older versions`,
      allOnGithub: "All versions on GitHub",
      error: "Couldn't load the version list right now. Try again in a moment, or download straight from GitHub:",
      latestOnGithub: "Latest version on GitHub",
      sha: "SHA-256",
      copy: "Copy",
      copied: "Copied",
      platforms: { windows: "Windows", macos: "macOS", linux: "Linux", source: "Source" },
      kinds: {
        msi: "Installer (.msi)",
        portable: "Portable (.exe)",
        zip: "Zip",
        msix: "MSIX package",
        dmg: "Disk image (.dmg), Intel and Apple silicon",
        txz: (arch) => `Archive (.txz), ${arch}`,
        flatpak: (arch) => `Flatpak, ${arch}`,
        script: "Install script",
        src: "Source code (.tar.xz)",
      },
    },
    he: {
      locale: "he-IL",
      soon: "הגרסה הראשונה תפורסם בקרוב",
      heroMeta: (v, os, size) => `גרסה ${v} · ${os} · ${size}`,
      otherSystems: "מערכות ופורמטים אחרים",
      latest: "האחרונה",
      download: "הורדה",
      releasePage: "לדף הגרסה",
      whatsNew: "מה חדש בגרסה הזו",
      published: (d) => `פורסמה ב-${d}`,
      none: "עדיין לא פורסמה גרסה להורדה. היא תופיע כאן ברגע שתעלה.",
      follow: "מעקב אחרי הפרויקט ב-GitHub",
      showMore: (n) => `הצגת ${n} גרסאות קודמות`,
      allOnGithub: "כל הגרסאות ב-GitHub",
      error: "לא הצלחנו לטעון את רשימת הגרסאות כרגע. אפשר לנסות שוב בעוד רגע, או להוריד ישירות מ-GitHub:",
      latestOnGithub: "לגרסה האחרונה ב-GitHub",
      sha: "SHA-256",
      copy: "העתקה",
      copied: "הועתק",
      platforms: { windows: "Windows", macos: "macOS", linux: "Linux", source: "קוד מקור" },
      kinds: {
        msi: "קובץ התקנה (‎.msi)",
        portable: "גרסה ניידת (‎.exe)",
        zip: "קובץ Zip",
        msix: "חבילת MSIX",
        dmg: "קובץ ‎.dmg, למעבדי Intel ו-Apple",
        txz: (arch) => `ארכיון ‎.txz, ‏${arch}`,
        flatpak: (arch) => `Flatpak, ‏${arch}`,
        script: "סקריפט התקנה",
        src: "קוד מקור (‎.tar.xz)",
      },
    },
  };
  const T = STRINGS[document.documentElement.lang] || STRINGS.en;

  const $ = (sel, root = document) => root.querySelector(sel);

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  const icon = (name) => `<svg class="ic" aria-hidden="true"><use href="#i-${name}"/></svg>`;

  const formatSize = (bytes) => {
    if (!bytes) return "";
    const mb = bytes / (1024 * 1024);
    return mb >= 1 ? `${Math.round(mb)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  };

  const formatDate = (iso) => {
    try {
      return new Date(iso).toLocaleDateString(T.locale, { day: "numeric", month: "long", year: "numeric" });
    } catch {
      return "";
    }
  };

  const versionOf = (rel) => String(rel.tag_name || "").replace(/^v/i, "");

  // What each release file is, by its name (packaging/<os>/package.*). The order here is the order shown.
  const KINDS = [
    { re: /-windows-x64\.msi$/i, os: "windows", kind: () => T.kinds.msi, primary: true },
    { re: /-portable-installer-[\d.]+\.exe$/i, os: "windows", kind: () => T.kinds.portable },
    { re: /-windows-x64\.zip$/i, os: "windows", kind: () => T.kinds.zip },
    { re: /-macos\.dmg$/i, os: "macos", kind: () => T.kinds.dmg, primary: true },
    { re: /-linux-x86_64\.txz$/i, os: "linux", kind: () => T.kinds.txz("x86_64"), primary: true },
    { re: /-linux-arm64\.txz$/i, os: "linux", kind: () => T.kinds.txz("arm64") },
    { re: /-linux-x86_64\.flatpak$/i, os: "linux", kind: () => T.kinds.flatpak("x86_64") },
    { re: /-linux-arm64\.flatpak$/i, os: "linux", kind: () => T.kinds.flatpak("arm64") },
    { re: /^install-zen\.sh$/i, os: "linux", kind: () => T.kinds.script },
    { re: /^calibre-zen-margin-[\d.]+\.tar\.xz$/i, os: "source", kind: () => T.kinds.src },
  ];

  const classify = (rel) =>
    KINDS.flatMap((k) =>
      (rel.assets || []).filter((a) => k.re.test(a.name)).map((a) => ({ ...a, os: k.os, kind: k.kind(), primary: !!k.primary }))
    );

  const visitorOS = () => {
    const ua = navigator.userAgent || "";
    const plat = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
    if (/win/i.test(plat) || /Windows/.test(ua)) return "windows";
    if (/mac/i.test(plat) || /Mac OS X/.test(ua)) return /iPhone|iPad/.test(ua) ? null : "macos";
    if (/linux/i.test(plat) && !/Android/.test(ua)) return "linux";
    return null;
  };

  // --- Data ----------------------------------------------------------------

  const readCache = () => {
    try {
      const c = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null");
      return c && Date.now() - c.t < CACHE_MS ? c.data : null;
    } catch {
      return null;
    }
  };

  const writeCache = (data) => {
    try {
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({ t: Date.now(), data }));
    } catch {
      /* storage unavailable - fine, just no cache */
    }
  };

  async function loadReleases() {
    const cached = readCache();
    if (cached) return cached;
    // The html+json media type adds `body_html`: the release notes, rendered and sanitized by GitHub.
    const res = await fetch(API, { headers: { Accept: "application/vnd.github.html+json" } });
    if (!res.ok) throw new Error(`GitHub API ${res.status}`);
    const data = (await res.json())
      // Only this fork's own releases, v<version>: the repository also holds mirrored calibre
      // installers (upstream-<version>) and update tests (update-test-...), both pre-releases.
      .filter((r) => !r.draft && !r.prerelease && /^v\d/.test(r.tag_name))
      .map((r) => ({
        tag_name: r.tag_name,
        name: r.name,
        html_url: r.html_url,
        published_at: r.published_at,
        body_html: r.body_html || "",
        assets: (r.assets || []).map((a) => ({
          name: a.name,
          size: a.size,
          browser_download_url: a.browser_download_url,
          digest: a.digest || null,
        })),
      }));
    writeCache(data);
    return data;
  }

  // --- Rendering -------------------------------------------------------------

  function renderHero(latest) {
    const meta = $("#hero-meta");
    if (!latest) {
      meta.textContent = T.soon;
      document.querySelectorAll("[data-latest-link]").forEach((a) => (a.href = "#download"));
      return;
    }
    const files = classify(latest);
    const os = visitorOS();
    const pick = files.find((f) => f.primary && f.os === os);
    if (!pick) {
      document.querySelectorAll("[data-latest-link]").forEach((a) => (a.href = "#download"));
      meta.innerHTML = `<bdi dir="ltr">${esc(versionOf(latest))}</bdi>`;
      return;
    }
    document.querySelectorAll("[data-latest-link]").forEach((a) => (a.href = pick.browser_download_url));
    meta.innerHTML =
      T.heroMeta(`<bdi dir="ltr">${esc(versionOf(latest))}</bdi>`, esc(T.platforms[os]), `<bdi dir="ltr">${esc(formatSize(pick.size))}</bdi>`) +
      ` · <a href="#download">${esc(T.otherSystems)}</a>`;
  }

  function fileRow(f) {
    const sha = /^sha256:/i.test(f.digest || "") ? f.digest.slice(7) : "";
    return `<li class="file">
      <a class="file-link" href="${esc(f.browser_download_url)}">${icon("download")}<span>${esc(f.kind)}</span></a>
      <small><bdi dir="ltr">${esc(formatSize(f.size))}</bdi></small>
      ${
        sha
          ? `<details class="sha"><summary>${esc(T.sha)}</summary><div class="hash-row"><code dir="ltr">${esc(sha)}</code><button type="button" class="copy-btn" data-copy="${esc(sha)}">${esc(T.copy)}</button></div></details>`
          : ""
      }
    </li>`;
  }

  function releaseCard(rel, isLatest) {
    const files = classify(rel);
    const groups = ["windows", "macos", "linux", "source"]
      .map((os) => [os, files.filter((f) => f.os === os)])
      .filter(([, list]) => list.length);
    const body = groups.length
      ? `<div class="platforms">${groups
          .map(
            ([os, list]) => `<section class="platform">
              <h4>${icon(os)}${esc(T.platforms[os])}</h4>
              <ul>${list.map(fileRow).join("")}</ul>
            </section>`
          )
          .join("")}</div>`
      : `<p><a class="btn btn-secondary btn-md" href="${esc(rel.html_url)}">${icon("external")}<span>${esc(T.releasePage)}</span></a></p>`;

    const notes = rel.body_html.trim()
      ? `<details class="disclosure"${isLatest ? " open" : ""}>
           <summary>${icon("chevron").replace('class="ic"', 'class="ic chev"')}${esc(T.whatsNew)}</summary>
           <div class="disclosure-body notes" dir="auto">${rel.body_html}</div>
         </details>`
      : "";

    return `<article class="release${isLatest ? " is-latest" : ""}">
      <div class="release-head">
        <h3><bdi dir="ltr">${esc(versionOf(rel))}</bdi>${isLatest ? `<span class="badge">${esc(T.latest)}</span>` : ""}</h3>
        <div class="when">${esc(T.published(formatDate(rel.published_at)))}</div>
      </div>
      ${notes}
      ${isLatest ? body : `<details class="disclosure"><summary>${icon("chevron").replace('class="ic"', 'class="ic chev"')}${esc(T.download)}</summary><div class="disclosure-body">${body}</div></details>`}
    </article>`;
  }

  function renderList(releases, latest) {
    const box = $("#releases");
    if (!releases.length) {
      box.innerHTML = `<div class="notice">
        <p>${esc(T.none)}</p>
        <a href="${RELEASES_PAGE}">${icon("github")} ${esc(T.follow)}</a>
      </div>`;
      return;
    }
    const cards = releases.map((r) => releaseCard(r, r === latest));
    const rest = cards.length - SHOWN_AT_FIRST;
    box.innerHTML =
      cards.slice(0, SHOWN_AT_FIRST).join("") +
      (rest > 0
        ? `<div class="more-hidden" hidden>${cards.slice(SHOWN_AT_FIRST).join("")}</div>
           <div class="more-wrap"><button type="button" class="btn btn-secondary btn-md" id="show-more">${esc(T.showMore(rest))}</button></div>`
        : "") +
      `<p class="more-wrap"><a href="${RELEASES_PAGE}">${icon("external")} ${esc(T.allOnGithub)}</a></p>`;

    const more = $("#show-more");
    if (more) {
      more.addEventListener("click", () => {
        const hidden = $(".more-hidden", box);
        hidden.hidden = false;
        hidden.style.display = "contents";
        more.parentElement.remove();
      });
    }
  }

  function renderError() {
    $("#hero-meta").textContent = "";
    document.querySelectorAll("[data-latest-link]").forEach((a) => (a.href = `${RELEASES_PAGE}/latest`));
    $("#releases").innerHTML = `<div class="notice">
      <p>${esc(T.error)}</p>
      <a class="btn btn-primary btn-md" href="${RELEASES_PAGE}/latest">${icon("download")}<span>${esc(T.latestOnGithub)}</span></a>
    </div>`;
  }

  loadReleases()
    .then((releases) => {
      const latest = releases[0] || null;
      renderHero(latest);
      renderList(releases, latest);
    })
    .catch(renderError);

  // Copy a SHA-256 to the clipboard.
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    try {
      await navigator.clipboard.writeText(btn.dataset.copy);
      btn.textContent = T.copied;
      setTimeout(() => (btn.textContent = T.copy), 1600);
    } catch {
      /* clipboard blocked - the hash text is still selectable */
    }
  });

  // --- Theme switch for the screenshots ---------------------------------------
  // Light and dark shots exist for every view; the page shows the ones matching
  // the visitor's theme, and the toggle swaps them by hand.
  const shotsFor = (mode) =>
    document.querySelectorAll("img[data-shot]").forEach((img) => {
      img.src = img.dataset.shot.replace("{mode}", mode);
      const btn = img.closest(".shot-btn");
      if (btn) btn.dataset.full = img.src;
    });
  const dark = window.matchMedia && matchMedia("(prefers-color-scheme: dark)");
  let mode = dark && dark.matches ? "dark" : "light";
  shotsFor(mode);
  document.querySelectorAll("[data-shot-mode]").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.shotMode === mode));
    b.addEventListener("click", () => {
      mode = b.dataset.shotMode;
      shotsFor(mode);
      document.querySelectorAll("[data-shot-mode]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    });
  });

  // --- Lightbox --------------------------------------------------------------

  const box = $("#lightbox");
  if (box && typeof box.showModal === "function") {
    const img = $("img", box);
    const caption = $(".lightbox-caption", box);
    document.querySelectorAll(".shot-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const thumb = $("img", btn);
        img.src = btn.dataset.full || thumb.src;
        img.alt = thumb.alt;
        caption.textContent = $("figcaption strong", btn.closest("figure"))?.textContent || "";
        box.showModal();
      });
    });
    $(".lightbox-close", box).addEventListener("click", () => box.close());
    box.addEventListener("click", (e) => {
      if (e.target === box) box.close();
    });
  }
})();
