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

  function chosenFromHash() {
    const m = /^#tab=(\w+)$/.exec(location.hash || "");
    return m ? m[1] : "recon";
  }

  tabs.forEach(t => t.addEventListener("click", () => {
    const name = t.dataset.tab;
    location.hash = "tab=" + name;
    show(name);
  }));

  window.addEventListener("hashchange", () => show(chosenFromHash()));
  show(chosenFromHash());
})();
