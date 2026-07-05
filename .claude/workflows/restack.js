export const meta = {
  name: 'restack',
  description:
    'Rebase/merge each fork-stack branch onto its updated parent in dependency order, green the targeted tests, and push. Mirrors dev/stack.toml.',
  phases: [{ title: 'Restack', detail: 'one worktree-isolated agent per branch, bottom-up' }],
}

// Workflow scripts have no filesystem access, so the stack is mirrored from dev/stack.toml.
// KEEP IN SYNC with the ledger. Order is bottom-up: a parent is restacked before its children.
const STACK = [
  { branch: 'eql-arithmetic', parent: 'main', strategy: 'merge' },
  { branch: 'eql-verbalization-extensions', parent: 'main', strategy: 'merge' },
  { branch: 'claude/performatives-clean', parent: 'eql-arithmetic', strategy: 'merge' },
  { branch: 'claude/eql-performatives-unify', parent: 'claude/performatives-clean', strategy: 'merge' },
  { branch: 'claude/eql-roboknerd-why-acts', parent: 'main', strategy: 'merge' },
]

const RESULT = {
  type: 'object',
  properties: {
    integrated: { type: 'boolean' },
    testsPassed: { type: 'boolean' },
    pushed: { type: 'boolean' },
    unresolvedConflicts: { type: 'boolean' },
    notes: { type: 'string' },
  },
  required: ['integrated', 'testsPassed', 'pushed', 'unresolvedConflicts', 'notes'],
}

function instructions(step) {
  const integrate =
    step.strategy === 'merge'
      ? `Merge origin/${step.parent} into it (preserve history — the branch is far diverged).`
      : `Rebase it onto origin/${step.parent} (clean linear history).`
  return (
    `Restack one branch of a stacked-PR chain on the 'origin' fork.\n` +
    `1. Fetch origin. Check out origin/${step.branch} as local '${step.branch}'.\n` +
    `2. ${integrate} Resolve conflicts faithfully. If a generated ormatic_interface.py conflicts, do NOT hand-edit it — run scripts/regenerate_all_orm.py.\n` +
    `3. Source ROS: 'source /opt/ros/jazzy/setup.bash && source /opt/ros/overlay_ws/install/setup.bash'. Run ONLY the tests this branch touches with /opt/ros/cram-env/bin/python. Do NOT run the full test suite.\n` +
    `4. Revert any per-run generated artifacts you did not intend to change.\n` +
    `5. If clean and green: ${step.strategy === 'merge' ? 'push' : 'force-push-with-lease'} origin/${step.branch}. ` +
    `If conflicts cannot be resolved safely, STOP without pushing and set unresolvedConflicts=true.\n` +
    `Return the structured result.`
  )
}

phase('Restack')
const results = []
for (const step of STACK) {
  const r = await agent(instructions(step), {
    label: `restack:${step.branch}`,
    phase: 'Restack',
    isolation: 'worktree',
    schema: RESULT,
  })
  results.push({ branch: step.branch, ...(r || { pushed: false, unresolvedConflicts: true, notes: 'agent died' }) })
  if (!r || r.unresolvedConflicts || !r.pushed) {
    log(`Stopping at ${step.branch}: downstream branches depend on its new SHA. Resolve, then re-run — completed branches are cached.`)
    break
  }
  log(`${step.branch}: integrated, tests ${r.testsPassed ? 'green' : 'RED'}, pushed.`)
}
return results
