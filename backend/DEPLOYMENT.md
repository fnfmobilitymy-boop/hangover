# GitHub Actions → Render

GitHub Actions runs tests and requests deployments. Render runs the website, API and administration UI continuously, with a persistent disk for SQLite and uploads. GitHub Pages remains a separate static demo.

## One-time setup

For an already connected Render Blueprint, automatic deployment now waits for GitHub checks to pass (`autoDeployTrigger: checksPass`). With Blueprint Auto Sync enabled, pushes to `main` are published after the checks succeed. No Render API key is required for this path. The API-based Action below remains an optional way to request and verify an explicit deployment. Avoid running both for the same commit.

1. Open [Create KENNY on Render](https://render.com/deploy?repo=https://github.com/fnfmobilitymy-boop/hangover). Sign in, connect this repository, and review the Blueprint. **The Starter web service and 1 GB disk are paid resources. Review Render's current price before confirming.** No hosting resource is created merely by pushing this repository.
2. After creation, copy the service ID (`srv-…`) from Render. In GitHub repository **Settings → Secrets and variables → Actions → Variables**, create `RENDER_SERVICE_ID`. Use a repository variable so the push trigger can see it.
3. Create a Render API key in your Render account settings. In GitHub **Actions secrets**, save it as `RENDER_API_KEY`. Do not paste it into chat, source files or logs. It must be available to the `backend-production` GitHub environment. Follow any organization environment approval rules.
4. For the optional API-based route, set Render's Auto-Deploy to **Off** to avoid duplicate deployments. Open GitHub **Actions → Deploy KENNY backend → Run workflow**, select `main`, and run it. The job tests the application, deploys that exact commit, waits for Render's live state, checks public health/admin, and prints the verified public URLs in the job summary. Future pushes to `main` deploy through this Action once `RENDER_SERVICE_ID` exists. To stay on the Blueprint's check-based route, leave `RENDER_SERVICE_ID` unset; GitHub checks and Render handle publishing without this API-based Action.

If GitHub environment protections require a reviewer, approve the `backend-production` deployment in Actions. A missing API key or service ID produces a clear setup error. The workflow cannot create hosting accounts or paid services for you.

## Administrator initialization

Open the **verified** `/admin/` URL from the Actions summary. In Render's service Environment settings, privately reveal `KENNY_BOOTSTRAP_TOKEN`, which Render generated during service creation. Enter it in the initial setup form with your own email and a password of at least 12 characters. Never post the token in GitHub issues or Actions logs. After setup the token no longer authorizes another administrator.

Production seeds zero stock. Update products and inventory before testing purchases; development stock is not real inventory. Payments and refunds remain manual records, with no payment gateway attached.

## Domain, storage and recovery

The service's Render HTTPS origin is automatically trusted for CSRF via `RENDER_EXTERNAL_URL`. For a custom domain, set `KENNY_ALLOWED_ORIGINS=https://your-domain.example` in Render and redeploy. Cookies require HTTPS.

Data lives at `/var/data/kenny` on the persistent disk. Never delete this disk or replace it with ephemeral storage when redeploying. Run one application instance; SQLite and the disk are not configured for horizontal scaling. Follow the database/upload backup instructions in [README.md](README.md). GitHub Actions never downloads customer data.

If a deployment fails, Actions fails rather than announcing success. Inspect the Render build/runtime logs. The script checks the live commit SHA, so an older healthy version cannot be reported as the new release. To roll back application code, revert the change on `main` and let Actions deploy the new revert commit. Data migrations and backups need separate review; code rollback does not revert database contents.
