// ============================================================================
// Constants / State
// ============================================================================

const WORKSPACE_KEY = "opc_browse_workspace_v1";
const TAG_FILTERS = [
  "all_numeric",
  "useful_only",
  "changing_numeric",
  "counter_like",
  "state_like",
  "constants",
  "stale",
  "low_sample",
  "ignore",
];
const RELATIONSHIP_FILTERS = [
  "all",
  "moves_together",
  "possible_driver",
  "possible_effect",
  "changes_together",
];
const PANEL_WIDTH_OPTIONS = [4, 6, 8, 12];
const PANEL_HEIGHT_OPTIONS = [3, 4, 6, 8];

const state = {
  machines: [],
  selectedMachineId: null,
  tags: [],
  filteredTags: [],
  folderCollapsed: {},
  activeTagFilter: "all_numeric",
  useScoredProfiles: false,
  tagSort: "score_desc",
  targetTag: null,
  lastAnalysisResponse: null,
  analysisResults: [],
  selectedResultTagIds: new Set(),
  activeRelationshipFilter: "all",
  resultSort: "score_desc",
  chart: null,
  lastTimeseriesRequest: null,
  lastTimeseriesResponse: null,
  dashboards: [],
  currentDashboard: null,
  currentTab: "explore",
  panelCharts: {},
  builderPreviewChart: null,
  builderEditingPanelId: null,
  builderTags: [],
  builderSelectedTagIds: new Set(),
  dashboardDirty: false,
  loading: {
    machines: false,
    tags: false,
    builderTags: false,
    analysis: false,
    chart: false,
    dashboards: false,
    refreshAll: false,
  },
};

// ============================================================================
// DOM Helpers
// ============================================================================

function qs(selector, root = document) {
  return root.querySelector(selector);
}

function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

function setText(idOrElement, value) {
  const element = typeof idOrElement === "string" ? document.getElementById(idOrElement) : idOrElement;
  if (element) {
    element.textContent = value ?? "";
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatUtc(value) {
  return value || "-";
}

function createEmptyState(title, message) {
  return `
    <div class="empty-state">
      <strong>${escapeHtml(title)}</strong>
      <div>${escapeHtml(message)}</div>
    </div>
  `;
}

function createBadge(label, type = "") {
  return `<span class="badge ${type}">${escapeHtml(label)}</span>`;
}

function getCurrentWorkflowState() {
  return {
    machine: Boolean(state.selectedMachineId),
    target: Boolean(state.targetTag),
    analysis: Array.isArray(state.analysisResults) && state.analysisResults.length > 0,
    plot: Boolean(state.lastTimeseriesResponse?.series?.length),
    save: Boolean((state.currentDashboard?.panels || []).length),
  };
}

function updateWorkflowSteps() {
  const workflowState = getCurrentWorkflowState();
  const activeStep = !workflowState.machine
    ? "machine"
    : !workflowState.target
      ? "target"
      : !workflowState.analysis
        ? "analysis"
        : !workflowState.plot
          ? "plot"
          : "save";

  qsa("[data-workflow-step]").forEach((element) => {
    const stepName = element.getAttribute("data-workflow-step");
    element.classList.remove("incomplete", "active", "complete");
    if (workflowState[stepName]) {
      element.classList.add("complete");
    } else if (stepName === activeStep) {
      element.classList.add("active");
    } else {
      element.classList.add("incomplete");
    }
  });
}

function generatePanelId() {
  return `panel_${Math.random().toString(36).slice(2, 10)}`;
}

function tagDisplayLabel(tag) {
  return tag?.display_name || tag?.browse_name || tag?.opc_path || `Tag ${tag?.tag_id ?? ""}`.trim();
}

// ============================================================================
// Workspace Persistence
// ============================================================================

function persistWorkspace() {
  const payload = {
    machine_id: state.selectedMachineId,
    search_text: document.getElementById("tag-search").value,
    numeric_only: document.getElementById("numeric-only").checked,
    use_scored_profiles: document.getElementById("use-scored-profiles").checked,
    target_tag: state.targetTag,
    start_utc: document.getElementById("start-utc").value,
    end_utc: document.getElementById("end-utc").value,
    bucket_seconds: document.getElementById("bucket-seconds").value,
    candidate_scope: document.getElementById("candidate-scope").value,
    max_candidate_tags: document.getElementById("max-candidate-tags").value,
    max_results: document.getElementById("max-results").value,
    min_pair_count: document.getElementById("min-pair-count").value,
    max_lag_seconds: document.getElementById("max-lag-seconds").value,
    selected_related_tag_ids: Array.from(state.selectedResultTagIds),
    relationship_filter: state.activeRelationshipFilter,
    result_sort: state.resultSort,
    chart_mode: document.getElementById("chart-mode").value,
    chart_aggregation: document.getElementById("chart-aggregation").value,
    active_tag_filter: state.activeTagFilter,
    tag_sort: state.tagSort,
  };
  localStorage.setItem(WORKSPACE_KEY, JSON.stringify(payload));
}

function loadWorkspace() {
  try {
    const raw = localStorage.getItem(WORKSPACE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function clearWorkspace() {
  localStorage.removeItem(WORKSPACE_KEY);
}

function setDefaultUtcRange() {
  const end = new Date();
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
  document.getElementById("start-utc").value = start.toISOString().replace(/\.\d{3}Z$/, "Z");
  document.getElementById("end-utc").value = end.toISOString().replace(/\.\d{3}Z$/, "Z");
}

function restoreWorkspaceControls(workspace) {
  if (!workspace) {
    setDefaultUtcRange();
    return;
  }
  document.getElementById("tag-search").value = workspace.search_text || "";
  document.getElementById("numeric-only").checked = workspace.numeric_only !== false;
  document.getElementById("use-scored-profiles").checked = workspace.use_scored_profiles === true;
  document.getElementById("start-utc").value = workspace.start_utc || "";
  document.getElementById("end-utc").value = workspace.end_utc || "";
  document.getElementById("bucket-seconds").value = workspace.bucket_seconds || 60;
  document.getElementById("candidate-scope").value = workspace.candidate_scope || "same_machine";
  document.getElementById("max-candidate-tags").value = workspace.max_candidate_tags || 300;
  document.getElementById("max-results").value = workspace.max_results || 25;
  document.getElementById("min-pair-count").value = workspace.min_pair_count || 30;
  document.getElementById("max-lag-seconds").value = workspace.max_lag_seconds || 1800;
  document.getElementById("chart-mode").value = workspace.chart_mode || "raw";
  document.getElementById("chart-aggregation").value = workspace.chart_aggregation || "avg";
  state.activeTagFilter = TAG_FILTERS.includes(workspace.active_tag_filter)
    ? workspace.active_tag_filter
    : "all_numeric";
  state.useScoredProfiles = workspace.use_scored_profiles === true;
  state.tagSort = workspace.tag_sort || "score_desc";
  state.activeRelationshipFilter = RELATIONSHIP_FILTERS.includes(workspace.relationship_filter)
    ? workspace.relationship_filter
    : "all";
  state.resultSort = workspace.result_sort || "score_desc";
  state.selectedMachineId = workspace.machine_id || null;
  state.targetTag = workspace.target_tag || null;
  state.selectedResultTagIds = new Set(workspace.selected_related_tag_ids || []);
  if (!document.getElementById("start-utc").value || !document.getElementById("end-utc").value) {
    setDefaultUtcRange();
  }
}

// ============================================================================
// API Helpers
// ============================================================================

async function apiGet(path) {
  const response = await fetch(path);
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `GET ${path} failed`);
  }
  return text ? JSON.parse(text) : null;
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `POST ${path} failed`);
  }
  return text ? JSON.parse(text) : null;
}

async function apiDelete(path) {
  const response = await fetch(path, { method: "DELETE" });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `DELETE ${path} failed`);
  }
  return text ? JSON.parse(text) : null;
}

// ============================================================================
// Toast / Alert / Loading Helpers
// ============================================================================

function showToast(message, type = "info", timeoutMs = 4000) {
  const container = document.getElementById("toast-container");
  if (!container) {
    return;
  }
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  window.setTimeout(() => {
    toast.remove();
  }, timeoutMs);
}

function clearError() {
  const box = document.getElementById("error-box");
  box.classList.add("hidden");
  setText("error-message", "");
  setText("error-details", "");
  document.getElementById("error-details").classList.add("hidden");
}

function showError(message, details = null) {
  const box = document.getElementById("error-box");
  const detailBox = document.getElementById("error-details");
  if (!message) {
    clearError();
    return;
  }
  setText("error-title", "Request Error");
  setText("error-message", message);
  if (details) {
    setText(detailBox, details);
    detailBox.classList.remove("hidden");
  } else {
    detailBox.classList.add("hidden");
    setText(detailBox, "");
  }
  box.classList.remove("hidden");
}

function setGlobalStatus(message, type = "info") {
  const element = document.getElementById("global-status");
  if (!element) {
    return;
  }
  element.className = `status-banner ${type}`;
  element.textContent = message;
}

function disableButton(id, isDisabled) {
  const element = document.getElementById(id);
  if (element) {
    element.disabled = isDisabled;
  }
}

function setSectionLoading(sectionName, isLoading, message = "") {
  const sectionConfig = {
    health: { loadingId: "health-status" },
    machines: { loadingId: "machine-loading", panelId: "machine-browser-panel" },
    tags: { loadingId: "tag-loading", panelId: "machine-browser-panel" },
    builderTags: { loadingId: "builder-tag-loading", panelId: null },
    analysis: { loadingId: "analysis-loading", panelId: "relationship-panel" },
    chart: { loadingId: "chart-loading", panelId: "chart-panel-card" },
    dashboards: { loadingId: "dashboard-loading", panelId: null },
    saveDashboard: { loadingId: "dashboard-loading", panelId: null },
    refreshAll: { loadingId: null, panelId: "dashboards-view" },
  };
  const config = sectionConfig[sectionName];
  if (!config) {
    return;
  }
  if (config.loadingId) {
    const element = document.getElementById(config.loadingId);
    if (element) {
      if (message) {
        element.textContent = message;
      }
      element.classList.toggle("hidden", !isLoading);
    }
  }
  if (config.panelId) {
    const panel = document.getElementById(config.panelId);
    if (panel) {
      panel.dataset.loading = isLoading ? "true" : "false";
    }
  }
  state.loading[sectionName] = isLoading;
}

async function withLoading(sectionName, asyncFn, message = "") {
  setSectionLoading(sectionName, true, message);
  try {
    return await asyncFn();
  } finally {
    setSectionLoading(sectionName, false);
  }
}

function setDashboardStatus(message) {
  setText("dashboard-status", message);
}

function markDashboardDirty(isDirty = true) {
  state.dashboardDirty = isDirty;
  document.getElementById("dashboard-dirty-indicator").classList.toggle("hidden", !isDirty);
}

window.addEventListener("beforeunload", (event) => {
  if (!state.dashboardDirty) {
    return;
  }
  event.preventDefault();
  event.returnValue = "";
});

function switchTab(tabName) {
  state.currentTab = tabName;
  document.getElementById("tab-explore").classList.toggle("active", tabName === "explore");
  document.getElementById("tab-dashboards").classList.toggle("active", tabName === "dashboards");
  document.getElementById("explore-view").classList.toggle("active", tabName === "explore");
  document.getElementById("dashboards-view").classList.toggle("active", tabName === "dashboards");
}

function parseUtc(value) {
  const date = value ? new Date(value) : null;
  return Number.isNaN(date?.getTime?.()) ? null : date;
}

function formatNumber(value, digits = 3) {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "number") {
    return value.toFixed(digits);
  }
  return String(value);
}

function formatTimestamp(value) {
  return formatUtc(value);
}

function isStaleTag(tag) {
  const lastSeen = parseUtc(tag.last_seen_utc);
  if (!lastSeen) {
    return true;
  }
  return Date.now() - lastSeen.getTime() > 24 * 60 * 60 * 1000;
}

function isLowSampleTag(tag) {
  return Number(tag.sample_count || 0) < 30;
}

function getTagUsefulness(tag) {
  return tag.usefulness_score || null;
}

const SKIP_REASON_LABELS = {
  target_insufficient_data: "Target has insufficient data",
  candidate_insufficient_overlap: "Candidate has insufficient overlap",
  constant_or_insufficient_variance: "Constant or not enough variation",
  insufficient_pair_count: "Not enough matching time buckets",
  non_numeric_or_missing_series: "Non-numeric or missing series",
  analysis_error: "Analysis error",
};

function readableSkipReason(reason) {
  return SKIP_REASON_LABELS[reason] || reason;
}

