<!-- agentloop:managed:begin -->
## Governed self-improvement (agentloop)

This workspace is governed by the Loop standard. Rules for every agent:

1. Do NOT edit loop-managed files directly (AGENTS.md, CLAUDE.md, memory,
   skills, tools, agent config). Policy lists the exact patterns in
   `.loop/policy.yaml`.
2. When you learn a durable lesson, propose it instead:
   `agentloop propose --layer context --target <file> --patch <diff> --rationale "<why>"`
3. Attach evidence (fail -> apply -> pass transcript):
   `agentloop evidence <cs-id> --record <ev.json> --artifact <transcript>`
4. Gate and apply: `agentloop gate <cs-id>` then `agentloop apply <cs-id>`.
   Low-risk context changes auto-apply with independent evidence; capability
   and architecture changes queue for human review.
5. Never touch `.loop/**`. Verify integrity anytime: `agentloop verify .`
<!-- agentloop:managed:end -->
