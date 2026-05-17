(function () {
  const tabs = document.querySelectorAll(".tabs .tab");
  const panels = document.querySelectorAll("[id^='tab-']");

  function show(name) {
    panels.forEach(p => p.hidden = (p.id !== "tab-" + name));
    tabs.forEach(t => {
      const on = t.dataset.tab === name;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  // The hash is a `&`-joined param list (e.g. `#tab=probe&run=<id>`) so
  // each piece is matched independently; a strict ^…$ exact-match would
  // drop tab selection the moment any other param showed up.
  function chosenFromHash() {
    const m = /(?:^#|&)tab=(\w+)/.exec(location.hash || "");
    return m ? m[1] : "recon";
  }

  function _writeTabPreservingOthers(name) {
    const hash = (location.hash || "").replace(/^#/, "");
    const others = hash.split("&").filter(p => p && !p.startsWith("tab="));
    location.hash = ["tab=" + name, ...others].join("&");
  }

  tabs.forEach(t => t.addEventListener("click", () => {
    const name = t.dataset.tab;
    _writeTabPreservingOthers(name);
    show(name);
  }));

  window.addEventListener("hashchange", () => show(chosenFromHash()));
  show(chosenFromHash());
})();
