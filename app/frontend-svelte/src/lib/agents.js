/** Agent pipeline order and display config. Must match backend agent names/ids. */
export const AGENT_CONFIG = [
  { id: 'orchestrator', name: 'Orchestrator', icon: '🎯' },
  { id: 'parser', name: 'Architecture Parser', icon: '📐' },
  { id: 'modeler', name: 'Threat Modeler', icon: '🛡️' },
  { id: 'builder', name: 'Report Builder', icon: '📄' },
  { id: 'verifier', name: 'Report Verifier', icon: '✅' },
];

export const AGENT_SEQUENCE = AGENT_CONFIG.map((a) => a.id);

const AUTHOR_TO_ID = {
  threat_model_orchestrator: 'orchestrator',
  orchestrator: 'orchestrator',
  architecture_parser: 'parser',
  parser: 'parser',
  threat_modeler: 'modeler',
  modeler: 'modeler',
  report_builder: 'builder',
  builder: 'builder',
  report_verifier: 'verifier',
  verifier: 'verifier',
};

/**
 * @param {string} author - Author string from stream event
 * @returns {string} agent id for status display
 */
export function getAgentIdFromAuthor(author) {
  if (!author) return 'orchestrator';
  const lower = author.toLowerCase();
  for (const [key, id] of Object.entries(AUTHOR_TO_ID)) {
    if (lower.includes(key)) return id;
  }
  return 'orchestrator';
}
