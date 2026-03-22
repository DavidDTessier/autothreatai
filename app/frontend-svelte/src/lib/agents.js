/** Agent pipeline order and display config. Must match backend agent names/ids. */
export const AGENT_CONFIG = [
  { id: "orchestrator", name: "Orchestrator", icon: "🎯" },
  { id: "parser", name: "Architecture Parser", icon: "📐" },
  { id: "modeler", name: "Standard Threat Modeller", icon: "🛡️" },
  { id: "ai_modeler", name: "MEASTRO Threat Modeller", icon: "🤖" },
  { id: "builder", name: "Report Builder", icon: "📄" },
  { id: "verifier", name: "Report Verifier", icon: "✅" },
];

/** Linear sequence for error propagation (all agents). */
export const AGENT_SEQUENCE = AGENT_CONFIG.map((a) => a.id);

/** Pipeline steps for visual: each step is a string (single agent) or array (branch – one of these runs). */
export const PIPELINE_STEPS = [
  "orchestrator",
  "parser",
  ["modeler", "ai_modeler"], // Architecture Parser routes to one of these
  "builder",
  "verifier",
];

/** After an agent completes, which agent(s) become active next. */
export const NEXT_AGENT_IDS = {
  orchestrator: ["parser"],
  parser: ["modeler", "ai_modeler"],
  modeler: ["builder"],
  ai_modeler: ["builder"],
  builder: ["verifier"],
  verifier: [],
};

const AUTHOR_TO_ID = {
  threat_model_orchestrator: "orchestrator",
  orchestrator: "orchestrator",
  architecture_parser: "parser",
  parser: "parser",
  threat_modeler: "modeler",
  threat_modeler_agent: "modeler",
  modeler: "modeler",
  meastro_threat_modeler: "ai_modeler",
  meastro_threat_modeler_agent: "ai_modeler",
  ai_modeler: "ai_modeler",
  report_builder: "builder",
  builder: "builder",
  report_verifier: "verifier",
  verifier: "verifier",
};

const CONFIG_BY_ID = Object.fromEntries(AGENT_CONFIG.map((a) => [a.id, a]));

/**
 * @param {string} id - Agent id
 * @returns {{ id: string, name: string, icon: string }|undefined}
 */
export function getAgentConfig(id) {
  return CONFIG_BY_ID[id];
}

/**
 * @param {string} author - Author string from stream event
 * @returns {string} agent id for status display
 */
export function getAgentIdFromAuthor(author) {
  if (!author) return "orchestrator";
  const lower = String(author).toLowerCase();
  const entries = Object.entries(AUTHOR_TO_ID).sort(
    (a, b) => b[0].length - a[0].length,
  );
  for (const [key, id] of entries) {
    if (lower.includes(key)) return id;
  }
  return "orchestrator";
}
