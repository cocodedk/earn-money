// State owner + SSE reducer for the Probe Live Tab.
// Only writer to `window.probeState`. Both renderers (probe-render.js,
// probe-detail.js) are strictly read-only over `window.probeState`.
// probe.js wires the EventSource → probeReducer and registers a single
// `onChange` callback that triggers a render of both panels.

(function () {
  const _onChangeCallbacks = [];

  function _emptyState() {
    return {
      turns: {},
      maxTurn: 0,         // tracked during action_pending; avoids O(N) scans
      selectedTurn: null,
      followLatest: true,
      activeTab: "delta",
      runError: null,
    };
  }

  window.probeState = _emptyState();

  function _notify() {
    for (const cb of _onChangeCallbacks) cb();
  }

  function _ensureTurn(turn, e) {
    let t = window.probeState.turns[turn];
    if (!t) {
      t = {
        system: e.system || "",
        prompt: e.prompt || "",
        attempts: [],
        policyDecision: null,
        observation: null,
        complete: false,
      };
      window.probeState.turns[turn] = t;
    }
    return t;
  }

  function _onActionPending(e) {
    const t = _ensureTurn(e.turn, e);
    if (e.system && !t.system) t.system = e.system;
    if (e.prompt && !t.prompt) t.prompt = e.prompt;
    t.attempts.push({
      attempt: e.attempt,
      raw: e.raw || "",
      model: e.model || "",
      used_response_format: e.used_response_format,
      ts: Date.now(),
      parseOutcome: "pending",
      parseError: null,
    });
    if (e.turn > window.probeState.maxTurn) window.probeState.maxTurn = e.turn;
    if (window.probeState.followLatest) {
      window.probeState.selectedTurn = e.turn;
    }
  }

  function _findAttempt(turn, attempt) {
    const t = window.probeState.turns[turn];
    if (!t) return null;
    return t.attempts.find((a) => a.attempt === attempt) || null;
  }

  function _onActionParsed(e) {
    const a = _findAttempt(e.turn, e.attempt);
    if (a) a.parseOutcome = "ok";
  }

  function _onActionParseFailed(e) {
    const a = _findAttempt(e.turn, e.attempt);
    if (a) {
      a.parseOutcome = "failed";
      a.parseError = e.error || "";
    }
  }

  function _onPolicy(e) {
    const t = window.probeState.turns[e.turn];
    if (t) t.policyDecision = e.policy;
  }

  function _onObservation(e) {
    const t = window.probeState.turns[e.turn];
    if (t) t.observation = e.obs;
  }

  function _onComplete(e) {
    const t = window.probeState.turns[e.turn];
    if (t) t.complete = true;
  }

  function _onProbeError(e) {
    window.probeState.runError = e.message || "";
  }

  function _onProbeStart() {
    window.probeState = _emptyState();
  }

  const _HANDLERS = {
    "action_pending":     _onActionPending,
    "action_parsed":      _onActionParsed,
    "action_parse_failed": _onActionParseFailed,
    "policy":             _onPolicy,
    "observation":        _onObservation,
    "complete":           _onComplete,
    "probe_error":        _onProbeError,
    "probe_start":        _onProbeStart,
  };

  window.probeReducer = function probeReducer(event) {
    const handler = _HANDLERS[event && event.stage];
    if (!handler) return;
    handler(event);
    _notify();
  };

  window.setSelectedTurn = function setSelectedTurn(n) {
    window.probeState.selectedTurn = n;
    window.probeState.followLatest = false;
    _notify();
  };

  window.setActiveTab = function setActiveTab(tab) {
    window.probeState.activeTab = tab;
    _notify();
  };

  window.setFollowLatest = function setFollowLatest(on) {
    window.probeState.followLatest = !!on;
    if (on && window.probeState.maxTurn > 0) {
      window.probeState.selectedTurn = window.probeState.maxTurn;
    }
    _notify();
  };

  window.onChange = function onChange(fn) {
    _onChangeCallbacks.push(fn);
  };
})();
