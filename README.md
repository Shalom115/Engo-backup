# Engo-backup

Automated read-only backup of [`engineergelliceaux/engo`](https://github.com/engineergelliceaux/engo).

A scheduled GitHub Actions workflow (`.github/workflows/mirror-engo.yml`) syncs
every branch and tag from `engo` into this repo every 15 minutes (or on-demand
via the Actions tab "Run workflow" button).

## Where the backup lives

Mirrored content is pushed under the `mirror/` prefix, e.g.:

- `engo`'s `main` branch → `mirror/main` here
- `engo`'s `v1.2.3` tag → `mirror/v1.2.3` here

This repo's own default branch (`main`) is never overwritten by the sync — it
only holds this workflow and README. Keeping the sync scoped to `mirror/*`
means the workflow file can't accidentally delete itself when the sync runs.

To restore from backup, check out the relevant `mirror/<branch>` branch.

## Required setup

A repo secret named `ENGO_SOURCE_TOKEN` must be set (Settings → Secrets and
variables → Actions) containing a read-only Personal Access Token for the
`engineergelliceaux` account with access to the `engo` repo.

The repo's Actions workflow permissions (Settings → Actions → General →
Workflow permissions) must be set to "Read and write permissions" so the
built-in `GITHUB_TOKEN` can push the mirrored branches here.
