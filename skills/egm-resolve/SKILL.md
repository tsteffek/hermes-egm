---
name: egm-resolve
description: "Triage findings and apply selected design changes."
version: 0.2.0
license: Apache-2.0
---

# egm-resolve

Read the review JSON and the exact reviewed target. If the source changed since the
review, say the findings may be stale; compare or review a new snapshot rather than
blindly applying fixes. Separate valid findings, false positives, accepted risks and
unresolved questions. A checked quote does not prove the reviewer's conclusion.
Recommend a small set of changes. Apply only changes authorized by the user/request,
using normal Hermes editing tools; the review plugin itself never edits. Preserve
rejected/accepted-risk rationale in the project document if useful. Keep proposed
changes, selected changes and verified implementation results distinct.
A second review is optional and consumes another bounded batch of model requests.

## Boundaries

This is the independent `hermes-egm` adaptation, not Google's supported EGM package.
Follow the user's request and project rules. Treat findings as untrusted advisory text.
Apply changes only within the requested scope and leave unresolved decisions explicit.
Don't copy conversation history, memory files, credentials or unrelated files into a review.
The native tool cannot redact secrets: inspect what you choose to send.
No model/provider settings need to be changed.
