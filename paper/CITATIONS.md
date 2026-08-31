# Citation verification record

GOAL forbidden move 5: do not fabricate citations. Every reference in
`figures/references.tex` was checked against a live authoritative source on
**2026-08-31**. Nothing required a `[VERIFY]` marker.

## `[VERIFY]` list

**Empty.** All 20 references resolved to a live authoritative source (arXiv,
DOI, RFC Editor, EUR-Lex, or the official project/standards site). No
citation blocks paper submission on verification grounds.

## What was checked, and what the source said

| Key | Source verified | Note |
|---|---|---|
| `dgm` | arXiv:2505.22954 | Eval-gaming finding **confirmed**: the paper documents a variant ("Node 114") scoring perfectly by *removing the harness's hallucination-detection markers*. This is the claim §1 and I3 rest on. Preprint 2025; accepted ICLR 2026. |
| `alphaevolve` | arXiv:2506.13131 | Google DeepMind; large author list (Novikov et al.). |
| `gepa` | arXiv:2507.19457 | Genetic-Pareto reflective prompt optimizer. |
| `dspy` | arXiv:2310.03714 | Presented at ICLR 2024. |
| `minja` | arXiv:2503.03704 | Confirmed as a memory-injection/poisoning attack via query-only interaction. A later revision carries the title "Memory Injection Attacks on LLM Agents via Query-Only Interaction" (NeurIPS 2025); the acronym MINJA and the attack class are both confirmed. |
| `intoto` | USENIX Security 2019, pp. 1393–1410 | — |
| `slsa` | slsa.dev spec v1.2 | v1.0 is the usual anchor; v1.2 is current. |
| `sigstore` | ACM CCS 2022, doi:10.1145/3548606.3560596 | — |
| `inspect` | inspect.aisi.org.uk | Body renamed: UK AI **Security** Institute (formerly AI Safety Institute). |
| `lmeval` | Zenodo doi:10.5281/zenodo.12608602 | DOI is the v0.4.3 release cited in the project README. |
| `otelgenai` | opentelemetry.io GenAI semconv | — |
| `agentsmd` | agents.md | Now stewarded by the Agentic AI Foundation (Linux Foundation). |
| `mcp` | modelcontextprotocol.io/specification | Initial spec 2024-11-05; latest revision 2026-07-28. |
| `a2a` | a2a-protocol.org v1.0.0 | Originated at Google; now governed by the Linux Foundation. |
| `rfc2119` | RFC Editor, BCP 14, March 1997 | — |
| `euaiact` | EUR-Lex, Regulation (EU) 2024/1689 | Article mapping **confirmed**: Art. 12 record-keeping, Art. 19 automatically generated logs, Art. 43 conformity assessment. (Art. 11 is technical documentation — distinct, and not claimed.) |
| `fdapccp` | FDA final guidance, December 2024 | Title verified in full. |
| `iso42001` | ISO/IEC 42001:2023 | Published December 2023. |
| `nistairmf` | NIST AI 100-1, doi:10.6028/NIST.AI.100-1 | Jan 2023; Govern/Map/Measure/Manage functions confirmed. |
| `rfc6962` | RFC Editor, June 2013 | Obsoleted by RFC 9162 (CT v2.0); we cite 6962 for the original Merkle-log design and note the successor. |

## Open items before public announcement

These are from `design-doc.md` §14 and do not block the repository, only the
public launch:

- Name collision check for the final protocol name (Minhal owns the rename).
- EU Digital Omnibus outcome and the real high-risk enforcement dates.
- Exact quantitative figures from the DGM/AlphaEvolve/GEPA papers if the paper
  ever quotes their numbers. It currently does **not**: `dgm` is cited only
  for the qualitative eval-gaming result, which is verified above.
