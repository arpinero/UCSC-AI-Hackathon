/** @type {Record<string, string[][]>} */
export const roleQuestions = {
  containment: [
    ['Explain the scope', 'Explain the containment targets and scope using the recorded evidence. What remains exposed?'],
    ['Check rollback', 'Explain the proposed containment expiry, preserved channels, and rollback. Identify missing safeguards.']
  ],
  forensics: [
    ['Trace the timeline', 'Walk through the forensic timeline with evidence IDs. Separate observations from inferences.'],
    ['Identify gaps', 'What evidence is missing from this investigation, and what should the analyst collect next?']
  ],
  compliance: [
    ['Explain policy gates', 'Explain the recorded compliance findings and policy gates. Which decisions still need human review?'],
    ['Review obligations', 'Which reporting obligations are supported by the supplied policy, and which facts need verification?']
  ],
  fixing: [
    ['Review recovery', 'Explain the recovery proposal, its prerequisites, and how restoration would be verified.'],
    ['Check residual risk', 'What risks remain after the proposed recovery? Cite the recorded evidence and distinguish planned from executed actions.']
  ]
};

/** Local navigation remains available during inference; questions only draft chat. */
export function suggestions({running=false, pending=false, decision=false, escalated=false, view='activity', latestRole=''}) {
  if (decision) return [
    {label:'Review exact plan', action:'plan'},
    {label:'Inspect evidence', action:'evidence'},
    {label:'Cancel decision', action:'cancel'}
  ];
  if (pending) return [
    {label:'Review exact plan', action:'plan'},
    {label:'Inspect evidence', action:'evidence'},
    {label:'Compare agent responses', action:'agents'}
  ];
  const questions = roleQuestions[latestRole] || [['Summarize findings','Summarize the recorded evidence, agent findings, and remaining uncertainty.']];
  return [
    {label:view==='evidence'?'Back to activity':'Inspect evidence', action:view==='evidence'?'activity':'evidence'},
    running ? {label:latestRole?'Explore latest response':'Check model services',action:latestRole?'latest':'models'} :
      {label:escalated?'Review escalation':'View outcomes',action:escalated?'escalation':'metrics'},
    {label:escalated?'What needs review?':questions[0][0], action:'draft', text:escalated?'Explain why this run escalated, the binding policy gates, and the decisions an analyst needs to make.':questions[0][1]}
  ];
}
