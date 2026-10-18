# Publishing `he-dapi` and `napari-he-dapi` (PyPI)

Both packages live in `packages/` and are **independent PyPI distributions**:

| Package | Directory | Import | Console script |
|---|---|---|---|
| `he-dapi` | `packages/he-dapi/` | `he_dapi` | `he-dapi` |
| `napari-he-dapi` | `packages/napari-he-dapi/` | `napari_he_dapi` | — (napari plugin) |

`napari-he-dapi` depends on `he-dapi`, so publish **`he-dapi` first**.

---

## 1. Build locally (dry run)
```bash
cd packages/he-dapi        && uv build      # -> dist/*.whl + *.tar.gz
cd ../napari-he-dapi       && uv build
```
Install into a scratch venv to sanity-check:
```bash
python -m venv /tmp/hd && /tmp/hd/bin/pip install packages/he-dapi/dist/*.whl
/tmp/hd/bin/he-dapi info
```
> Wheels are git-ignored (`dist/`). Never commit them.

## 2. Publish to TestPyPI first (recommended)
1. Create a TestPyPI account: https://test.pypi.org/account/register/
2. Generate an API token (Account → API tokens).
3. Upload:
```bash
uv publish --publish-url https://test.pypi.org/legacy/ \
  --token pypi-XXXXXXXX packages/he-dapi/dist/*
uv publish --publish-url https://test.pypi.org/legacy/ \
  --token pypi-XXXXXXXX packages/napari-he-dapi/dist/*
```
4. Verify: `pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple he-dapi`

## 3. Publish to real PyPI
1. Account: https://pypi.org/account/register/ (verify email, enable 2FA).
2. Create an API token scoped to the project (or account-wide for first upload).
3. Upload:
```bash
uv publish --token pypi-XXXXXXXX packages/he-dapi/dist/*
uv publish --token pypi-XXXXXXXX packages/napari-he-dapi/dist/*
```
Bump `version =` in each `pyproject.toml` for every release (PyPI rejects duplicates).

---

## 4. Automated publishing via GitHub Actions (no stored secrets)

Use **PyPI Trusted Publishing** (OIDC) — no token needed in the repo.

**One-time setup on PyPI:** *Your projects → Publishing* → add a *pending publisher*:
- Owner: `urbiologicalpa`
- Repository: `he-dapi-translator`
- Workflow: `publish-pypi.yml`
- Environment: `pypi`

**Then:** `Actions → publish-pypi → Run workflow` (pick `testpypi` or `pypi`).
The workflow is **manual only** and uses a protected environment, consistent with the
repo's "no unattended production deploys" rule.

## 5. napari plugin listing
After `napari-he-dapi` is on PyPI it appears on
[napari-hub](https://napari-hub.org) automatically (npe2 manifest is bundled).
You can refine the listing (screenshots, description) on the hub.

## 6. Checklist per release
- [ ] bump `version` in `packages/*/pyproject.toml`
- [ ] `uv build` both, install-check the wheels
- [ ] tag the repo (`vX.Y.Z`) — notify maintainer; production env approval applies
- [ ] run `publish-pypi` workflow (testpypi first)
- [ ] confirm `pip install he-dapi` and `pip install napari-he-dapi` work
