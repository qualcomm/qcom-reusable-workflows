# Qualcomm Reusable Workflows

This project contains reusable GitHub Actions workflows for Qualcomm projects. Do not use directly. See [qualcomm/qcom-actions](https://github.com/qualcomm/qcom-actions) for usage.

## Overview

The `qcom-reusable-workflows` repository provides a collection of reusable GitHub Actions workflows that can be incorporated into your Qualcomm projects. These workflows help ensure code quality, security, and compliance with Qualcomm standards.

## Workflow Components

The main orchestrator workflow is `reusable-qcom-preflight-checks-orchestrator.yml`, which coordinates the execution of several specialized workflows:

1. **[Semgrep Scan](https://github.com/semgrep/semgrep)** - Static code analysis for security vulnerabilities
2. **[Dependency Review](https://github.com/actions/dependency-review-action)** - Checks for vulnerabilities in dependencies
3. **[Dependency Confusion Scan](https://github.com/omni-line/omni-audit)** - Detects dependency confusion, typosquatted and known-malicious dependencies
4. **[Repolinter Check](https://github.com/todogroup/repolinter-action)** - Ensures repository follows best practices
5. **[Copyright and License Check](https://github.com/qualcomm/copyright-license-checker-action)** - Verifies proper copyright and license notices
6. **[Commit Email Check](https://github.com/qualcomm/commit-emails-check-action)** - Validates commit author emails
7. **[Commit Message Check](https://github.com/qualcomm/commit-msg-check-action)** - Ensures commit messages follow standards (optional)
8. **[ARMOR Compatibility Checkers](https://github.com/qualcomm/armor-checkers)** - Ensures source code follows API and ABI backward compatibility (optional)


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
    uses: qualcomm/qcom-reusable-workflows/.github/workflows/reusable-qcom-preflight-checks-orchestrator.yml@v2
    with:
      enable-semgrep-scan: true
      enable-dependency-review: true
      enable-dependency-confusion-scan: true
      enable-repolinter-check: true
      enable-copyright-license-check: true
      enable-commit-email-check: true
      enable-commit-msg-check: false
      enable-armor-checkers: false
    permissions:
      contents: read
      security-events: write
```

## Workflow Configuration Options

### Semgrep Scan

[Semgrep](https://semgrep.dev/) is a lightweight static analysis tool for finding bugs and enforcing code standards. The scan runs [semgrep](https://github.com/semgrep/semgrep) from its official container image.

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

Dependency Review checks for vulnerabilities in your project dependencies when they change in pull requests using [dependency-review-action](https://github.com/actions/dependency-review-action).

**Configuration Options:**
- `enable-dependency-review`: Boolean to enable/disable the review (default: `true`)

The workflow automatically:
- Detects if dependency review is supported for your repository
- Runs the review on pull requests or pushes
- Fails on critical severity vulnerabilities

### Dependency Confusion Scan

The dependency confusion scan checks your dependency manifests with [omni-audit](https://github.com/omni-line/omni-audit) and reports the results as code scanning alerts in the repository's Security tab.

**Configuration Options:**
- `enable-dependency-confusion-scan`: Boolean to enable/disable the scan (default: `true`)
- `dependency-confusion-scan-options`: String of extra omni-audit CLI options, separated by whitespace (default: empty string)

The workflow:
- Runs on push, pull request and `workflow_dispatch` events in public repositories only, because the scan sends dependency names to the public registries and would disclose the internal package names of private and internal repositories. Pull requests and pushes from Dependabot are skipped.
- Reports dependencies whose name is not registered on the public registry, so anyone could publish it. It checks npm, PyPI, Maven, Go, Cargo, RubyGems, Composer and Conan manifests, and Docker Hub images in Dockerfiles and Compose files. NuGet is not supported.
- Also reports typosquats of popular packages, known-malicious packages from the [OpenSSF malicious packages](https://github.com/ossf/malicious-packages) database, and package manager settings that let a public package replace an internal one, such as `--extra-index-url`
- Uploads the results to code scanning (category `omni-audit`)
- Fails when open code scanning alerts of error severity remain, which are omni-audit's critical and high findings. To accept a risk or mark a false positive, dismiss the alert in the Security tab.
- Fails without uploading results when a manifest cannot be parsed or a registry cannot be reached, so an incomplete scan does not close open alerts
- Downloads a pinned omni-audit release and verifies its SHA-256 digest

Lockfile entries that resolve from public registries are not reported (`--no-sources`), because open source projects normally install from them.

**Example options:**
```yml
dependency-confusion-scan-options: '--exclude tests/fixtures --safe-namespace @my-org/* --ignore my-internal-*'
```
- `--exclude <path>`: Skip a directory or file, e.g., test fixtures with placeholder or invalid manifests
- `--safe-namespace <glob>`: Skip namespaces you own, e.g., an npm scope or a Maven group
- `--ignore <glob>`: Skip package names
- `--allow <name>`: Treat a package name as safe in the typosquat check
- `--no-sources=false --expected-host <host>`: Also report lockfile entries that resolve from hosts other than your registry

The options are split on whitespace and passed to omni-audit without quote processing. The output format, the exit behavior and `--strict` cannot be overridden. For all options, see the [omni-audit flags](https://github.com/omni-line/omni-audit#flags).

### Repolinter Check

[Repolinter](https://github.com/todogroup/repolinter) is a tool that checks repositories for compliance with open source best practices. It is run using [repolinter-action](https://github.com/todogroup/repolinter-action).

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

- **ARMOR Compatibility Checkers**: Ensures source-level (API) and binary-level (ABI) backward compatibility of source code using [armor-checkers](https://github.com/qualcomm/armor-checkers)
  - **Configuration Options:**
    - `enable-armor-checkers`: Boolean to enable/disable the check (default: `false`)
    - `armor-checker-options`: String containing JSON object with options (default: empty string). To view all available options, please see [armor-checkers](https://github.com/qualcomm/armor-checkers)
  - Runs on both push and pull request events

For detailed configuration options and default values for each action, please refer to their respective GitHub repositories.

## Branches

**main**: Primary development branch. Contributors should develop submissions based on this branch, and submit pull requests to this branch.

## Getting in Contact

* [Report an Issue on GitHub](../../issues)

## License

*qcom-reusable-workflows* is licensed under the [BSD-3-clause License](https://spdx.org/licenses/BSD-3-Clause.html). See [LICENSE.txt](LICENSE.txt) for the full license text.
