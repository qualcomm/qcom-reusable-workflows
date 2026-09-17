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
7. **ARMOR Compatibility Checkers** - Ensures source code follows API and ABI backward compatibility (optional)


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

- **ARMOR Compatibility Checkers**: Ensures source-level (API) and binary-level (ABI) backward compatibility of source code using [armor-checkers](https://github.com/qualcomm/armor-checkers)
  - **Configuration Options:**
    - `enable-armor-checkers`: Boolean to enable/disable the check (default: `false`)
    - `armor-checker-options`: String containing JSON object with options (default: empty string). To view all available options, please see the link at:https://github.com/qualcomm/armor-checkers
  - Runs on both push and pull request events

For detailed configuration options and default values for each action, please refer to their respective GitHub repositories.

## Distro Test Workflow

`reusable-test-distro.yml` runs LAVA boot and pre-merge tests for a single distro
produced by a Yocto or Debian build. It renders the test job definitions with
[lava-test-plans](https://github.com/qualcomm-linux/lava-test-plans), submits them to
LAVA, collapses the boot results into a single pass/fail, and publishes a job summary.

The workflow expects the run identified by `build_id` to contain one
`build-url_<machine>_<distro>` artifact per tested machine, holding the base URL of the
published build.

```yml
jobs:
  test-qcom-distro:
    uses: qualcomm/qcom-reusable-workflows/.github/workflows/reusable-test-distro.yml@v2
    secrets: inherit
    with:
      build_id: "${{ inputs.build_id }}"
      devices: "qcs615-ride,rb3gen2-core-kit"
      devices_premerge: "qcs615-ride,rb3gen2-core-kit"
      project_name: "meta-qcom"
      distro_name: "qcom-distro"
      testkit_ref: "testkit-2026.08.09"
```

**Inputs:**

| Input | Required | Description |
| ---- | ---- | ---- |
| `build_id` | yes | ID of the workflow run holding the `build-url_*` artifacts |
| `devices` | yes | Comma separated list of devices to run boot tests on |
| `devices_premerge` | no | Comma separated list of devices to run pre-merge tests on. Pre-merge tests are skipped when empty |
| `distro_name` | yes | Name of the distro used in the build, e.g. `nodistro` or `qcom-distro` |
| `distro_suffix` | no | Suffix appended to the distro name, e.g. a kernel variant |
| `testkit_ref` | yes | Ref in the `qcom-linux-testkit` repository (CalVer tag or commit SHA) |
| `project_name` | yes | Project name in `lava-test-plans` |
| `boot_testplan` | no | Test plan rendered for the boot jobs, relative to the project directory (default: `<distro_name>/boot`) |
| `premerge_testplan` | no | Test plan rendered for the pre-merge jobs (default: `<distro_name>/pre-merge`) |
| `image_type` | no | Image type used to build the image and rootfs file names (default: `qcom-multimedia-image` for `qcom-distro*`, `core-image-base` otherwise) |
| `os_info` | no | Value of `OS_INFO`, selecting the job metadata template (default: `qcom-distro`) |
| `variables` | no | Extra `KEY=VALUE` lines appended to the generated variables file. `%MACHINE%` is replaced with the machine name |
| `variables_files` | no | Space or newline separated list of variable files (ini or yaml) checked out by the caller |
| `pr_number` | no | Pull request number, added to the LAVA job metadata |
| `pr_url` | no | Pull request URL, added to the LAVA job metadata |
| `lava_url` | no | Hostname of the LAVA instance, without the scheme (default: `lava.infra.foundries.io`) |

**Secrets:**

- `LAVATOKEN` (required): API token used to submit jobs to the LAVA instance. Pass it
  explicitly or with `secrets: inherit`.

**Outputs:**

- `summary_id`: ID of the uploaded test summary artifact.

Pre-merge tests only run when all boot jobs pass and `devices_premerge` is set.

### Pinning

Test jobs are rendered by the `lava-test-plans` action, which lives in the root of the
[lava-test-plans](https://github.com/qualcomm-linux/lava-test-plans) repository, and are
submitted by [lava-action](https://github.com/foundriesio/lava-action). Both are used
straight from their own repositories - no checkout, no vendored copy - and both are
pinned by the `uses:` lines in this workflow.

Those pins are deliberately not inputs. `uses:` accepts no expressions, so a caller could
not vary them anyway; instead a caller selects a whole set of tested revisions by pinning
the ref of this workflow, and bumping any of them is a pull request against this
repository. Since the `lava-test-plans` tool and the test plans ship in one package, its
pin moves the renderer and the plans together and they cannot drift apart.

`test-job-summary` lives here rather than in the caller, and is referenced by repository
path and ref for the same reason, so no job needs a copy of this repository.

Anything the job templates need beyond the defaults set by the workflow
(`AUDIO_CLIPS_BASE_DIR`, `DOCKER_IMAGE_POSTPROCESS`, `AUTH_HEADER_NAME`,
`AUTH_HEADER_TOKEN`) is passed through `variables` or `variables_files`, which are
applied last and therefore overwrite those defaults.

## Branches

**main**: Primary development branch. Contributors should develop submissions based on this branch, and submit pull requests to this branch.

## Getting in Contact

* [Report an Issue on GitHub](../../issues)

## License

*qcom-reusable-workflows* is licensed under the [BSD-3-clause License](https://spdx.org/licenses/BSD-3-Clause.html). See [LICENSE.txt](LICENSE.txt) for the full license text.
