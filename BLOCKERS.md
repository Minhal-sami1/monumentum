# BLOCKERS.md

## B-001 — process conflict: the `/goal` stop-hook condition presumes a fresh build; the work is at publication (2026-09-05)

**Problem.** The session-scoped stop hook carries the original `/goal`
condition verbatim: "Read GOAL.md and design-doc.md before any other
action … Begin with m1 now." That condition was written for the start of
the build cycle. The build is complete: tags `m1`–`m7` and `m7.1` exist,
every documented gate exits 0 on Windows and on a fresh clone in a clean
Linux container, the dogfood loop verifies, and Minhal's live directive is
the six-step publication procedure, currently halted at STEP 1 awaiting
his name choice.

Both binding documents have now been read in full in this session (GOAL.md
lines 1–155, design-doc.md lines 1–327). The remaining objection is
ordering: STEP 1's collision checks ran before that full read. That is
historical and cannot be undone. The hook's own latest feedback says the
condition "cannot be retroactively satisfied."

Satisfying the hook literally would mean restarting at m1 on a finished,
tagged, externally reviewed v1 — destructive, and contrary to the owner's
current instruction. GOAL rule 2 says a real conflict is a blocker, not a
judgment call.

**Proposal.** Minhal resolves the conflict, as the owner of the process
(GOAL §11):
1. clear or re-issue the `/goal` for the publication phase (STEPS 1–6 as
   given on 2026-09-05), or
2. confirm that the binding documents being read in full counts as
   satisfying rule 7 for this resumed session, and that "begin with m1"
   is superseded by the tagged milestones.

Until then: STEP 1 is complete and reported (all candidates checked —
Ratchet, Lamarck, Cairn, agentloop, provenloop, nacre, varve, stele,
escapement — every one has an active in-domain collision; `cairnspec`
recommended). Nothing is renamed. Nothing is pushed. Waiting for the name.

**What this is not.** Not a gate failure, not a defect in the repository,
not a reason to alter any gate. It will be removed once resolved.
