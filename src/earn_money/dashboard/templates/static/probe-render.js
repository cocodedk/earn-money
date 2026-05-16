(function () {
  function $card(timeline, turn) {
    let card = timeline.querySelector(`[data-turn="${turn}"]`);
    if (card) return card;
    card = document.createElement("article");
    card.className = "turn-card";
    card.dataset.turn = String(turn);
    card.append(
      buildHeader(turn),
      buildSlot("action"),
      buildSlot("policy"),
      buildSlot("obs"),
      buildSlot("findings"),
    );
    timeline.append(card);
    return card;
  }

  function buildSlot(name) {
    const el = document.createElement("div");
    el.className = "slot slot-" + name;
    return el;
  }

  function buildHeader(turn) {
    const h = document.createElement("header");
    const num = document.createElement("span");
    num.className = "turn-num";
    num.textContent = "TURN " + turn;
    const model = document.createElement("span");
    model.className = "model-id";
    const tokens = document.createElement("span");
    tokens.className = "tokens";
    h.append(num, model, tokens);
    return h;
  }

  function appendOrUpdateTurnCard(timeline, data) {
    const card = $card(timeline, data.turn);
    const header = card.querySelector("header");
    if (data.stage === "action_pending") {
      header.querySelector(".model-id").textContent = data.model || "?";
      header.querySelector(".tokens").textContent = "~" + (data.estimated_tokens || 0) + "t";
      card.querySelector(".slot-action").textContent = data.raw_excerpt || "";
    } else if (data.stage === "action_parsed") {
      const slot = card.querySelector(".slot-action");
      slot.textContent = JSON.stringify(data.action);
      if (data.parse_recovered) slot.dataset.recovered = "true";
    } else if (data.stage === "policy") {
      const slot = card.querySelector(".slot-policy");
      slot.textContent = (data.policy.allowed ? "✓ " : "✗ ") + data.policy.reason;
      slot.className = "slot slot-policy " + (data.policy.allowed ? "policy-ok" : "policy-deny");
    } else if (data.stage === "observation") {
      const slot = card.querySelector(".slot-obs");
      slot.textContent = `${data.obs.status} ${data.obs.content_type}  ${data.obs.url}\n${data.obs.body_excerpt}`;
    } else if (data.stage === "complete") {
      card.classList.add("complete", "outcome-" + data.outcome);
    }
  }

  function appendFinding(timeline, data) {
    const card = $card(timeline, data.turn);
    const row = document.createElement("div");
    row.className = "finding-row finding-" + data.kind;
    row.textContent = `[${data.kind}:${data.type}] ${data.path || data.target || "?"}`;
    card.querySelector(".slot-findings").append(row);
  }

  function markComplete(timeline, data) {
    const banner = document.createElement("div");
    banner.className = "timeline-banner";
    banner.textContent = `done · ${data.turns} turns · stop=${data.stop_reason} · candidates=${data.candidates_count} verified=${data.verified_count}`;
    timeline.append(banner);
  }

  function showError(timeline, data) {
    const banner = document.createElement("div");
    banner.className = "timeline-banner error";
    banner.textContent = "error · " + (data.message || "unknown");
    timeline.append(banner);
  }

  window.ProbeRender = { appendOrUpdateTurnCard, appendFinding, markComplete, showError };
})();
