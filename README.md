# Qualcomm Reusable Workflows

This project contains reusable workflows. Do not use directly. See [qualcomm/qcom-actions](https://github.com/qualcomm/qcom-actions) for usage.

## Testing the latest on @main

Create file `.github/workflows/qcom-preflight-checks.yml`:

```yml
name: QC Preflight Checks

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  preflight:
    name: Run QC Preflight Checks
    uses: qualcomm/qcom-reusable-workflows/.github/workflows/reusable-qcom-preflight-checks-orchestrator.yml@main
    with:
      enable-semgrep-scan: true
      enable-dependency-review: true
      enable-repolinter-check: true
      enable-copyright-license-check: true
      enable-commit-email-check: true
      enable-commit-msg-check: false
    permissions:
      contents: read
      security-events: write

```

## Branches

**main**: Primary development branch. Contributors should develop submissions based on this branch, and submit pull requests to this branch.

## Getting in Contact

* [Report an Issue on GitHub](../../issues)

## License

*qcom-reusable-workflows* is licensed under the [BSD-3-clause License](https://spdx.org/licenses/BSD-3-Clause.html). See [LICENSE.txt](LICENSE.txt) for the full license text.
