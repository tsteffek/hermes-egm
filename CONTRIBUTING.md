# Contributing

Hermes EGM is an independent Hermes plugin inspired by Elephant/Goldfish design
review. Keep changes focused and use documented Hermes plugin APIs. Preserve the
snapshot-only, tool-free reviewer design. Discuss larger changes before implementation.

## Making a change

1. Create a branch and describe the behavior being changed.
2. Add regression tests for changed behavior. Distinguish fake-provider tests from
   live model checks.
3. Run the unit tests, Ruff, strict mypy and plugin validation commands in the
   [development guide](README.md#development-and-verification).
4. Update affected documentation and `CHANGELOG.md` under Added, Changed, Fixed or Removed.
5. Open a pull request explaining the change and checks performed. Security and
   privacy changes require focused independent review.

AI-assisted contributions are welcome. Disclose material AI assistance in the
pull request and describe the checks performed. This implementation was developed
with Hermes Agent assistance.

## Releases and catalog updates

Release tags, the plugin manifest and catalog entries must describe the same
source version. Catalog entries use a full commit pin and matching capabilities,
compatibility metadata and artwork links. Validate the pinned source before
submitting an entry or updating an existing submission.

Follow the current [Hermes catalog submission guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission).
Catalog review and merging are handled by Hermes maintainers.

## Conduct and security

Keep discussion respectful and focused on the change. Report vulnerabilities
using the process in [SECURITY.md](SECURITY.md), without publishing secrets or
sensitive review inputs.
