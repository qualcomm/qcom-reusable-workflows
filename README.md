# Qualcomm Reusable Workflows

This project contains reusable GitHub Actions workflows for Qualcomm projects. Do not use directly. See [qualcomm/qcom-actions](https://github.com/qualcomm/qcom-actions) for usage.

## Overview

The `qcom-reusable-workflows` repository provides a collection of reusable GitHub Actions workflows that can be incorporated into your Qualcomm projects. These workflows help ensure code quality, security, and compliance with Qualcomm standards.

## Workflow Components

The main orchestrator workflow is `reusable-qcom-preflight-checks-orchestrator.yml`, which coordinates the execution of several specialized workflows:

1. **Semgrep Scan** - Static code analysis for security vulnerabilities
2. **Dependency Review** - Checks for vulnerabilities in dependencies
3. **Repolinter Check** - Ensures repository follows best practices
4. **Copyright and License Check** - Verifies proper copyright and license notices
5. **Commit Email Check** - Validates commit author emails
6. **Commit Message Check** - Ensures commit messages follow standards (optional)

## Usage

Create a file `.github/workflows/qcom-preflight-checks.yml` in your repository:

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
    uses: qualcomm/qcom-reusable-workflows/.github/workflows/reusable-qcom-preflight-checks-orchestrator.yml@v2.0.0
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

## Workflow Configuration Options

### Semgrep Scan

[Semgrep](https://semgrep.dev/) is a lightweight static analysis tool for finding bugs and enforcing code standards.

**Configuration Options:**
- `enable-semgrep-scan`: Boolean to enable/disable the scan (default: `true`)
- `semgrep-cli-options`: String containing CLI options for Semgrep (default: `--config auto`)

**Available Semgrep CLI Options:**

Semgrep supports numerous command-line options. Some commonly used options include:

- `--config <rules>`: Specify rules or rule sets (e.g., `--config p/owasp-top-ten`)
- `--severity <level>`: Filter by severity level (e.g., `--severity ERROR`)
- `--exclude <pattern>`: Exclude files/directories matching pattern
- `--include <pattern>`: Only include files/directories matching pattern
- `--max-target-bytes <n>`: Maximum file size to scan in bytes
- `--timeout <seconds>`: Maximum time to spend running a rule on a single file

For a complete list of options, visit the [Semgrep CLI Reference](https://semgrep.dev/docs/cli-reference).

**Ignoring Files and Folders:**

You can create a `.semgrepignore` file in your repository to specify files and folders that should be ignored during scanning. This file uses the same syntax as `.gitignore`.

Example `.semgrepignore` file:
```
# Ignore node_modules directory
node_modules/

# Ignore build artifacts
dist/
build/

# Ignore specific file types
*.min.js
*.test.js
```

For more information on ignoring files and folders, see the [Semgrep documentation](https://semgrep.dev/docs/ignoring-files-folders-code).

### Dependency Review

Dependency Review checks for vulnerabilities in your project dependencies when they change in pull requests.

**Configuration Options:**
- `enable-dependency-review`: Boolean to enable/disable the review (default: `true`)

The workflow automatically:
- Detects if dependency review is supported for your repository
- Runs the review on pull requests or pushes
- Fails on critical severity vulnerabilities

### Repolinter Check

[Repolinter](https://github.com/todogroup/repolinter) is a tool that checks repositories for compliance with open source best practices.

**Configuration Options:**
- `enable-repolinter-check`: Boolean to enable/disable the check (default: `true`)

The workflow:
- Checks for a local `repolint.json` configuration file in your repository
- If found, uses your custom configuration
- If not found, uses the default Qualcomm ruleset from `https://raw.githubusercontent.com/qualcomm/.github/main/repolint.json`

### Additional Checks

- **Copyright and License Check**: Verifies proper copyright and license notices in files using [copyright-license-checker-action](https://github.com/qualcomm/copyright-license-checker-action)
  - **Configuration Options:**
    - `enable-copyright-license-check`: Boolean to enable/disable the check (default: `true`)
  - Runs only on pull requests and checks files changed in the PR

- **Commit Email Check**: Validates that commit author emails follow required patterns using [commit-emails-check-action](https://github.com/qualcomm/commit-emails-check-action)
  - **Configuration Options:**
    - `enable-commit-email-check`: Boolean to enable/disable the check (default: `true`)
  - Runs on both push and pull request events

- **Commit Message Check**: Ensures commit messages follow standards (disabled by default) using [commit-msg-check-action](https://github.com/qualcomm/commit-msg-check-action)
  - **Configuration Options:**
    - `enable-commit-msg-check`: Boolean to enable/disable the check (default: `false`)
    - `commit-msg-check-extra-options`: String containing JSON object with options (default: empty string)
      ```json
      {"body-char-limit": 60, "sub-char-limit": 50, "check-blank-line": true}
      ```
  - Runs only on pull request events

For detailed configuration options and default values for each action, please refer to their respective GitHub repositories.

## Branches

**main**: Primary development branch. Contributors should develop submissions based on this branch, and submit pull requests to this branch.

## Getting in Contact

* [Report an Issue on GitHub](../../issues)

## License

*qcom-reusable-workflows* is licensed under the [BSD-3-clause License](https://spdx.org/licenses/BSD-3-Clause.html). See [LICENSE.txt](LICENSE.txt) for the full license text.