function getTargetPreflight(tag) {
  if (!tag) {
    return { blocked: false, weak: false, messages: [] };
  }
  const usefulness = getTagUsefulness(tag);
  const minPairCount = Number(document.getElementById("min-pair-count")?.value || 30);
  const messages = [];
  let blocked = false;
  let weak = false;

  if (Number(tag.numeric_sample_count || 0) === 0 && usefulness?.semantic_type === "text_or_state") {
    blocked = true;
    messages.push(
      "This selected target does not appear to have numeric data. Pick a numeric changing tag or disable scored profiles and inspect the tag."
    );
  }

  if (usefulness) {
    if (["constant", "sparse"].includes(usefulness.semantic_type) || usefulness.grade === "ignore") {
      weak = true;
    }
    if (usefulness.badges?.includes("stale")) {
      weak = true;
      messages.push("This target appears stale in the current dataset.");
    }
  }

  if (Number(tag.sample_count || 0) > 0 && Number(tag.sample_count || 0) < minPairCount) {
    weak = true;
  }
  if (Number(tag.numeric_sample_count || 0) > 0 && Number(tag.numeric_sample_count || 0) < minPairCount) {
    weak = true;
  }

  if (weak && !blocked) {
    messages.push("This target may not have enough changing numeric data. Analysis may return no results.");
  }

  return { blocked, weak, messages };
}

function isChangingTag(tag) {
  const usefulness = getTagUsefulness(tag);
  if (usefulness?.semantic_type === "continuous_numeric") {
    return true;
  }
  return Number(tag.distinct_numeric_count || 0) > 1 && usefulness?.semantic_type !== "constant";
}

async function loadHealth() {
  try {
    setGlobalStatus("Checking API health...", "info");
    const payload = await apiGet("/health");
    const indicator = document.getElementById("health-status");
    indicator.textContent = payload.status === "ok" ? "OK" : "Unknown";
    indicator.className = "status-pill ok";
    setGlobalStatus("API health check passed.", "success");
  } catch (error) {
    const indicator = document.getElementById("health-status");
    indicator.textContent = "Error";
    indicator.className = "status-pill error";
    setGlobalStatus("API health check failed.", "danger");
    showError(`Health check failed: ${error.message}`);
  }
}

async function loadMachines() {
  const select = document.getElementById("machine-select");
  const builderSelect = document.getElementById("builder-machine-select");
  await withLoading("machines", async () => {
    try {
      const machines = await apiGet("/api/machines");
      state.machines = machines;
      select.innerHTML = "";
      builderSelect.innerHTML = "";
      if (!machines.length) {
        select.innerHTML = '<option value="">No enabled machines found</option>';
        builderSelect.innerHTML = '<option value="">No enabled machines found</option>';
        setGlobalStatus("No enabled machines returned by the API.", "warning");
        return;
      }
      select.innerHTML = '<option value="">Select a machine</option>';
      builderSelect.innerHTML = '<option value="">Select a machine</option>';
      for (const machine of machines) {
        const option = document.createElement("option");
        option.value = String(machine.id);
        option.textContent = `${machine.machine_name} (${machine.id})`;
        if (state.selectedMachineId && Number(state.selectedMachineId) === machine.id) {
          option.selected = true;
        }
        select.appendChild(option);

        const builderOption = document.createElement("option");
        builderOption.value = String(machine.id);
        builderOption.textContent = `${machine.machine_name} (${machine.id})`;
        builderSelect.appendChild(builderOption);
      }
      if (!builderSelect.value && state.selectedMachineId) {
        builderSelect.value = String(state.selectedMachineId);
      }
      setGlobalStatus(`Loaded ${machines.length} machine(s).`, "success");
    } catch (error) {
      showError(`Failed to load machines: ${error.message}`);
      select.innerHTML = '<option value="">Failed to load machines</option>';
      builderSelect.innerHTML = '<option value="">Failed to load machines</option>';
      setGlobalStatus("Machine loading failed.", "danger");
    }
  }, "Loading...");
  updateActiveMachineLabel();
}

function updateActiveMachineLabel() {
  const label = document.getElementById("active-machine-label");
  if (!state.selectedMachineId) {
    label.textContent = "No machine selected";
    label.className = "status-pill pending";
    return;
  }
  const machine = state.machines.find((item) => Number(item.id) === Number(state.selectedMachineId));
  if (!machine) {
    label.textContent = `Machine ${state.selectedMachineId}`;
    label.className = "status-pill";
    return;
  }
  label.textContent = `${machine.machine_name} (${machine.id})`;
  label.className = "status-pill ok";
}

function updateChartPlaceholder() {
  const placeholder = document.getElementById("chart-empty-state");
  if (!placeholder || state.chart) {
    return;
  }
  if (!state.targetTag) {
    placeholder.textContent = "Click Plot to view the selected target tag.";
    return;
  }
  if (state.selectedResultTagIds.size > 0) {
    placeholder.textContent = "Click Plot to compare target with selected related tags.";
    return;
  }
  if (state.analysisResults.length > 0) {
    placeholder.textContent = "Click Plot to view the target tag alone, or select related tags to compare.";
    return;
  }
  placeholder.textContent = "Click Plot to view the selected target tag.";
}

function folderNameFromTag(tag) {
  if (!tag.opc_path || !tag.opc_path.includes("/")) {
    return tag.parent_branch || "root";
  }
  return tag.opc_path.split("/").slice(0, -1).join("/");
}

function flattenTagTree(node, parentName = "root") {
  let leaves = [];
  for (const tag of node.tags || []) {
    leaves.push({
      ...tag,
      group_name: parentName,
      folder_name: folderNameFromTag(tag),
    });
  }
  for (const child of node.children || []) {
    leaves = leaves.concat(flattenTagTree(child, child.path || child.name || parentName));
  }
  return leaves;
}

function getTagSearchValue() {
  return document.getElementById("tag-search").value.trim().toLowerCase();
}

function matchesTagQuickFilter(tag) {
  const usefulness = getTagUsefulness(tag);
  switch (state.activeTagFilter) {
    case "useful_only":
      return usefulness && ["high", "medium"].includes(usefulness.grade);
    case "changing_numeric":
      return isChangingTag(tag);
    case "counter_like":
      return usefulness?.semantic_type === "counter_like";
    case "state_like":
      return usefulness?.semantic_type === "state_like_numeric";
    case "constants":
      return usefulness?.semantic_type === "constant";
    case "stale":
      return isStaleTag(tag);
    case "low_sample":
      return isLowSampleTag(tag);
    case "ignore":
      return usefulness?.grade === "ignore";
    case "all_numeric":
    default:
      return true;
  }
}

function sortTags(tags) {
  const sorted = [...tags];
  sorted.sort((a, b) => {
    if (state.tagSort === "last_seen_desc") {
      return new Date(b.last_seen_utc || 0).getTime() - new Date(a.last_seen_utc || 0).getTime();
    }
    if (state.tagSort === "sample_count_desc") {
      return Number(b.sample_count || 0) - Number(a.sample_count || 0);
    }
    if (state.tagSort === "display_name_asc") {
      return (a.display_name || a.browse_name || a.opc_path || "").localeCompare(
        b.display_name || b.browse_name || b.opc_path || "",
      );
    }
    return (
      Number(b.usefulness_score?.score || 0) - Number(a.usefulness_score?.score || 0)
      || Number(b.sample_count || 0) - Number(a.sample_count || 0)
      || (a.display_name || a.browse_name || a.opc_path || "").localeCompare(
        b.display_name || b.browse_name || b.opc_path || "",
      )
    );
  });
  return sorted;
}

