# Distro Test Workflow

[`reusable-test-distro.yml`](../.github/workflows/reusable-test-distro.yml) runs LAVA boot and pre-merge tests for a single distro
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

**Permissions:**

The workflow grants no token permissions by default and each job asks only for
what it needs. A reusable workflow can't be granted more than its caller has, so
the calling job has to grant at least:

```yml
    permissions:
      actions: read
      checks: write
      contents: read
      pull-requests: write
```

**Outputs:**

- `summary_id`: ID of the uploaded test summary artifact.

Pre-merge tests only run when all boot jobs pass and `devices_premerge` is set.

## Pinning

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

The [`test-job-summary`](../.github/actions/test-job-summary) action lives in this
repository rather than in the caller, and is referenced by repository path and ref for
the same reason, so no job needs a copy of this repository.

Anything the job templates need beyond the defaults set by the workflow
(`AUDIO_CLIPS_BASE_DIR`, `DOCKER_IMAGE_POSTPROCESS`, `AUTH_HEADER_NAME`,
`AUTH_HEADER_TOKEN`) is passed through `variables` or `variables_files`, which are
applied last and therefore overwrite those defaults.
