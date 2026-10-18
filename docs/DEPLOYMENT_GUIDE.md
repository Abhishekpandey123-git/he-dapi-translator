# Deployment Guide (beginner-friendly)

How code goes from your laptop to a released Docker image — and exactly how to
**review + approve** a production deploy in GitHub.

---

## 1. The big picture — a conveyor belt with 3 stations

All automation lives in `.github/workflows/` and runs on **GitHub Actions** (free
machines in the cloud).

| Station | File | Triggered by | What it does | Approval? |
|---|---|---|---|---|
| **1. Test (CI)** | `ci.yml` — job shown as **`guards`** | every push / pull request | Runs tests + resource guards. If it's red, stop. | no |
| **2. Build & publish** | `cd-staging.yml` | push to `main` | Builds the Docker image, pushes it to **GHCR** as `:staging` and `:<sha>`. | no |
| **3. Promote to production** | `cd-production.yml` | pushing a **tag** like `v*.*.*` | Re-tags the *already-built, already-tested* image as `:vX.Y.Z` + `:latest`. | **yes — you** |

> Key idea: production **does not rebuild**. It just re-labels the exact same tested
> image. Safe and fast.

**GHCR** = GitHub Container Registry, where the Docker image is stored
(`ghcr.io/urbiologicalpa/he-dapi-translator`).

---

## 2. Why GitHub asks you to approve

Station 3 uses an **Environment protection rule**. The environment is named
**`production`** and is configured to require a human reviewer. When a run reaches
that point it pauses at **"Waiting for approval"** and sends you a notification.
Nothing is published to `:latest` until you click **Approve**.

This is a safety gate: even if I (or CI) push a tag, *you* decide whether it ships.

---

## 3. Review + approve — step by step

1. Open the repo → **Actions** tab.
   > _[screenshot: top nav, "Actions" tab highlighted]_
2. In the **left sidebar**, click **`cd-production`**.
   > _[screenshot: workflows sidebar with cd-production selected]_
3. Click the run marked **Waiting** (yellow dot). Look for the banner
   **"This workflow is waiting for approval."**
   > _[screenshot: run summary with the waiting banner]_
4. Click **"Review deployments."**
   > _[screenshot: Review deployments button]_
5. A dialog opens listing the environment **`production`**. **Check these before approving:**
   - **Tag / version** is what you intended (e.g. `v0.1.0`), not a typo.
   - **Commit SHA** is one that already passed **`guards`** (green check).
   - Expand the **`promote` job** — steps should read: *Set up job → checkout → Log in
     to GHCR → Promote image → done*. No red steps.
   - It's a good moment to ship (no half-finished work on `main`).
6. Tick the **`production`** checkbox, optionally add a comment, then click
   **"Approve and deploy."**
   > _[screenshot: dialog with production ticked + Approve and deploy button]_
7. Watch the run finish green. Verify the tags under
   **repo → right sidebar → Packages → `he-dapi-translator`** (should now show
   `:vX.Y.Z` and `:latest`).

### To reject / stop
- Simply **don't approve** (close the dialog) — the run stays paused.
- Or open the run → **Cancel workflow** (top-right) to abort it. Nothing reaches `:latest`.

---

## 4. Your normal flow going forward

- **Daily:** you (or I) push to `main` → `guards` runs → `cd-staging` publishes
  `:staging`. You do nothing.
- **To release:** push a tag `vX.Y.Z` (I can do this) → `cd-production` starts →
  **you review + approve** → `:vX.Y.Z` + `:latest` go live.
- **If anything looks wrong at a gate:** don't approve; ask me and I'll cancel.

---

## 5. Glossary (plain English)

| Term | Meaning |
|---|---|
| **Workflow** | A YAML recipe in `.github/workflows/`. |
| **Run** | One execution of a workflow (what you see in the Actions tab). |
| **Job / Step** | A run is made of jobs; jobs are made of steps. |
| **CI** | Continuous Integration — automatically test every change. |
| **CD** | Continuous Delivery/Deployment — automatically ship passing changes. |
| **Tag** | A named pointer to a commit, e.g. `v0.1.0`. Used to trigger releases. |
| **SHA** | The 40-char fingerprint of a commit (e.g. `d36922c…`). |
| **GHCR** | GitHub's Docker image registry. |
| **Environment** | A named deploy target with rules; ours is `production` (needs your approval). |
| **guards** | Our CI job that runs the tests/resource checks. |

---

## 6. Troubleshooting

| Symptom | Meaning / fix |
|---|---|
| Run stuck on **"Waiting for approval"** | Expected — go to step 3 and approve (or cancel). |
| **`guards` red** on `main` | A test failed. Don't tag a release; fix the test first. |
| **`cd-production` fails at "checkout"** | Historical bug (fixed 2026-10-18): `fetch-tags: true` broke checkout on release events. Workflow now pins `ref` and triggers on tag-push only. |
| **`cd-staging` skipped** | Expected if the push only changed docs (paths filter). |
| Can't find the run | Ensure you're on the **Actions** tab and the left sidebar filter is **All workflows**. |

---

## 7. Quick reference (commands for maintainers)

```bash
# See recent runs (needs a token with repo scope at ~/.github_pat)
curl -s -H "Authorization: Bearer $(cat ~/.github_pat)" \
  "https://api.github.com/repos/urbiologicalpa/he-dapi-translator/actions/runs?per_page=5"

# Create + push a release tag (triggers cd-production -> waits for YOUR approval)
git tag -a v0.2.0 -m "v0.2.0" && git push origin v0.2.0
```