function filterTags() {
  const search = getTagSearchValue();
  state.filteredTags = state.tags.filter((tag) => {
    if (!matchesTagQuickFilter(tag)) {
      return false;
    }
    if (!search) {
      return true;
    }
    const haystack = [
      tag.display_name,
      tag.browse_name,
      tag.opc_path,
      tag.parent_branch,
      tag.data_type,
      tag.tag_id,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(search);
  });
}

function getGroupedTags() {
  filterTags();
  const grouped = {};
  for (const tag of state.filteredTags) {
    const folder = tag.folder_name || "root";
    if (!grouped[folder]) {
      grouped[folder] = [];
    }
    grouped[folder].push(tag);
  }
  return Object.entries(grouped).sort((a, b) => a[0].localeCompare(b[0]));
}

function renderTagList() {
  const container = document.getElementById("tag-list");
  container.innerHTML = "";
  if (!state.selectedMachineId) {
    container.innerHTML = createEmptyState("No machine selected", "Select a machine to load tags.");
    return;
  }
  const groupedTags = getGroupedTags();
  if (!groupedTags.length) {
    container.innerHTML = createEmptyState("No tags found", "Adjust search, filters, or scored-profile mode.");
    return;
  }
  for (const [folder, tags] of groupedTags) {
    const visibleTags = sortTags(tags);
    const group = document.createElement("div");
    group.className = "tag-group";
    const collapsed = !!state.folderCollapsed[folder];
    group.innerHTML = `
      <button class="tag-group-header" type="button">
        <span class="tag-group-title">${folder}</span>
        <span class="tag-group-count">${visibleTags.length} tag(s) ${collapsed ? "▸" : "▾"}</span>
      </button>
      <div class="tag-group-body ${collapsed ? "hidden" : ""}"></div>
    `;
    group.querySelector(".tag-group-header").addEventListener("click", () => {
      state.folderCollapsed[folder] = !state.folderCollapsed[folder];
      renderTagList();
    });
    const body = group.querySelector(".tag-group-body");
    for (const tag of visibleTags) {
      const usefulness = getTagUsefulness(tag);
      const reasonTitle = usefulness?.reasons?.join("; ") || "";
      const item = document.createElement("div");
      item.className = "tag-item";
      if (usefulness?.grade && ["high", "medium"].includes(usefulness.grade) && usefulness.semantic_type === "continuous_numeric") {
        item.classList.add("selected-recommended");
      }
      if (state.targetTag && state.targetTag.tag_id === tag.tag_id) {
        item.classList.add("selected");
      }
      item.title = reasonTitle;
      item.innerHTML = `
        <div class="tag-item-head">
          <div class="tag-item-title">${tag.display_name || tag.browse_name || `Tag ${tag.tag_id}`}</div>
          <div class="badge-row">
            <span class="badge numeric">numeric</span>
            ${isStaleTag(tag) ? createBadge("stale", "stale") : ""}
            ${isLowSampleTag(tag) ? createBadge("low-sample", "low-sample") : ""}
            ${usefulness ? createBadge(usefulness.grade, usefulness.grade) : ""}
          </div>
        </div>
        ${
          usefulness
            ? `<div class="tag-score-row">
                ${createBadge(usefulness.semantic_type, "semantic")}
                ${createBadge(`${usefulness.score}/100`)}
              </div>`
            : ""
        }
        <div class="tag-item-meta">Tag ID: ${tag.tag_id} | Type: ${tag.data_type || "-"}</div>
        <div class="tag-item-meta">Samples: ${tag.sample_count ?? "-"} | Last Seen: ${tag.last_seen_utc || "-"}</div>
        ${
          usefulness
            ? `<div class="tag-item-meta">Min/Max: ${formatNumber(tag.min_value)} / ${formatNumber(tag.max_value)}</div>`
            : ""
        }
        <div class="tag-item-meta">${tag.opc_path || "-"}</div>
      `;
      item.addEventListener("click", () => setTargetTag(tag));
      body.appendChild(item);
    }
    container.appendChild(group);
  }
}

async function loadTags() {
  if (!state.selectedMachineId) {
    state.tags = [];
    renderTagList();
    showError("Select a machine before loading tags.");
    return;
  }
  const numericOnly = document.getElementById("numeric-only").checked;
  const search = document.getElementById("tag-search").value.trim();
  const params = new URLSearchParams();
  params.set("numeric_only", String(numericOnly));
  params.set("limit", "1000");
  if (search) {
    params.set("search", search);
  }
  disableButton("refresh-tags-btn", true);
  await withLoading("tags", async () => {
    try {
      if (state.useScoredProfiles) {
        const response = await apiGet(
          `/api/machines/${state.selectedMachineId}/tags/profiles?${params.toString()}`
        );
        state.tags = (response.profiles || []).map((tag) => ({
          ...tag,
          is_numeric: Number(tag.numeric_sample_count || 0) > 0,
          folder_name: folderNameFromTag(tag),
        }));
      } else {
        const tree = await apiGet(`/api/machines/${state.selectedMachineId}/tags/tree?${params.toString()}`);
        state.tags = flattenTagTree(tree).sort((a, b) => {
          const folderCompare = (a.folder_name || "").localeCompare(b.folder_name || "");
          if (folderCompare !== 0) {
            return folderCompare;
          }
          return (a.display_name || a.browse_name || a.opc_path || "").localeCompare(
            b.display_name || b.browse_name || b.opc_path || "",
          );
        });
      }
      if (state.targetTag) {
        state.targetTag = state.tags.find((tag) => tag.tag_id === state.targetTag.tag_id) || null;
      }
      renderTagList();
      renderTargetTag();
      updateChartPlaceholder();
      updateWorkflowSteps();
      persistWorkspace();
      setGlobalStatus(`Loaded ${state.tags.length} tag(s).`, "success");
    } catch (error) {
      state.tags = [];
      renderTagList();
      showError(`Failed to load tags: ${error.message}`);
      setGlobalStatus("Tag loading failed.", "danger");
    }
  }, "Loading...");
  disableButton("refresh-tags-btn", false);
}

function setTargetTag(tag) {
  state.targetTag = tag;
  state.analysisResults = [];
  state.lastAnalysisResponse = null;
  state.selectedResultTagIds = new Set();
  state.lastTimeseriesRequest = null;
  state.lastTimeseriesResponse = null;
  renderTagList();
  renderTargetTag();
  renderAnalysisSummary(null);
  renderRelationshipResults();
  renderSelectedSeriesList();
  clearError();
  clearChart();
  showToast(`Target selected: ${tag.display_name || tag.browse_name || tag.opc_path || `Tag ${tag.tag_id}`}`, "success");
  setGlobalStatus(`Target selected: ${tag.display_name || tag.browse_name || tag.opc_path || `Tag ${tag.tag_id}`}.`, "info");
  updateChartPlaceholder();
  updateWorkflowSteps();
  persistWorkspace();
}

function renderTargetTag() {
  const card = document.getElementById("target-card");
  if (!state.targetTag) {
    card.className = "target-card empty-state";
    card.textContent = "Pick a numeric tag from the left to analyze.";
    return;
  }
  card.className = "target-card";
  const usefulness = getTagUsefulness(state.targetTag);
  if (usefulness?.grade && ["high", "medium"].includes(usefulness.grade) && usefulness.semantic_type === "continuous_numeric") {
    card.classList.add("target-recommended");
  }
  card.innerHTML = `
    <strong>${state.targetTag.display_name || state.targetTag.browse_name || `Tag ${state.targetTag.tag_id}`}</strong>
    <div class="tag-item-meta">Tag ID: ${state.targetTag.tag_id}</div>
    <div class="tag-item-meta">Path: ${state.targetTag.opc_path || "-"}</div>
    <div class="tag-item-meta">Type: ${state.targetTag.data_type || "-"}</div>
    <div class="tag-item-meta">Samples: ${state.targetTag.sample_count ?? "-"}</div>
    ${
      state.targetTag.numeric_sample_count !== undefined
        ? `<div class="tag-item-meta">Numeric samples: ${state.targetTag.numeric_sample_count ?? "-"}</div>`
        : ""
    }
    <div class="tag-item-meta">Last Seen: ${state.targetTag.last_seen_utc || "-"}</div>
    ${
      usefulness
        ? `<div class="tag-item-meta">Usefulness: ${usefulness.score}/100 (${usefulness.grade}, ${usefulness.semantic_type})</div>
           <div class="tag-score-row">
             ${createBadge(usefulness.grade, usefulness.grade)}
             ${createBadge(usefulness.semantic_type, "semantic")}
             ${(usefulness.badges || []).slice(0, 4).map((badge) => createBadge(badge)).join("")}
           </div>
           <div class="tag-item-meta">${escapeHtml((usefulness.reasons || []).join(" | "))}</div>`
        : ""
    }
  `;
}

function getAnalysisPayload() {
  if (!state.selectedMachineId || !state.targetTag) {
    if (!state.selectedMachineId) {
      throw new Error("Select a machine first.");
    }
    throw new Error("Select a target tag first.");
  }
  const startUtc = document.getElementById("start-utc").value.trim();
  const endUtc = document.getElementById("end-utc").value.trim();
  const bucketSeconds = Number(document.getElementById("bucket-seconds").value);
  const maxResults = Number(document.getElementById("max-results").value);
  if (!startUtc || !endUtc) {
    throw new Error("Start UTC and End UTC are required.");
  }
  if (new Date(startUtc).getTime() >= new Date(endUtc).getTime()) {
    throw new Error("Start UTC must be before End UTC.");
  }
  if (bucketSeconds < 1) {
    throw new Error("Bucket seconds must be at least 1.");
  }
  if (maxResults < 1) {
    throw new Error("Max results must be positive.");
  }
  return {
    target: {
      machine_id: Number(state.selectedMachineId),
      tag_id: state.targetTag.tag_id,
      label: state.targetTag.display_name || state.targetTag.browse_name || state.targetTag.opc_path,
    },
    start_utc: startUtc,
    end_utc: endUtc,
    bucket_seconds: bucketSeconds,
    max_points_per_series: 2000,
    candidate_scope: document.getElementById("candidate-scope").value,
    candidate_tag_ids: null,
    max_candidate_tags: Number(document.getElementById("max-candidate-tags").value),
    max_results: Number(document.getElementById("max-results").value),
    min_pair_count: Number(document.getElementById("min-pair-count").value),
    max_lag_seconds: Number(document.getElementById("max-lag-seconds").value),
  };
}

async function runRelationshipAnalysis() {
  clearError();
  let payload;
  try {
    if (!state.selectedMachineId) {
      throw new Error("Select a machine first.");
    }
    if (!state.targetTag) {
      throw new Error("Select a target tag first.");
    }
    const preflight = getTargetPreflight(state.targetTag);
    if (preflight.blocked) {
      showError(preflight.messages[0]);
      return;
    }
    if (preflight.weak) {
      showToast("This target may not have enough changing numeric data. Analysis may return no results.", "warning");
      setGlobalStatus("Target looks weak for relationship analysis. Consider choosing a better target or expanding the time range.", "warning");
    }
    payload = getAnalysisPayload();
  } catch (error) {
    showError(error.message);
    return;
  }
  disableButton("run-analysis-btn", true);
  await withLoading("analysis", async () => {
    try {
      const response = await apiPost("/api/analysis/relationships", payload);
      state.lastAnalysisResponse = response;
      state.analysisResults = response.results || [];
      const keptSelections = new Set();
      for (const result of state.analysisResults) {
        if (state.selectedResultTagIds.has(result.tag_id)) {
          keptSelections.add(result.tag_id);
        }
      }
      state.selectedResultTagIds = keptSelections;
      renderAnalysisSummary(response);
      renderRelationshipResults();
      renderSelectedSeriesList();
      updateChartPlaceholder();
      updateWorkflowSteps();
      persistWorkspace();
      showToast("Relationship analysis completed.", "success");
      setGlobalStatus(`Analysis completed with ${state.analysisResults.length} result(s).`, "success");
    } catch (error) {
      state.analysisResults = [];
      state.lastAnalysisResponse = null;
      renderAnalysisSummary(null);
      renderRelationshipResults();
      updateWorkflowSteps();
      showError(`Relationship analysis failed: ${error.message}`);
      setGlobalStatus("Relationship analysis failed.", "danger");
    }
  }, "Running...");
  disableButton("run-analysis-btn", false);
}

function renderAnalysisSummary(response) {
  const analysis = response?.analysis || null;
  const windowInfo = response?.window || null;
  const warningBox = document.getElementById("analysis-warning-box");
  document.getElementById("summary-scanned").textContent = analysis?.candidate_count_scanned ?? "-";
  document.getElementById("summary-analyzed").textContent = analysis?.candidate_count_analyzed ?? "-";
  document.getElementById("summary-skipped").textContent = analysis?.skipped_count ?? "-";
  document.getElementById("summary-warnings").textContent = (analysis?.warnings || []).length;

  const skippedList = document.getElementById("skipped-by-reason-list");
  skippedList.innerHTML = "";
  const skippedItems = Object.entries(analysis?.skipped_by_reason || {});
  if (!skippedItems.length) {
    skippedList.innerHTML = "<li>-</li>";
  } else {
    for (const [reason, count] of skippedItems) {
      const item = document.createElement("li");
      item.textContent = `${readableSkipReason(reason)}: ${count}`;
      item.title = reason;
      skippedList.appendChild(item);
    }
  }

  const warningList = document.getElementById("warning-list");
  warningList.innerHTML = "";
  const warnings = analysis?.warnings || [];
  if (!warnings.length) {
    warningList.innerHTML = "<li>-</li>";
  } else {
    const rawTargetCount = analysis?.skipped_by_reason?.target_insufficient_data || 0;
    const targetDominates = rawTargetCount > 0 && rawTargetCount >= Math.max(1, (analysis?.skipped_count || 0) - 1);
    const prioritizedWarnings = targetDominates
      ? warnings.filter((warning) => !warning.includes("candidate scan reached max_candidate_tags"))
      : warnings;
    for (const warning of prioritizedWarnings) {
      const item = document.createElement("li");
      item.textContent = warning;
      warningList.appendChild(item);
    }
  }

  const settingsList = document.getElementById("analysis-settings-list");
  settingsList.innerHTML = "";
  for (const setting of [
    `requested_bucket_seconds: ${windowInfo?.requested_bucket_seconds ?? "-"}`,
    `actual_bucket_seconds: ${windowInfo?.actual_bucket_seconds ?? "-"}`,
    `candidate_scope: ${analysis?.candidate_scope ?? "-"}`,
    `min_pair_count: ${analysis?.min_pair_count ?? "-"}`,
  ]) {
    const item = document.createElement("li");
    item.textContent = setting;
    settingsList.appendChild(item);
  }

  const rawTargetCount = analysis?.skipped_by_reason?.target_insufficient_data || 0;
  const targetDominates = rawTargetCount > 0 && rawTargetCount >= Math.max(1, (analysis?.skipped_count || 0) - 1);
  if (targetDominates) {
    warningBox.classList.remove("hidden");
    warningBox.innerHTML = `
      <strong>The selected target did not have enough usable numeric data in this time range.</strong>
      <div>Fix the target first; candidate results were not meaningful.</div>
      <div>Recommended actions:</div>
      <ol>
        <li>Choose a different target tag with more samples.</li>
        <li>Expand the time range.</li>
        <li>Lower Min Pair Count.</li>
        <li>Use scored profiles and select a high/medium continuous_numeric tag.</li>
      </ol>
    `;
  } else {
    warningBox.classList.add("hidden");
    warningBox.innerHTML = "";
  }
}

function getFilteredSortedResults() {
  let results = [...state.analysisResults];
  if (state.activeRelationshipFilter !== "all") {
    results = results.filter((result) => result.relationship_type === state.activeRelationshipFilter);
  }
  results.sort((a, b) => {
    if (state.resultSort === "abs_lag_desc") {
      return Math.abs(b.best_lag_seconds || 0) - Math.abs(a.best_lag_seconds || 0);
    }
    if (state.resultSort === "pair_count_desc") {
      return (b.pair_count || 0) - (a.pair_count || 0);
    }
    if (state.resultSort === "display_name_asc") {
      return (a.display_name || a.label || "").localeCompare(b.display_name || b.label || "");
    }
    return (b.score || 0) - (a.score || 0);
  });
  return results;
}

function rowClassForRelationship(type) {
  if (type === "possible_driver") {
    return "row-driver";
  }
  if (type === "possible_effect") {
    return "row-effect";
  }
  if (type === "moves_together") {
    return "row-together";
  }
  return "";
}

function toggleResultSelection(tagId) {
  if (state.selectedResultTagIds.has(tagId)) {
    state.selectedResultTagIds.delete(tagId);
  } else {
    state.selectedResultTagIds.add(tagId);
  }
  renderRelationshipResults();
  renderSelectedSeriesList();
  updateChartPlaceholder();
  persistWorkspace();
}

function renderRelationshipResults() {
  const tbody = document.getElementById("results-table-body");
  const resultsCount = document.getElementById("results-count");
  tbody.innerHTML = "";
  if (!state.analysisResults.length) {
    resultsCount.textContent = "No results loaded.";
    tbody.innerHTML = '<tr><td colspan="11" class="empty-cell">Run analysis to see related tags.</td></tr>';
    return;
  }
  const results = getFilteredSortedResults();
  resultsCount.textContent = `${results.length} visible result(s) of ${state.analysisResults.length}.`;
  if (!results.length) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty-cell">No results match the current filter.</td></tr>';
    return;
  }
  results.forEach((result, index) => {
    const row = document.createElement("tr");
    row.classList.add(rowClassForRelationship(result.relationship_type));
    if (state.selectedResultTagIds.has(result.tag_id)) {
      row.classList.add("selected");
    }
    row.innerHTML = `
      <td><input type="checkbox" ${state.selectedResultTagIds.has(result.tag_id) ? "checked" : ""}></td>
      <td>${index + 1}</td>
      <td>${result.relationship_type || "-"}</td>
      <td>${formatNumber(result.score)}</td>
      <td>${formatNumber(result.same_time_corr)}</td>
      <td>${formatNumber(result.delta_corr)}</td>
      <td>${formatNumber(result.best_lag_corr)}</td>
      <td>${result.best_lag_seconds ?? "-"}</td>
      <td>${result.pair_count ?? "-"}</td>
      <td>${result.display_name || result.label || "-"}</td>
      <td>${result.opc_path || "-"}</td>
    `;
    row.addEventListener("click", () => toggleResultSelection(result.tag_id));
    row.querySelector("input[type=checkbox]").addEventListener("click", (event) => {
      event.stopPropagation();
      toggleResultSelection(result.tag_id);
    });
    tbody.appendChild(row);
  });
}

