export const meta = {
  name: 'restack',
  description:
    'Rebase/merge each fork-stack branch onto its updated parent in dependency order, green the targeted tests, and push. Stack comes from dev/stack.toml via args.',
  phases: [{ title: 'Restack', detail: 'one worktree-isolated agent per branch, bottom-up' }],
}

// Workflow scripts have no filesystem access, so the ledger is the single source of truth: the
// caller runs `python dev/stack.py restack-plan` and passes its JSON as `args`. No hand-mirroring.
// args may be the plan array directly, or { stack: [...] }. Each entry: { branch, parent, strategy }.
const STACK = Array.isArray(args) ? args : Array.isArray(args?.stack) ? args.stack : []
if (!STACK.length) {
  throw new Error(
    'restack: no stack provided. Launch with the ledger-derived plan, e.g.\n' +
      '  Workflow({ scriptPath: ".claude/workflows/restack.js", args: <output of `python dev/stack.py restack-plan`> })',
  )
}

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
