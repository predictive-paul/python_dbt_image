# python_dbt_image

Prebuilt **Python 3.11 + dbt-bigquery** image for [pi_dbt](https://github.com/predictiveinsights/pi_dbt) CI.

pi_dbt currently starts from `python:3.11-slim` and `pip install -r ci/requirements.txt` (`dbt-bigquery==1.11.3`) on every GitLab Pages job and GitHub Pages workflow. This repo builds that environment once so those pipelines can pull a tagged image instead of rebuilding it each run.

This image is for **dbt**. It does not include the separate Polars `python/models_input/` stack in pi_dbt.

## Image contents

| Pin | Source in pi_dbt |
|---|---|
| Python 3.11 (slim) | `.gitlab-ci.yml` (`image: python:3.11-slim`) and `.github/workflows/pages.yml` |
| `dbt-bigquery==1.11.3` | `ci/requirements.txt` |
| `git` | needed for `dbt deps` (dbt Hub packages such as `dbt_utils`) |

`dbt deps` is **not** baked in: package versions live in the consumer repo (`packages.yml`).

## Tags

Default image name is `dbt`. Version comes from [`VERSION`](VERSION) (currently `0.1.0`).

| Registry | Example |
|---|---|
| Local | `dbt:0.1.0` / `dbt:latest` |
| GHCR | `ghcr.io/predictive-paul/python_dbt_image/dbt:0.1.0` |
| Artifact Registry | `europe-west1-docker.pkg.dev/pi-storage-258815/pi/dbt:0.1.0` |

Pushing a `v*` git tag publishes that version (`v0.1.0` → `:0.1.0` and `:latest`). Tags of the form `{image}_{version}` (e.g. `dbt_0.1.0`) also work, matching [pi_docker](https://github.com/predictiveinsights/pi_docker).

## Build locally

Requires Docker and Python 3 (stdlib only; no extra packages).

```bash
python3 build.py
docker run --rm dbt:0.1.0 dbt --version
```

Useful flags:

```bash
python3 build.py --dry-run
python3 build.py --version 0.1.0 --no-latest
python3 build.py --push --registry ghcr.io/predictive-paul/python_dbt_image
```

`--push` only pushes registry-qualified tags (local `dbt:0.1.0` is skipped). Log in first:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u USER --password-stdin
# optional, for Artifact Registry:
gcloud auth configure-docker europe-west1-docker.pkg.dev
```

## Publish

Increment `VERSION`, commit, and create an annotated git tag. Pushing that tag
publishes the image (or run **Build image** from Actions):

```bash
python3 build.py --bump patch   # 0.1.0 → 0.1.1, commit, tag v0.1.1
git push origin HEAD
git push origin v0.1.1
```

`--bump minor` and `--bump major` reset the lower parts (`0.1.0` → `0.2.0` /
`1.0.0`). The workflow tags the image with the semver from the git tag
(`v0.1.1` → `:0.1.1` and `:latest`).

[`.github/workflows/build.yml`](.github/workflows/build.yml) runs `build.py --push` on `v*` / `dbt_*` tags and via `workflow_dispatch`.

- Always pushes to **GHCR** (using `GITHUB_TOKEN`).
- Pushes to **Artifact Registry** only when GCP Workload Identity or `GCP_SERVICE_KEY` is configured (same vars/secrets as pi_docker).

`cloudbuild.yaml` is an optional GCP-side equivalent if you already trigger Cloud Build from git tags.

## How pi_dbt should consume this

Point jobs at the tagged image and drop the per-run `pip install`. Keep `dbt deps` in the job so Hub packages follow pi_dbt's `packages.yml`.

**GitLab** (replace `python:3.11-slim` + `pip install`):

```yaml
.dbt_docs:
  image: ghcr.io/predictive-paul/python_dbt_image/dbt:0.1.0
  before_script:
    - dbt deps
```

**GitHub Actions** (replace `setup-python` + `pip install`):

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    container: ghcr.io/predictive-paul/python_dbt_image/dbt:0.1.0
    steps:
      - uses: actions/checkout@v4
      - run: dbt deps
```

If this GitHub package is private, grant the pi_dbt workflow `packages: read` and log in to GHCR (or make the package public). Artifact Registry pulls need a GCP identity with `roles/artifactregistry.reader`, same as other PI images.

Pin a version tag in consumers (`:0.1.0`), not `:latest`.
