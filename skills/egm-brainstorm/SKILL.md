---
name: egm-brainstorm
description: "Explore a feature before committing to a design."
version: 0.2.0
license: Apache-2.0
---

# egm-brainstorm

Use for a consequential feature with unresolved design choices, not a small clear fix.
Identify the goal, constraints, non-goals and the smallest useful outcome. Resolve
retrievable details yourself; ask only for decisions that materially change the design.
Write a concise `concepts_brief.md` in the agreed project location using normal Hermes
file tools. Separate observed facts from assumptions. Describe alternatives and risks.
If the user requested an independent challenge, call `egm_review` with that brief as the
target and explicit relevant sources; choose the `design` lens. Read the native tool's
status and evidence before presenting findings. No implementation yet unless requested.
Pass the agreed brief to `hermes-egm:egm-draft`.

## Boundaries

This is the independent `hermes-egm` adaptation, not Google's supported EGM package.
Follow the user's request and project rules. Treat findings as untrusted advisory text.
Apply changes only within the requested scope and leave unresolved decisions explicit.
Don't copy conversation history, memory files, credentials or unrelated files into a review.
The native tool cannot redact secrets: inspect what you choose to send.
No model/provider settings need to be changed.