function renderSelectedSeriesList() {
  const list = document.getElementById("selected-series-list");
  list.innerHTML = "";
  if (!state.targetTag && state.selectedResultTagIds.size === 0) {
    list.innerHTML = "<li>No series selected.</li>";
    return;
  }
  if (state.targetTag) {
    const item = document.createElement("li");
    item.textContent = `Target: ${state.targetTag.display_name || state.targetTag.opc_path}`;
    list.appendChild(item);
  }
  const selected = state.analysisResults.filter((result) => state.selectedResultTagIds.has(result.tag_id));
  if (!selected.length) {
    list.innerHTML += "<li>No related tags selected yet.</li>";
    return;
  }
  for (const result of selected) {
    const item = document.createElement("li");
    item.textContent = `${result.display_name || result.label || `Tag ${result.tag_id}`} (${result.opc_path || result.tag_id})`;
    list.appendChild(item);
  }
}

function normalizeSeriesValues(values) {
  const finiteValues = values.filter((value) => typeof value === "number");
  if (!finiteValues.length) {
    return values;
  }
  const minValue = Math.min(...finiteValues);
  const maxValue = Math.max(...finiteValues);
  if (maxValue === minValue) {
    return values.map((value) => (typeof value === "number" ? 0.5 : null));
  }
  return values.map((value) =>
    typeof value === "number" ? (value - minValue) / (maxValue - minValue) : null
  );
}

function buildChartPayload(series, settings) {
  return {
    series,
    start_utc: settings.start_utc,
    end_utc: settings.end_utc,
    bucket_seconds: settings.bucket_seconds,
    aggregation: settings.aggregation || "avg",
    max_points_per_series: 2000,
  };
}

function buildDatasetsFromTimeseries(series, chartMode) {
  const labels = [];
  for (const entry of series) {
    for (const point of entry.points || []) {
      if (!labels.includes(point.t)) {
        labels.push(point.t);
      }
    }
  }
  labels.sort();
  const palette = ["#4fb0ff", "#7bd389", "#f2c14e", "#ef6f6c", "#c792ea", "#5ec8e5", "#ff9f68", "#9ccc65"];
  const datasets = series.map((entry, index) => {
    const rawValues = labels.map((label) => {
      const match = (entry.points || []).find((point) => point.t === label);
      return match ? match.v : null;
    });
    const data = chartMode === "normalized" ? normalizeSeriesValues(rawValues) : rawValues;
    return {
      label: entry.label || `Tag ${entry.tag_id}`,
      data,
      borderColor: palette[index % palette.length],
      backgroundColor: palette[index % palette.length],
      tension: 0.15,
      borderWidth: index === 0 ? 3 : 2,
      pointRadius: 0,
      spanGaps: true,
    };
  });
  return { labels, datasets };
}

function buildBarChartData(series, aggregation) {
  const palette = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#ea580c", "#65a30d"];
  return {
    labels: series.map((entry) => entry.label || `Tag ${entry.tag_id}`),
    datasets: [
      {
        label: aggregation || "avg",
        data: series.map((entry) => {
          const points = entry.points || [];
          if (!points.length) {
            return null;
          }
          if (aggregation === "min") {
            return Math.min(...points.map((point) => point.min_value ?? point.v).filter((value) => typeof value === "number"));
          }
          if (aggregation === "max") {
            return Math.max(...points.map((point) => point.max_value ?? point.v).filter((value) => typeof value === "number"));
          }
          const values = points.map((point) => point.v).filter((value) => typeof value === "number");
          if (!values.length) {
            return null;
          }
          return values.reduce((sum, value) => sum + value, 0) / values.length;
        }),
        backgroundColor: series.map((_, index) => palette[index % palette.length]),
        borderColor: series.map((_, index) => palette[index % palette.length]),
        borderWidth: 1,
      },
    ],
  };
}

