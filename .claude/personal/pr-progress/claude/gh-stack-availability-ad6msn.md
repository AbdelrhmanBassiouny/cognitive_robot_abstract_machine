## Plan

User asked about the `gh-stack` skill (GitHub's stacked-PRs CLI tooling,
public preview since 2026-07-30) and wanted Claude sessions in this repo
able to use it. Single-PR task, no multi-session plan needed.

- [x] Vendor github/gh-stack's official `skills/gh-stack/SKILL.md` into
      `.claude/skills/gh-stack/SKILL.md` in this repo, with an added
      environment note clarifying it only works where a local, authenticated
      `gh` CLI + the `gh-stack` extension are installed (a developer's own
      terminal), not in Claude Code Remote sessions like this one, which use
      the `mcp__github__*` tools instead.
- [x] Commit under the user's own git identity (AbdelrhmanBassiouny
      <bido.bassuny@gmail.com>) per AGENTS.md - the environment's default
      git config is `Claude <noreply@anthropic.com>`, which must never be
      used as commit author/committer here.
- [x] Push to `claude/gh-stack-availability-ad6msn`.

## Done

Skill added and pushed (commit 5d51e95a). Confirmed via the session's
available-skills listing that `gh-stack` is now discoverable.

## Next

Nothing pending. No PR opened yet - ask the user if they want one before
creating it (see personal notes: PRs open as drafts by default).