function createChart(canvas, series, chartMode, chartType = "line", aggregation = "avg") {
  const context = canvas.getContext("2d");
  const chartData = chartType === "bar"
    ? buildBarChartData(series, aggregation)
    : buildDatasetsFromTimeseries(series, chartMode);
  return new Chart(context, {
    type: chartType,
    data: chartData,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "nearest", intersect: false },
      plugins: {
        legend: { labels: { color: "#334155" } },
        tooltip: {
          callbacks: {
            title(items) {
              return items[0]?.label || "";
            },
            label(contextItem) {
              const value = contextItem.parsed.y;
              return `${contextItem.dataset.label}: ${typeof value === "number" ? value.toFixed(4) : "-"}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: "#64748b",
            maxRotation: 0,
            callback(value, index) {
              const label = chartData.labels[index] || "";
              return label.replace("T", " ").replace("+00:00", " UTC");
            },
          },
          grid: { color: "rgba(148, 163, 184, 0.18)" },
        },
        y: {
          ticks: {
            color: "#64748b",
            callback(value) {
              return chartMode === "normalized" ? Number(value).toFixed(2) : value;
            },
          },
          grid: { color: "rgba(148, 163, 184, 0.18)" },
        },
      },
    },
  });
}

async function plotSelectedSeries() {
  clearError();
  if (!state.selectedMachineId) {
    showError("Select a machine first.");
    return;
  }
  if (!state.targetTag) {
    showError("Select a target tag before plotting.");
    return;
  }
  const selectedResults = state.analysisResults.filter((result) => state.selectedResultTagIds.has(result.tag_id));
  if (!selectedResults.length) {
    showToast("Plotting target only. Select related tags after analysis to compare.", "info");
  }
  const requestPayload = buildChartPayload(
    [
      {
        machine_id: Number(state.selectedMachineId),
        tag_id: state.targetTag.tag_id,
        label: `Target: ${state.targetTag.display_name || state.targetTag.opc_path}`,
      },
      ...selectedResults.map((result) => ({
        machine_id: Number(state.selectedMachineId),
        tag_id: result.tag_id,
        label: result.display_name || result.label || result.opc_path,
      })),
    ],
    {
      start_utc: document.getElementById("start-utc").value.trim(),
      end_utc: document.getElementById("end-utc").value.trim(),
      bucket_seconds: Number(document.getElementById("bucket-seconds").value),
      aggregation: document.getElementById("chart-aggregation").value,
    },
  );

  disableButton("plot-selected-btn", true);
  disableButton("clear-chart-btn", true);
  await withLoading("chart", async () => {
    try {
      const response = await apiPost("/api/timeseries/query", requestPayload);
      state.lastTimeseriesRequest = requestPayload;
      state.lastTimeseriesResponse = response;
      renderChart(response.series || []);
      updateWorkflowSteps();
      persistWorkspace();
      showToast("Chart plotted.", "success");
      setGlobalStatus(`Chart updated with ${response.series?.length || 0} series.`, "success");
    } catch (error) {
      showError(`Failed to load chart data: ${error.message}`);
      setGlobalStatus("Chart request failed.", "danger");
    }
  }, "Loading...");
  disableButton("plot-selected-btn", false);
  disableButton("clear-chart-btn", false);
}

function renderChart(series) {
  const canvas = document.getElementById("trend-chart");
  const chartMode = document.getElementById("chart-mode").value;
  const aggregation = document.getElementById("chart-aggregation").value;
  const chartWarning = document.getElementById("chart-warning");
  if (state.chart) {
    state.chart.destroy();
  }
  document.getElementById("chart-empty-state").classList.toggle("hidden", !!series.length);
  if (series.length > 8) {
    chartWarning.textContent = "Plotting more than 8 series may be hard to read.";
    chartWarning.classList.remove("hidden");
  } else {
    chartWarning.classList.add("hidden");
    chartWarning.textContent = "";
  }
  state.chart = createChart(canvas, series, chartMode, "line", aggregation);
  updateChartPlaceholder();
}

function clearChart() {
  if (state.chart) {
    state.chart.destroy();
    state.chart = null;
  }
  state.lastTimeseriesRequest = null;
  state.lastTimeseriesResponse = null;
  document.getElementById("chart-empty-state").classList.remove("hidden");
  document.getElementById("chart-warning").classList.add("hidden");
  document.getElementById("chart-warning").textContent = "";
  updateChartPlaceholder();
  updateWorkflowSteps();
}

function selectTopResults(limit) {
  const results = getFilteredSortedResults().slice(0, limit);
  for (const result of results) {
    state.selectedResultTagIds.add(result.tag_id);
  }
  renderRelationshipResults();
  renderSelectedSeriesList();
  updateChartPlaceholder();
  persistWorkspace();
}

function clearSelectedResults() {
  state.selectedResultTagIds = new Set();
  renderRelationshipResults();
  renderSelectedSeriesList();
  updateChartPlaceholder();
  persistWorkspace();
}

function applyFilterButtonState(containerId, activeValue, attributeName) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }
  for (const button of container.querySelectorAll(`[${attributeName}]`)) {
    button.classList.toggle("active", button.getAttribute(attributeName) === activeValue);
  }
}

function getBuilderMachineId() {
  const value = document.getElementById("builder-machine-select").value;
  return value ? Number(value) : null;
}

function getBuilderPanelType() {
  return document.getElementById("builder-panel-type").value;
}

function getBuilderSelectedTags() {
  return state.builderTags.filter((tag) => state.builderSelectedTagIds.has(tag.tag_id));
}

function renderDashboardBuilderSelectedTags() {
  const list = document.getElementById("builder-selected-tags-list");
  const tags = getBuilderSelectedTags();
  list.innerHTML = "";
  if (!tags.length) {
    list.innerHTML = "<li>No tags selected.</li>";
    return;
  }
  for (const tag of tags) {
    const item = document.createElement("li");
    item.textContent = `${tagDisplayLabel(tag)} (${tag.tag_id})`;
    list.appendChild(item);
  }
}

function builderSearchValue() {
  return document.getElementById("builder-tag-search").value.trim().toLowerCase();
}

function renderDashboardBuilderTagList() {
  const container = document.getElementById("builder-tag-list");
  const machineId = getBuilderMachineId();
  container.innerHTML = "";
  if (!machineId) {
    container.innerHTML = createEmptyState("No machine selected", "Choose a machine for the dashboard panel.");
    return;
  }
  const search = builderSearchValue();
  const tags = state.builderTags.filter((tag) => {
    if (!search) {
      return true;
    }
    return [
      tag.display_name,
      tag.browse_name,
      tag.opc_path,
      tag.tag_id,
      tag.data_type,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(search);
  });
  if (!tags.length) {
    container.innerHTML = createEmptyState("No tags found", "Adjust the builder search or load a different machine.");
    return;
  }
  for (const tag of sortTags(tags)) {
    const usefulness = getTagUsefulness(tag);
    const item = document.createElement("div");
    item.className = "tag-item";
    if (state.builderSelectedTagIds.has(tag.tag_id)) {
      item.classList.add("selected");
    }
    if (usefulness?.grade && ["high", "medium"].includes(usefulness.grade) && usefulness.semantic_type === "continuous_numeric") {
      item.classList.add("selected-recommended");
    }
    item.innerHTML = `
      <div class="tag-item-head">
        <div class="tag-item-title">${tagDisplayLabel(tag)}</div>
        <div class="badge-row">
          ${usefulness ? createBadge(usefulness.grade, usefulness.grade) : ""}
          ${usefulness ? createBadge(usefulness.semantic_type, "semantic") : ""}
        </div>
      </div>
      <div class="tag-item-meta">Tag ID: ${tag.tag_id} | Samples: ${tag.sample_count ?? "-"}</div>
      <div class="tag-item-meta">${tag.opc_path || "-"}</div>
    `;
    item.addEventListener("click", () => {
      const type = getBuilderPanelType();
      const singleSelectTypes = new Set(["kpi", "tag_profile", "relationship_results"]);
      if (singleSelectTypes.has(type)) {
        state.builderSelectedTagIds = new Set([tag.tag_id]);
      } else if (state.builderSelectedTagIds.has(tag.tag_id)) {
        state.builderSelectedTagIds.delete(tag.tag_id);
      } else {
        state.builderSelectedTagIds.add(tag.tag_id);
      }
      renderDashboardBuilderTagList();
      renderDashboardBuilderSelectedTags();
    });
    container.appendChild(item);
  }
}

async function loadDashboardBuilderTags() {
  const machineId = getBuilderMachineId();
  if (!machineId) {
    state.builderTags = [];
    state.builderSelectedTagIds = new Set();
    renderDashboardBuilderTagList();
    renderDashboardBuilderSelectedTags();
    return;
  }
  const useScored = document.getElementById("builder-use-scored-profiles").checked;
  const search = document.getElementById("builder-tag-search").value.trim();
  const params = new URLSearchParams({
    numeric_only: "true",
    limit: "1000",
  });
  if (search) {
    params.set("search", search);
  }
  const previouslySelectedIds = new Set(state.builderSelectedTagIds);
  disableButton("builder-refresh-tags-btn", true);
  await withLoading("builderTags", async () => {
    try {
      if (useScored) {
        const response = await apiGet(`/api/machines/${machineId}/tags/profiles?${params.toString()}`);
        state.builderTags = (response.profiles || []).map((tag) => ({
          ...tag,
          is_numeric: Number(tag.numeric_sample_count || 0) > 0,
          folder_name: folderNameFromTag(tag),
        }));
      } else {
        const tree = await apiGet(`/api/machines/${machineId}/tags/tree?${params.toString()}`);
        state.builderTags = flattenTagTree(tree).map((tag) => ({
          ...tag,
          folder_name: folderNameFromTag(tag),
        }));
      }
      state.builderSelectedTagIds = new Set(
        Array.from(previouslySelectedIds).filter((tagId) =>
          state.builderTags.some((tag) => tag.tag_id === tagId)
        )
      );
      renderDashboardBuilderTagList();
      renderDashboardBuilderSelectedTags();
    } catch (error) {
      state.builderTags = [];
      renderDashboardBuilderTagList();
      showError(`Failed to load dashboard builder tags: ${error.message}`);
    }
  }, "Loading...");
  disableButton("builder-refresh-tags-btn", false);
}

function defaultBuilderTitle(panelType, selectedTags) {
  if (!selectedTags.length) {
    return panelType === "line_trend" ? "Line trend" : panelType.replaceAll("_", " ");
  }
  if (panelType === "kpi") {
    return `${tagDisplayLabel(selectedTags[0])} KPI`;
  }
  if (panelType === "tag_profile") {
    return `${tagDisplayLabel(selectedTags[0])} Profile`;
  }
  if (panelType === "relationship_results") {
    return `${tagDisplayLabel(selectedTags[0])} Relationships`;
  }
  return selectedTags.length > 1
    ? `${tagDisplayLabel(selectedTags[0])} + ${selectedTags.length - 1} more`
    : tagDisplayLabel(selectedTags[0]);
}

function builderTimeSettings() {
  return {
    start_utc: document.getElementById("builder-start-utc").value.trim(),
    end_utc: document.getElementById("builder-end-utc").value.trim(),
    bucket_seconds: Number(document.getElementById("builder-bucket-seconds").value),
    aggregation: document.getElementById("builder-aggregation").value,
    chart_mode: document.getElementById("builder-chart-mode").value,
  };
}

function validatePanelBuilder() {
  const panelType = getBuilderPanelType();
  const machineId = getBuilderMachineId();
  const selectedTags = getBuilderSelectedTags();
  const timeSettings = builderTimeSettings();

  if (!machineId) {
    throw new Error("Select a machine for the dashboard panel.");
  }
  if (!timeSettings.start_utc || !timeSettings.end_utc) {
    throw new Error("Start UTC and End UTC are required for the dashboard panel.");
  }
  if (new Date(timeSettings.start_utc).getTime() >= new Date(timeSettings.end_utc).getTime()) {
    throw new Error("Start UTC must be before End UTC.");
  }
  if (timeSettings.bucket_seconds < 1) {
    throw new Error("Bucket seconds must be at least 1.");
  }
  if (["line_trend", "bar_chart"].includes(panelType) && selectedTags.length < 1) {
    throw new Error("Line and bar panels require at least one selected tag.");
  }
  if (["kpi", "tag_profile", "relationship_results"].includes(panelType) && selectedTags.length !== 1) {
    throw new Error("This panel type requires exactly one selected tag.");
  }
  if (!document.getElementById("builder-panel-title").value.trim()) {
    document.getElementById("builder-panel-title").value = defaultBuilderTitle(panelType, selectedTags);
  }
}

function buildPanelFromBuilder() {
  validatePanelBuilder();
  const panelType = getBuilderPanelType();
  const machineId = getBuilderMachineId();
  const selectedTags = getBuilderSelectedTags();
  const timeSettings = builderTimeSettings();
  const title = document.getElementById("builder-panel-title").value.trim();
  const width = Number(document.getElementById("builder-panel-width").value);
  const height = Number(document.getElementById("builder-panel-height").value);
  const base = {
    id: state.builderEditingPanelId || generatePanelId(),
    title,
    layout: { ...getNextPanelLayout(), w: width, h: height },
    refresh: { mode: "manual", last_refreshed_utc: null },
    settings: {},
    series: [],
    data: {},
  };

  if (panelType === "line_trend" || panelType === "bar_chart") {
    return {
      ...base,
      type: "timeseries",
      settings: {
        chart_type: panelType === "bar_chart" ? "bar" : "line",
        aggregation: timeSettings.aggregation,
        chart_mode: timeSettings.chart_mode,
        start_utc: timeSettings.start_utc,
        end_utc: timeSettings.end_utc,
        bucket_seconds: timeSettings.bucket_seconds,
      },
      series: selectedTags.map((tag) => ({
        machine_id: machineId,
        tag_id: tag.tag_id,
        label: tagDisplayLabel(tag),
      })),
      data: {},
    };
  }
  if (panelType === "kpi") {
    return {
      ...base,
      type: "kpi",
      settings: {
        machine_id: machineId,
        tag_id: selectedTags[0].tag_id,
        label: tagDisplayLabel(selectedTags[0]),
        start_utc: timeSettings.start_utc,
        end_utc: timeSettings.end_utc,
        bucket_seconds: timeSettings.bucket_seconds,
        aggregation: timeSettings.aggregation,
      },
      data: {},
    };
  }
  if (panelType === "tag_profile") {
    return {
      ...base,
      type: "tag_profile",
      settings: {
        machine_id: machineId,
        tag_id: selectedTags[0].tag_id,
        start_utc: timeSettings.start_utc,
        end_utc: timeSettings.end_utc,
      },
      data: {},
    };
  }
  return {
    ...base,
    type: "relationship_results",
    settings: {
      request: {
        target: {
          machine_id: machineId,
          tag_id: selectedTags[0].tag_id,
          label: tagDisplayLabel(selectedTags[0]),
        },
        start_utc: timeSettings.start_utc,
        end_utc: timeSettings.end_utc,
        bucket_seconds: timeSettings.bucket_seconds,
        max_points_per_series: 2000,
        candidate_scope: "same_machine",
        candidate_tag_ids: null,
        max_candidate_tags: 300,
        max_results: 25,
        min_pair_count: 30,
        max_lag_seconds: 1800,
        prefer_useful_candidates: true,
      },
    },
    data: {},
  };
}

function summarizePanelDataSource(panel) {
  if (panel.type === "timeseries") {
    return `${panel.series.length} tag(s) | ${panel.settings.start_utc || "-"} to ${panel.settings.end_utc || "-"}`;
  }
  if (panel.type === "kpi" || panel.type === "tag_profile") {
    return `Machine ${panel.settings.machine_id} | Tag ${panel.settings.tag_id}`;
  }
  if (panel.type === "relationship_results") {
    return `Target tag ${panel.settings?.request?.target?.tag_id || "-"}`;
  }
  return "";
}

async function hydratePanelData(panel) {
  panel.data = panel.data || {};
  panel.data.error = null;
  if (panel.type === "timeseries") {
    panel.data.response = await apiPost(
      "/api/timeseries/query",
      buildChartPayload(panel.series, {
        start_utc: panel.settings.start_utc,
        end_utc: panel.settings.end_utc,
        bucket_seconds: panel.settings.bucket_seconds,
        aggregation: panel.settings.aggregation,
      }),
    );
    return;
  }
  if (panel.type === "relationship_results") {
    panel.data.response = await apiPost("/api/analysis/relationships", panel.settings.request);
    return;
  }
  if (panel.type === "tag_profile") {
    const params = new URLSearchParams();
    if (panel.settings.start_utc) {
      params.set("start_utc", panel.settings.start_utc);
    }
    if (panel.settings.end_utc) {
      params.set("end_utc", panel.settings.end_utc);
    }
    panel.data.profile = await apiGet(
      `/api/machines/${panel.settings.machine_id}/tags/${panel.settings.tag_id}/scored-profile?${params.toString()}`
    );
    return;
  }
  if (panel.type === "kpi") {
    const params = new URLSearchParams();
    if (panel.settings.start_utc) {
      params.set("start_utc", panel.settings.start_utc);
    }
    if (panel.settings.end_utc) {
      params.set("end_utc", panel.settings.end_utc);
    }
    panel.data.profile = await apiGet(
      `/api/machines/${panel.settings.machine_id}/tags/${panel.settings.tag_id}/scored-profile?${params.toString()}`
    );
    panel.data.response = await apiPost(
      "/api/timeseries/query",
      buildChartPayload(
        [
          {
            machine_id: panel.settings.machine_id,
            tag_id: panel.settings.tag_id,
            label: panel.settings.label || `Tag ${panel.settings.tag_id}`,
          },
        ],
        {
          start_utc: panel.settings.start_utc,
          end_utc: panel.settings.end_utc,
          bucket_seconds: panel.settings.bucket_seconds || 60,
          aggregation: panel.settings.aggregation || "avg",
        },
      ),
    );
  }
}

function destroyBuilderPreviewChart() {
  if (state.builderPreviewChart) {
    state.builderPreviewChart.destroy();
    state.builderPreviewChart = null;
  }
}

function renderPreviewPanel(panel) {
  const mount = document.getElementById("dashboard-builder-preview");
  mount.classList.remove("empty-state");
  mount.innerHTML = `
    <div class="dashboard-panel-head">
      <div class="dashboard-panel-title">
        <h3>${escapeHtml(panel.title)}</h3>
        <span class="type-badge ${panel.type}">${panel.type}</span>
      </div>
    </div>
    <div class="dashboard-meta">${escapeHtml(summarizePanelDataSource(panel))}</div>
    <div class="dashboard-preview-body"></div>
  `;
  const body = mount.querySelector(".dashboard-preview-body");
  if (panel.type === "timeseries") {
    body.innerHTML = '<div class="dashboard-chart-wrap preview-chart-wrap"><canvas id="builder-preview-chart"></canvas></div>';
    destroyBuilderPreviewChart();
    state.builderPreviewChart = createChart(
      body.querySelector("canvas"),
      panel.data?.response?.series || [],
      panel.settings.chart_mode || "raw",
      panel.settings.chart_type || "line",
      panel.settings.aggregation || "avg",
    );
    return;
  }
  if (panel.type === "kpi") {
    body.innerHTML = renderKpiPanelContent(panel.data?.profile, panel.data?.response, panel.settings.label);
    return;
  }
  if (panel.type === "tag_profile") {
    body.innerHTML = renderTagProfilePanelContent(panel.data?.profile || null);
    return;
  }
  if (panel.type === "relationship_results") {
    body.innerHTML = renderRelationshipPanelContent(panel.data?.response || null);
  }
}

async function previewBuilderPanel() {
  clearError();
  try {
    const panel = buildPanelFromBuilder();
    await hydratePanelData(panel);
    renderPreviewPanel(panel);
    setText("builder-edit-status", `Preview ready for ${panel.title}.`);
    showToast("Preview loaded.", "success");
  } catch (error) {
    destroyBuilderPreviewChart();
    document.getElementById("dashboard-builder-preview").innerHTML = createEmptyState(
      "Preview failed",
      error.message,
    );
    showError(error.message);
  }
}

function clearBuilderPreview() {
  destroyBuilderPreviewChart();
  const mount = document.getElementById("dashboard-builder-preview");
  mount.classList.add("empty-state");
  mount.innerHTML = "Select a panel type, machine, and tags, then click Preview.";
}

function defaultPanelLayout(index) {
  return { x: 0, y: index * 4, w: 12, h: 4 };
}

function getNextPanelLayout() {
  const panels = (state.currentDashboard?.panels || []).slice();
  if (!panels.length) {
    return defaultPanelLayout(0);
  }
  const nextY = Math.max(...panels.map((panel) => (panel.layout?.y || 0) + (panel.layout?.h || 4)));
  return { x: 0, y: nextY, w: 12, h: 4 };
}

function normalizeDashboardPayload(payload) {
  const dashboard = payload || {};
  const panels = (dashboard.panels || []).map((panel, index) => ({
    id: panel.id || generatePanelId(),
    type: panel.type,
    title: panel.title || panel.type || "Panel",
    layout: panel.layout || defaultPanelLayout(index),
    refresh: {
      mode: panel.refresh?.mode || "manual",
      last_refreshed_utc: panel.refresh?.last_refreshed_utc || null,
    },
    settings: panel.settings || {},
    series: panel.series || [],
    data: panel.data || {},
  }));
  panels.sort((a, b) => (a.layout.y - b.layout.y) || (a.layout.x - b.layout.x));
  return {
    id: dashboard.id || null,
    name: dashboard.name || "",
    description: dashboard.description || "",
    created_at_utc: dashboard.created_at_utc || null,
    updated_at_utc: dashboard.updated_at_utc || null,
    workspace: dashboard.workspace || {},
    panels,
  };
}

function createBlankDashboard() {
  return normalizeDashboardPayload({ id: null, name: "", description: "", workspace: {}, panels: [] });
}

function syncDashboardInputs() {
  document.getElementById("dashboard-name").value = state.currentDashboard?.name || "";
  document.getElementById("dashboard-description").value = state.currentDashboard?.description || "";
}

function syncBuilderDefaultsFromExplore() {
  document.getElementById("builder-start-utc").value = document.getElementById("start-utc").value;
  document.getElementById("builder-end-utc").value = document.getElementById("end-utc").value;
  document.getElementById("builder-bucket-seconds").value = document.getElementById("bucket-seconds").value;
  document.getElementById("builder-aggregation").value = document.getElementById("chart-aggregation").value;
  document.getElementById("builder-chart-mode").value = document.getElementById("chart-mode").value;
  if (state.selectedMachineId) {
    document.getElementById("builder-machine-select").value = String(state.selectedMachineId);
  }
}

function syncDashboardBuilderEditingState() {
  document.getElementById("builder-update-panel-btn").classList.toggle("hidden", !state.builderEditingPanelId);
  document.getElementById("builder-cancel-edit-btn").classList.toggle("hidden", !state.builderEditingPanelId);
  document.getElementById("builder-add-panel-btn").classList.toggle("hidden", !!state.builderEditingPanelId);
  setText(
    "builder-edit-status",
    state.builderEditingPanelId
      ? `Editing panel ${state.builderEditingPanelId}. Update it or cancel edit.`
      : "Create a panel from the builder on the left.",
  );
}

function resetDashboardBuilderForm() {
  state.builderEditingPanelId = null;
  state.builderSelectedTagIds = new Set();
  document.getElementById("builder-panel-type").value = "line_trend";
  document.getElementById("builder-panel-title").value = "";
  document.getElementById("builder-panel-width").value = "6";
  document.getElementById("builder-panel-height").value = "4";
  document.getElementById("builder-use-scored-profiles").checked = true;
  document.getElementById("builder-tag-search").value = "";
  syncBuilderDefaultsFromExplore();
  renderDashboardBuilderTagList();
  renderDashboardBuilderSelectedTags();
  clearBuilderPreview();
  syncDashboardBuilderEditingState();
}

function buildDashboardPayload() {
  const current = state.currentDashboard || createBlankDashboard();
  return {
    id: current.id || null,
    name: document.getElementById("dashboard-name").value.trim(),
    description: document.getElementById("dashboard-description").value.trim(),
    created_at_utc: current.created_at_utc || null,
    updated_at_utc: current.updated_at_utc || null,
    workspace: {
      machine_id: state.selectedMachineId,
      start_utc: document.getElementById("start-utc").value.trim(),
      end_utc: document.getElementById("end-utc").value.trim(),
      bucket_seconds: Number(document.getElementById("bucket-seconds").value),
    },
    panels: current.panels || [],
  };
}

async function loadDashboards() {
  await withLoading("dashboards", async () => {
    try {
      const response = await apiGet("/api/dashboards");
      state.dashboards = response.dashboards || [];
      const select = document.getElementById("dashboard-select");
      select.innerHTML = '<option value="">No dashboard selected</option>';
      for (const dashboard of state.dashboards) {
        const option = document.createElement("option");
        option.value = dashboard.id;
        option.textContent = `${dashboard.name} (${dashboard.panel_count})`;
        if (state.currentDashboard?.id === dashboard.id) {
          option.selected = true;
        }
        select.appendChild(option);
      }
      setGlobalStatus(`Loaded ${state.dashboards.length} dashboard definition(s).`, "info");
    } catch (error) {
      showError(`Failed to load dashboards: ${error.message}`);
    }
  }, "Loading...");
}

async function loadDashboardById(dashboardId) {
  if (!dashboardId) {
    state.currentDashboard = createBlankDashboard();
    syncDashboardInputs();
    renderDashboardGrid();
    markDashboardDirty(false);
    setDashboardStatus("No dashboard selected.");
    updateWorkflowSteps();
    return;
  }
  try {
    const payload = await apiGet(`/api/dashboards/${dashboardId}`);
    state.currentDashboard = normalizeDashboardPayload(payload);
    syncDashboardInputs();
    renderDashboardGrid();
    markDashboardDirty(false);
    setDashboardStatus(`Loaded dashboard ${payload.name}.`);
    updateWorkflowSteps();
  } catch (error) {
    showError(`Failed to load dashboard: ${error.message}`);
  }
}

async function saveCurrentDashboard() {
  try {
    const payload = buildDashboardPayload();
    if (!payload.name) {
      showError("Dashboard name is required before saving.");
      return;
    }
    disableButton("save-dashboard-btn", true);
    await withLoading("saveDashboard", async () => {
      const saved = await apiPost("/api/dashboards", payload);
      state.currentDashboard = normalizeDashboardPayload(saved);
      syncDashboardInputs();
      await loadDashboards();
      document.getElementById("dashboard-select").value = saved.id;
      renderDashboardGrid();
      markDashboardDirty(false);
      setDashboardStatus(`Saved dashboard ${saved.name}.`);
      showToast("Dashboard saved.", "success");
      setGlobalStatus(`Dashboard ${saved.name} saved.`, "success");
      updateWorkflowSteps();
    }, "Saving...");
  } catch (error) {
    showError(`Failed to save dashboard: ${error.message}`);
  } finally {
    disableButton("save-dashboard-btn", false);
  }
}

async function deleteCurrentDashboard() {
  if (!state.currentDashboard?.id) {
    showError("Select a saved dashboard before deleting.");
    return;
  }
  try {
    disableButton("delete-dashboard-btn", true);
    const response = await apiDelete(`/api/dashboards/${state.currentDashboard.id}`);
    if (response.deleted) {
      state.currentDashboard = createBlankDashboard();
      syncDashboardInputs();
      renderDashboardGrid();
      await loadDashboards();
      markDashboardDirty(false);
      setDashboardStatus("Dashboard deleted.");
      showToast("Dashboard deleted.", "warning");
      setGlobalStatus("Dashboard deleted.", "warning");
      updateWorkflowSteps();
    }
  } catch (error) {
    showError(`Failed to delete dashboard: ${error.message}`);
  } finally {
    disableButton("delete-dashboard-btn", false);
  }
}

function ensureCurrentDashboard() {
  if (!state.currentDashboard) {
    state.currentDashboard = createBlankDashboard();
  }
  return state.currentDashboard;
}

function addPanelToDashboard(panel) {
  const dashboard = ensureCurrentDashboard();
  dashboard.panels.push({
    ...panel,
    id: panel.id || generatePanelId(),
    layout: panel.layout || getNextPanelLayout(),
    refresh: panel.refresh || { mode: "manual", last_refreshed_utc: null },
  });
  dashboard.panels.sort((a, b) => (a.layout.y - b.layout.y) || (a.layout.x - b.layout.x));
  renderDashboardGrid();
  markDashboardDirty(true);
  setGlobalStatus("Dashboard changed. Save to persist panel updates.", "warning");
  updateWorkflowSteps();
}

async function addBuilderPanelToDashboard() {
  clearError();
  try {
    const panel = buildPanelFromBuilder();
    await hydratePanelData(panel);
    addPanelToDashboard(panel);
    renderPreviewPanel(panel);
    setDashboardStatus(`Added panel ${panel.title}. Save the dashboard to persist it.`);
    showToast("Dashboard panel added.", "success");
    resetDashboardBuilderForm();
  } catch (error) {
    showError(error.message);
  }
}

function editPanelInBuilder(panelId) {
  const panel = ensureCurrentDashboard().panels.find((item) => item.id === panelId);
  if (!panel) {
    return;
  }
  state.builderEditingPanelId = panel.id;
  document.getElementById("builder-panel-title").value = panel.title || "";
  document.getElementById("builder-panel-width").value = String(panel.layout?.w || 6);
  document.getElementById("builder-panel-height").value = String(panel.layout?.h || 4);
  if (panel.type === "timeseries") {
    document.getElementById("builder-panel-type").value = panel.settings?.chart_type === "bar" ? "bar_chart" : "line_trend";
    document.getElementById("builder-machine-select").value = String(panel.series?.[0]?.machine_id || "");
    document.getElementById("builder-start-utc").value = panel.settings?.start_utc || "";
    document.getElementById("builder-end-utc").value = panel.settings?.end_utc || "";
    document.getElementById("builder-bucket-seconds").value = panel.settings?.bucket_seconds || 60;
    document.getElementById("builder-aggregation").value = panel.settings?.aggregation || "avg";
    document.getElementById("builder-chart-mode").value = panel.settings?.chart_mode || "raw";
    state.builderSelectedTagIds = new Set((panel.series || []).map((seriesItem) => seriesItem.tag_id));
  } else if (panel.type === "kpi" || panel.type === "tag_profile") {
    document.getElementById("builder-panel-type").value = panel.type;
    document.getElementById("builder-machine-select").value = String(panel.settings?.machine_id || "");
    document.getElementById("builder-start-utc").value = panel.settings?.start_utc || "";
    document.getElementById("builder-end-utc").value = panel.settings?.end_utc || "";
    document.getElementById("builder-bucket-seconds").value = panel.settings?.bucket_seconds || 60;
    document.getElementById("builder-aggregation").value = panel.settings?.aggregation || "avg";
    state.builderSelectedTagIds = new Set([panel.settings?.tag_id]);
  } else if (panel.type === "relationship_results") {
    document.getElementById("builder-panel-type").value = "relationship_results";
    const request = panel.settings?.request || {};
    document.getElementById("builder-machine-select").value = String(request?.target?.machine_id || "");
    document.getElementById("builder-start-utc").value = request.start_utc || "";
    document.getElementById("builder-end-utc").value = request.end_utc || "";
    document.getElementById("builder-bucket-seconds").value = request.bucket_seconds || 60;
    state.builderSelectedTagIds = new Set([request?.target?.tag_id]);
  }
  renderDashboardBuilderTagList();
  renderDashboardBuilderSelectedTags();
  syncDashboardBuilderEditingState();
  showToast(`Editing panel: ${panel.title}`, "info");
}

async function updatePanelFromBuilder() {
  if (!state.builderEditingPanelId) {
    return;
  }
  try {
    const nextPanel = buildPanelFromBuilder();
    await hydratePanelData(nextPanel);
    const dashboard = ensureCurrentDashboard();
    const index = dashboard.panels.findIndex((panel) => panel.id === state.builderEditingPanelId);
    if (index < 0) {
      throw new Error("Selected dashboard panel was not found.");
    }
    nextPanel.layout.y = dashboard.panels[index].layout?.y || nextPanel.layout.y;
    nextPanel.layout.x = dashboard.panels[index].layout?.x || nextPanel.layout.x;
    nextPanel.refresh.last_refreshed_utc = new Date().toISOString();
    dashboard.panels[index] = nextPanel;
    renderDashboardGrid();
    markDashboardDirty(true);
    showToast("Panel updated.", "success");
    setDashboardStatus(`Updated panel ${nextPanel.title}. Save the dashboard to persist it.`);
    resetDashboardBuilderForm();
  } catch (error) {
    showError(error.message);
  }
}

function cancelPanelEdit() {
  resetDashboardBuilderForm();
  showToast("Panel edit canceled.", "info");
}

function addCurrentChartPanel() {
  if (!state.lastTimeseriesRequest || !state.lastTimeseriesResponse) {
    showError("Plot a chart first, then add it as a dashboard panel.");
    return;
  }
  addPanelToDashboard({
    type: "timeseries",
    title: `Trend: ${state.targetTag?.display_name || state.targetTag?.opc_path || "Series"}`,
    settings: {
      aggregation: document.getElementById("chart-aggregation").value,
      chart_mode: document.getElementById("chart-mode").value,
      start_utc: state.lastTimeseriesRequest.start_utc,
      end_utc: state.lastTimeseriesRequest.end_utc,
      bucket_seconds: state.lastTimeseriesRequest.bucket_seconds,
    },
    series: state.lastTimeseriesRequest.series,
    data: { response: state.lastTimeseriesResponse },
  });
  setDashboardStatus("Added current chart as a panel. Save the dashboard to persist it.");
  showToast("Chart panel added to dashboard.", "success");
  updateWorkflowSteps();
}

function addRelationshipResultsPanel() {
  if (!state.lastAnalysisResponse || !state.targetTag) {
    showError("Run relationship analysis first, then add it as a panel.");
    return;
  }
  addPanelToDashboard({
    type: "relationship_results",
    title: `Relationships: ${state.targetTag.display_name || state.targetTag.opc_path}`,
    settings: { request: getAnalysisPayload() },
    series: [],
    data: { response: state.lastAnalysisResponse },
  });
  setDashboardStatus("Added relationship results panel. Save the dashboard to persist it.");
  showToast("Relationship panel added to dashboard.", "success");
  updateWorkflowSteps();
}

async function addTargetProfilePanel() {
  if (!state.targetTag || !state.selectedMachineId) {
    showError("Select a target tag before adding a profile panel.");
    return;
  }
  try {
    const params = new URLSearchParams({
      start_utc: document.getElementById("start-utc").value.trim(),
      end_utc: document.getElementById("end-utc").value.trim(),
    });
    const profile = await apiGet(
      `/api/machines/${state.selectedMachineId}/tags/${state.targetTag.tag_id}/profile?${params.toString()}`
    );
    addPanelToDashboard({
      type: "tag_profile",
      title: `Profile: ${state.targetTag.display_name || state.targetTag.opc_path}`,
      settings: {
        machine_id: Number(state.selectedMachineId),
        tag_id: state.targetTag.tag_id,
        start_utc: document.getElementById("start-utc").value.trim(),
        end_utc: document.getElementById("end-utc").value.trim(),
      },
      series: [],
      data: { profile },
    });
    setDashboardStatus("Added tag profile panel. Save the dashboard to persist it.");
    showToast("Profile panel added to dashboard.", "success");
    updateWorkflowSteps();
  } catch (error) {
    showError(`Failed to load tag profile: ${error.message}`);
  }
}

function destroyPanelChart(panelId) {
  if (state.panelCharts[panelId]) {
    state.panelCharts[panelId].destroy();
    delete state.panelCharts[panelId];
  }
}

function removeDashboardPanel(panelId) {
  const dashboard = ensureCurrentDashboard();
  dashboard.panels = dashboard.panels.filter((panel) => panel.id !== panelId);
  destroyPanelChart(panelId);
  renderDashboardGrid();
  markDashboardDirty(true);
  setDashboardStatus("Panel removed. Save the dashboard to persist the change.");
  showToast("Panel removed.", "warning");
  updateWorkflowSteps();
}

function updatePanelTitle(panelId) {
  const panel = ensureCurrentDashboard().panels.find((item) => item.id === panelId);
  if (!panel) {
    return;
  }
  const nextTitle = window.prompt("Panel title", panel.title);
  if (!nextTitle) {
    return;
  }
  panel.title = nextTitle.trim();
  renderDashboardGrid();
  markDashboardDirty(true);
}

function updatePanelLayout(panelId, changes) {
  const panel = ensureCurrentDashboard().panels.find((item) => item.id === panelId);
  if (!panel) {
    return;
  }
  const nextLayout = { ...panel.layout, ...changes };
  nextLayout.x = Math.max(0, Math.min(11, nextLayout.x));
  nextLayout.w = Math.max(1, Math.min(12, nextLayout.w));
  nextLayout.h = Math.max(2, nextLayout.h);
  if (nextLayout.x + nextLayout.w > 12) {
    nextLayout.x = Math.max(0, 12 - nextLayout.w);
  }
  nextLayout.y = Math.max(0, nextLayout.y);
  panel.layout = nextLayout;
  ensureCurrentDashboard().panels.sort((a, b) => (a.layout.y - b.layout.y) || (a.layout.x - b.layout.x));
  renderDashboardGrid();
  markDashboardDirty(true);
}

function renderRelationshipPanelContent(response) {
  const topResults = (response?.results || []).slice(0, 10);
  return `
    <div class="dashboard-meta">
      Target: ${response?.target?.display_name || response?.target?.opc_path || "-"} |
      Analyzed: ${response?.analysis?.candidate_count_analyzed ?? "-"} |
      Warnings: ${(response?.analysis?.warnings || []).length}
    </div>
    <div class="table-wrap panel-scroll">
      <table class="compact-results-table">
        <thead>
          <tr>
            <th>Relationship</th>
            <th>Score</th>
            <th>Lag</th>
            <th>Pairs</th>
            <th>Display Name</th>
          </tr>
        </thead>
        <tbody>
          ${
            topResults.length
              ? topResults
                  .map(
                    (result) => `
              <tr>
                <td>${result.relationship_type || "-"}</td>
                <td>${formatNumber(result.score)}</td>
                <td>${result.best_lag_seconds ?? "-"}</td>
                <td>${result.pair_count ?? "-"}</td>
                <td>${result.display_name || result.label || "-"}</td>
              </tr>`,
                  )
                  .join("")
              : '<tr><td colspan="5" class="empty-cell">No results stored.</td></tr>'
          }
        </tbody>
      </table>
    </div>
  `;
}

function renderTagProfilePanelContent(profile) {
  const usefulness = profile?.usefulness_score || null;
  return `
    ${
      usefulness
        ? `<div class="tag-score-row">
            ${createBadge(`${usefulness.score}/100`, "semantic")}
            ${createBadge(usefulness.grade, usefulness.grade)}
            ${createBadge(usefulness.semantic_type, "semantic")}
          </div>`
        : ""
    }
    <div class="profile-grid">
      <div><strong>Sample Count</strong><div>${profile?.sample_count ?? "-"}</div></div>
      <div><strong>Numeric Samples</strong><div>${profile?.numeric_sample_count ?? "-"}</div></div>
      <div><strong>First Seen</strong><div>${formatTimestamp(profile?.first_seen_utc)}</div></div>
      <div><strong>Last Seen</strong><div>${formatTimestamp(profile?.last_seen_utc)}</div></div>
      <div><strong>Min Value</strong><div>${formatNumber(profile?.min_value)}</div></div>
      <div><strong>Max Value</strong><div>${formatNumber(profile?.max_value)}</div></div>
      <div><strong>Avg Value</strong><div>${formatNumber(profile?.avg_value)}</div></div>
      <div><strong>Std Dev</strong><div>${formatNumber(profile?.stddev_value)}</div></div>
    </div>
    ${
      usefulness?.reasons?.length
        ? `<div class="dashboard-meta">${escapeHtml(usefulness.reasons.join(" | "))}</div>`
        : ""
    }
  `;
}

function renderKpiPanelContent(profile, response, label) {
  const entry = response?.series?.[0] || null;
  const lastPoint = entry?.points?.length ? entry.points[entry.points.length - 1] : null;
  return `
    <div class="kpi-panel-body">
      <div class="kpi-title">${escapeHtml(label || profile?.display_name || entry?.label || "KPI")}</div>
      <div class="kpi-value">${lastPoint ? formatNumber(lastPoint.v, 2) : "-"}</div>
      <div class="profile-grid">
        <div><strong>Min</strong><div>${formatNumber(profile?.min_value)}</div></div>
        <div><strong>Max</strong><div>${formatNumber(profile?.max_value)}</div></div>
        <div><strong>Average</strong><div>${formatNumber(profile?.avg_value)}</div></div>
        <div><strong>Sample Count</strong><div>${profile?.sample_count ?? "-"}</div></div>
        <div><strong>Last Seen</strong><div>${formatTimestamp(profile?.last_seen_utc)}</div></div>
        <div><strong>Latest Bucket</strong><div>${formatTimestamp(lastPoint?.t)}</div></div>
      </div>
    </div>
  `;
}

async function renderTimeseriesPanel(panel, mount) {
  const body = mount.querySelector(".dashboard-panel-body");
  body.innerHTML = `
    <div class="dashboard-meta">
      Aggregation: ${panel.settings.aggregation || "avg"} |
      Mode: ${panel.settings.chart_mode || "raw"} |
      Last Refreshed: ${formatTimestamp(panel.refresh.last_refreshed_utc)}
    </div>
    <div class="dashboard-chart-wrap">
      <canvas id="panel-chart-${panel.id}"></canvas>
    </div>
  `;
  const response = panel.data?.response || null;
  if (!response) {
    body.innerHTML += '<div class="dashboard-refresh-note">No stored chart payload yet. Use Refresh.</div>';
    return;
  }
  destroyPanelChart(panel.id);
  state.panelCharts[panel.id] = createChart(
    body.querySelector("canvas"),
    response.series || [],
    panel.settings.chart_mode || "raw",
  );
}

function renderRelationshipPanel(panel, mount) {
  const body = mount.querySelector(".dashboard-panel-body");
  const response = panel.data?.response || null;
  if (!response) {
    body.innerHTML = '<div class="empty-state">No relationship data stored yet.</div>';
    return;
  }
  body.innerHTML = renderRelationshipPanelContent(response);
}

function renderTagProfilePanel(panel, mount) {
  const body = mount.querySelector(".dashboard-panel-body");
  const profile = panel.data?.profile || null;
  if (!profile) {
    body.innerHTML = '<div class="empty-state">No profile data stored yet.</div>';
    return;
  }
  body.innerHTML = renderTagProfilePanelContent(profile);
}

function renderKpiPanel(panel, mount) {
  const body = mount.querySelector(".dashboard-panel-body");
  body.innerHTML = renderKpiPanelContent(
    panel.data?.profile || null,
    panel.data?.response || null,
    panel.settings?.label || panel.title,
  );
}

async function refreshPanel(panelId) {
  const panel = ensureCurrentDashboard().panels.find((item) => item.id === panelId);
  if (!panel) {
    return;
  }
  try {
    panel.data.error = null;
    if (panel.type === "timeseries") {
      panel.data.response = await apiPost(
        "/api/timeseries/query",
        buildChartPayload(panel.series, {
          start_utc: panel.settings.start_utc,
          end_utc: panel.settings.end_utc,
          bucket_seconds: panel.settings.bucket_seconds,
          aggregation: panel.settings.aggregation,
        }),
      );
    } else if (panel.type === "relationship_results") {
      panel.data.response = await apiPost("/api/analysis/relationships", panel.settings.request);
    } else if (panel.type === "tag_profile") {
      const params = new URLSearchParams();
      if (panel.settings.start_utc) {
        params.set("start_utc", panel.settings.start_utc);
      }
      if (panel.settings.end_utc) {
        params.set("end_utc", panel.settings.end_utc);
      }
      panel.data.profile = await apiGet(
        `/api/machines/${panel.settings.machine_id}/tags/${panel.settings.tag_id}/profile?${params.toString()}`
      );
    }
    panel.refresh.last_refreshed_utc = new Date().toISOString();
    renderDashboardGrid();
    markDashboardDirty(true);
    setDashboardStatus(`Refreshed panel ${panel.title}.`);
    showToast(`Panel refreshed: ${panel.title}`, "success");
    updateWorkflowSteps();
  } catch (error) {
    panel.data.error = error.message;
    renderDashboardGrid();
    showError(`Failed to refresh panel: ${error.message}`);
    showToast(`Panel refresh failed: ${panel.title}`, "danger");
  }
}

async function refreshAllPanels() {
  const panels = ensureCurrentDashboard().panels || [];
  if (!panels.length) {
    showError("No dashboard panels to refresh.");
    return;
  }
  disableButton("refresh-all-panels-btn", true);
  document.getElementById("refresh-all-status").textContent = "Refreshing panels...";
  try {
    for (let index = 0; index < panels.length; index += 1) {
      document.getElementById("refresh-all-status").textContent = `Refreshing panel ${index + 1} of ${panels.length}...`;
      await refreshPanel(panels[index].id);
    }
    document.getElementById("refresh-all-status").textContent = `Refreshed ${panels.length} panel(s).`;
    showToast(`Refreshed ${panels.length} panel(s).`, "success");
    updateWorkflowSteps();
  } finally {
    disableButton("refresh-all-panels-btn", false);
  }
}

async function renderDashboardPanel(panel, mount) {
  mount.style.gridColumn = `${panel.layout.x + 1} / span ${panel.layout.w}`;
  mount.style.gridRow = `${panel.layout.y + 1} / span ${panel.layout.h}`;
  mount.style.minHeight = `${panel.layout.h * 96}px`;
  mount.innerHTML = `
    <div class="dashboard-panel-head">
      <div class="dashboard-panel-title">
        <h2>${panel.title}</h2>
        <span class="type-badge ${panel.type}">${panel.type}</span>
      </div>
      <div class="dashboard-panel-actions">
        <button class="mini-btn" data-panel-refresh="${panel.id}">Refresh</button>
        <button class="mini-btn" data-panel-title="${panel.id}">Edit Title</button>
        <button class="mini-btn danger-tone" data-panel-remove="${panel.id}">Remove</button>
      </div>
    </div>
    <div class="dashboard-layout-row">
      <div class="dashboard-panel-controls">
        <button class="mini-btn" data-panel-left="${panel.id}">←</button>
        <button class="mini-btn" data-panel-right="${panel.id}">→</button>
        <button class="mini-btn" data-panel-up="${panel.id}">↑</button>
        <button class="mini-btn" data-panel-down="${panel.id}">↓</button>
        <label class="field">
          <span>Width</span>
          <select data-panel-width="${panel.id}">
            ${PANEL_WIDTH_OPTIONS.map((value) => `<option value="${value}" ${value === panel.layout.w ? "selected" : ""}>${value}</option>`).join("")}
          </select>
        </label>
        <label class="field">
          <span>Height</span>
          <select data-panel-height="${panel.id}">
            ${PANEL_HEIGHT_OPTIONS.map((value) => `<option value="${value}" ${value === panel.layout.h ? "selected" : ""}>${value}</option>`).join("")}
          </select>
        </label>
      </div>
      <div class="layout-readout">x=${panel.layout.x} y=${panel.layout.y} w=${panel.layout.w} h=${panel.layout.h}</div>
    </div>
    <div class="dashboard-refresh-note">Refresh mode: ${panel.refresh.mode} | Last refreshed: ${formatTimestamp(panel.refresh.last_refreshed_utc)}</div>
    ${panel.data?.error ? `<div class="error-box"><div><strong>Panel refresh failed</strong><div>${escapeHtml(panel.data.error)}</div></div></div>` : ""}
    <div class="dashboard-panel-body"></div>
  `;

  mount.querySelector(`[data-panel-refresh="${panel.id}"]`).addEventListener("click", () => refreshPanel(panel.id));
  mount.querySelector(`[data-panel-title="${panel.id}"]`).addEventListener("click", () => updatePanelTitle(panel.id));
  mount.querySelector(`[data-panel-remove="${panel.id}"]`).addEventListener("click", () => removeDashboardPanel(panel.id));
  mount.querySelector(`[data-panel-left="${panel.id}"]`).addEventListener("click", () => updatePanelLayout(panel.id, { x: panel.layout.x - 1 }));
  mount.querySelector(`[data-panel-right="${panel.id}"]`).addEventListener("click", () => updatePanelLayout(panel.id, { x: panel.layout.x + 1 }));
  mount.querySelector(`[data-panel-up="${panel.id}"]`).addEventListener("click", () => updatePanelLayout(panel.id, { y: panel.layout.y - 1 }));
  mount.querySelector(`[data-panel-down="${panel.id}"]`).addEventListener("click", () => updatePanelLayout(panel.id, { y: panel.layout.y + 1 }));
  mount.querySelector(`[data-panel-width="${panel.id}"]`).addEventListener("change", (event) => {
    updatePanelLayout(panel.id, { w: Number(event.target.value) });
  });
  mount.querySelector(`[data-panel-height="${panel.id}"]`).addEventListener("change", (event) => {
    updatePanelLayout(panel.id, { h: Number(event.target.value) });
  });

  if (panel.type === "timeseries") {
    await renderTimeseriesPanel(panel, mount);
  } else if (panel.type === "relationship_results") {
    renderRelationshipPanel(panel, mount);
  } else if (panel.type === "tag_profile") {
    renderTagProfilePanel(panel, mount);
  }
}

async function renderDashboardGrid() {
  const grid = document.getElementById("dashboard-panel-grid");
  const empty = document.getElementById("dashboard-empty");
  grid.innerHTML = "";
  if (!state.currentDashboard || !(state.currentDashboard.panels || []).length) {
    empty.classList.remove("hidden");
    empty.textContent = state.currentDashboard?.name
      ? "This dashboard has no panels yet. Add panels from Explore, then save."
      : "Create or load a dashboard, then add panels from Explore.";
    return;
  }
  empty.classList.add("hidden");
  const panels = [...state.currentDashboard.panels].sort((a, b) => (a.layout.y - b.layout.y) || (a.layout.x - b.layout.x));
  for (const panel of panels) {
    const wrapper = document.createElement("section");
    wrapper.className = "panel dashboard-panel";
    grid.appendChild(wrapper);
    try {
      await renderDashboardPanel(panel, wrapper);
    } catch (error) {
      wrapper.innerHTML = `<div class="empty-state">Failed to render panel: ${error.message}</div>`;
    }
  }
}

function resetWorkspace() {
  clearWorkspace();
  state.selectedMachineId = null;
  state.tags = [];
  state.filteredTags = [];
  state.folderCollapsed = {};
  state.activeTagFilter = "all_numeric";
  state.targetTag = null;
  state.lastAnalysisResponse = null;
  state.analysisResults = [];
  state.selectedResultTagIds = new Set();
  state.activeRelationshipFilter = "all";
  state.resultSort = "score_desc";
  state.lastTimeseriesRequest = null;
  state.lastTimeseriesResponse = null;
  document.getElementById("machine-select").value = "";
  document.getElementById("tag-search").value = "";
  document.getElementById("numeric-only").checked = true;
  document.getElementById("use-scored-profiles").checked = false;
  document.getElementById("bucket-seconds").value = 60;
  document.getElementById("candidate-scope").value = "same_machine";
  document.getElementById("max-candidate-tags").value = 300;
  document.getElementById("max-results").value = 25;
  document.getElementById("min-pair-count").value = 30;
  document.getElementById("max-lag-seconds").value = 1800;
  document.getElementById("chart-mode").value = "raw";
  document.getElementById("chart-aggregation").value = "avg";
  document.getElementById("results-sort").value = "score_desc";
  document.getElementById("tag-sort").value = "score_desc";
  state.useScoredProfiles = false;
  state.tagSort = "score_desc";
  setDefaultUtcRange();
  renderTargetTag();
  renderTagList();
  renderAnalysisSummary(null);
  renderRelationshipResults();
  renderSelectedSeriesList();
  clearChart();
  applyFilterButtonState("tag-filter-row", state.activeTagFilter, "data-tag-filter");
  applyFilterButtonState("relationship-filter-row", state.activeRelationshipFilter, "data-relationship-filter");
  updateActiveMachineLabel();
  updateChartPlaceholder();
  updateWorkflowSteps();
  showToast("Workspace reset.", "info");
  setGlobalStatus("Workspace reset.", "info");
}

function bindControlPersistence() {
  const ids = [
    "tag-search",
    "numeric-only",
    "use-scored-profiles",
    "start-utc",
    "end-utc",
    "bucket-seconds",
    "candidate-scope",
    "max-candidate-tags",
    "max-results",
    "min-pair-count",
    "max-lag-seconds",
    "chart-mode",
    "chart-aggregation",
    "results-sort",
    "tag-sort",
  ];
  for (const id of ids) {
    const element = document.getElementById(id);
    const eventName = element.tagName === "SELECT" || element.type === "checkbox" ? "change" : "input";
    element.addEventListener(eventName, persistWorkspace);
  }
}

function bindEvents() {
  document.getElementById("machine-select").addEventListener("change", async (event) => {
    state.selectedMachineId = event.target.value ? Number(event.target.value) : null;
    state.targetTag = null;
    state.analysisResults = [];
    state.lastAnalysisResponse = null;
    state.selectedResultTagIds = new Set();
    state.lastTimeseriesRequest = null;
    state.lastTimeseriesResponse = null;
    renderTargetTag();
    renderAnalysisSummary(null);
    renderRelationshipResults();
    renderSelectedSeriesList();
    clearChart();
    persistWorkspace();
    updateActiveMachineLabel();
    updateChartPlaceholder();
    updateWorkflowSteps();
    await loadTags();
  });

  document.getElementById("refresh-tags-btn").addEventListener("click", loadTags);
  document.getElementById("tag-search").addEventListener("input", () => {
    renderTagList();
    persistWorkspace();
  });
  document.getElementById("tag-search").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      renderTagList();
    }
  });
  document.getElementById("numeric-only").addEventListener("change", async () => {
    persistWorkspace();
    await loadTags();
  });
  document.getElementById("use-scored-profiles").addEventListener("change", async (event) => {
    state.useScoredProfiles = event.target.checked;
    persistWorkspace();
    await loadTags();
  });
  document.getElementById("tag-sort").addEventListener("change", (event) => {
    state.tagSort = event.target.value;
    renderTagList();
    persistWorkspace();
  });
  document.getElementById("run-analysis-btn").addEventListener("click", runRelationshipAnalysis);
  document.getElementById("plot-selected-btn").addEventListener("click", plotSelectedSeries);
  document.getElementById("clear-chart-btn").addEventListener("click", clearChart);
  document.getElementById("dismiss-error-btn").addEventListener("click", () => clearError());
  document.getElementById("reset-workspace-btn").addEventListener("click", async () => {
    resetWorkspace();
    await loadMachines();
  });
  document.getElementById("results-sort").addEventListener("change", (event) => {
    state.resultSort = event.target.value;
    renderRelationshipResults();
    persistWorkspace();
  });
  document.getElementById("select-top-5-btn").addEventListener("click", () => selectTopResults(5));
  document.getElementById("clear-selected-btn").addEventListener("click", clearSelectedResults);
  document.getElementById("tab-explore").addEventListener("click", () => switchTab("explore"));
  document.getElementById("tab-dashboards").addEventListener("click", () => switchTab("dashboards"));
  document.getElementById("go-to-dashboards-btn").addEventListener("click", () => switchTab("dashboards"));
  document.getElementById("new-dashboard-btn").addEventListener("click", () => {
    state.currentDashboard = createBlankDashboard();
    syncDashboardInputs();
    renderDashboardGrid();
    markDashboardDirty(false);
    setDashboardStatus("New unsaved dashboard created.");
    document.getElementById("dashboard-select").value = "";
    updateWorkflowSteps();
  });
  document.getElementById("save-dashboard-btn").addEventListener("click", saveCurrentDashboard);
  document.getElementById("delete-dashboard-btn").addEventListener("click", deleteCurrentDashboard);
  document.getElementById("dashboard-select").addEventListener("change", async (event) => {
    await loadDashboardById(event.target.value);
  });
  document.getElementById("add-chart-panel-btn").addEventListener("click", addCurrentChartPanel);
  document.getElementById("add-relationship-panel-btn").addEventListener("click", addRelationshipResultsPanel);
  document.getElementById("add-profile-panel-btn").addEventListener("click", addTargetProfilePanel);
  document.getElementById("refresh-all-panels-btn").addEventListener("click", refreshAllPanels);
  document.getElementById("dashboard-name").addEventListener("input", () => {
    ensureCurrentDashboard().name = document.getElementById("dashboard-name").value;
    markDashboardDirty(true);
  });
  document.getElementById("dashboard-description").addEventListener("input", () => {
    ensureCurrentDashboard().description = document.getElementById("dashboard-description").value;
    markDashboardDirty(true);
  });

  for (const button of document.querySelectorAll("[data-tag-filter]")) {
    button.addEventListener("click", () => {
      state.activeTagFilter = button.getAttribute("data-tag-filter");
      applyFilterButtonState("tag-filter-row", state.activeTagFilter, "data-tag-filter");
      renderTagList();
      persistWorkspace();
    });
  }
  for (const button of document.querySelectorAll("[data-relationship-filter]")) {
    button.addEventListener("click", () => {
      state.activeRelationshipFilter = button.getAttribute("data-relationship-filter");
      applyFilterButtonState("relationship-filter-row", state.activeRelationshipFilter, "data-relationship-filter");
      renderRelationshipResults();
      persistWorkspace();
    });
  }

  bindControlPersistence();
}

function syncDashboardInputs() {
  document.getElementById("dashboard-name").value = state.currentDashboard?.name || "";
  document.getElementById("dashboard-description").value = state.currentDashboard?.description || "";
}

// ============================================================================
// Init / Bootstrap
// ============================================================================

async function init() {
  const workspace = loadWorkspace();
  restoreWorkspaceControls(workspace);
  state.currentDashboard = createBlankDashboard();
  bindEvents();
  applyFilterButtonState("tag-filter-row", state.activeTagFilter, "data-tag-filter");
  applyFilterButtonState("relationship-filter-row", state.activeRelationshipFilter, "data-relationship-filter");
  document.getElementById("results-sort").value = state.resultSort;
  document.getElementById("tag-sort").value = state.tagSort;
  syncDashboardInputs();
  renderTargetTag();
  renderTagList();
  renderAnalysisSummary(null);
  renderRelationshipResults();
  renderSelectedSeriesList();
  updateActiveMachineLabel();
  updateChartPlaceholder();
  updateWorkflowSteps();
  await renderDashboardGrid();
  await loadHealth();
  await Promise.all([loadMachines(), loadDashboards()]);
  if (state.selectedMachineId) {
    await loadTags();
  }
}

window.addEventListener("DOMContentLoaded", init);
