# Deployment Guide — WorkSpaces WAFR Tool

## App Details
- **Amplify App ID:** `d1p2543h8l2mfc`
- **Region:** `eu-west-2`
- **Account:** `590183747733`
- **GitHub Repo:** `danielmatlock/workspaces-well-architected-review` (public)

### Environments

| | Production | Development |
|--|-----------|-------------|
| **Branch** | `main` | `dev` |
| **URL** | https://main.d1p2543h8l2mfc.amplifyapp.com | https://dev.d1p2543h8l2mfc.amplifyapp.com |
| **API Gateway** | `6ylrfwa3d8` | Created by `dev-setup.sh` |
| **Lambda (email/report)** | `wafr-email-report` | `wafr-email-report-dev` |
| **Lambda (explain)** | `wafr-explain` | `wafr-explain-dev` |
| **AppSync** | `zernxhslmvhe3o7ucljc55dmjq` | Created by `dev-setup.sh` |
| **DynamoDB** | `wafr-reviews`, `wafr-templates` | `wafr-reviews-dev`, `wafr-templates-dev` |
| **S3 (reports)** | `wafr-reports-danmmat-9219112` | `wafr-reports-danmmat-dev` |

### Shared Resources (not duplicated)

| Resource | Details |
|----------|---------|
| **Cognito User Pool** | `eu-west-2_Wy0eJHyN3` — single pool, access controlled by groups |
| **Bedrock** | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` (stateless) |
| **SES** | `danmmat@amazon.co.uk` sender (sandbox) |

### Access Control (Cognito Groups)

| Group | Access |
|-------|--------|
| `Admins` | Both dev and production |
| `Dev` | Development environment only |
| `Prod` | Production environment only |

Users are assigned to groups. The frontend checks group membership on login and blocks access if the user isn't in the appropriate group for that environment.

**Manage groups:**
```bash
# Add user to a group
aws cognito-idp admin-add-user-to-group --user-pool-id eu-west-2_Wy0eJHyN3 --username USER_EMAIL --group-name Admins --region eu-west-2

# Remove user from a group
aws cognito-idp admin-remove-user-from-group --user-pool-id eu-west-2_Wy0eJHyN3 --username USER_EMAIL --group-name Dev --region eu-west-2

# List users in a group
aws cognito-idp list-users-in-group --user-pool-id eu-west-2_Wy0eJHyN3 --group-name Prod --region eu-west-2
```

## Prerequisites
- AWS CloudShell (open in **eu-west-2** region)
- GitHub repo is public: `danielmatlock/workspaces-well-architected-review`

---

## Initial Dev Environment Setup (One-Time)

Run the setup script in CloudShell to create all dev resources:

```bash
curl -o /tmp/dev-setup.sh https://raw.githubusercontent.com/danielmatlock/workspaces-well-architected-review/main/scripts/dev-setup.sh
chmod +x /tmp/dev-setup.sh
/tmp/dev-setup.sh
```

This creates: Cognito groups, dev S3 bucket, dev DynamoDB tables, dev Lambda functions, dev API Gateway, dev AppSync API, and Amplify `dev` branch.

After running, the script outputs the dev API Gateway ID and AppSync URL. **Update `src/index.html`** on the `dev` branch — replace the `DEV_API_ID` and `DEV_APPSYNC_ID` placeholders in the ENV config block with the real values.

---

## How Updates Work

This app uses a **dev → production** promotion workflow:

### Development Workflow

1. **Create/switch to the `dev` branch** for all new work:
   ```bash
   cd ~/Scripts/Github/workspaces-well-architected-review
   git checkout dev
   ```

2. **Make your changes** to `src/index.html` or `lambda/wafr-email-report.py`

3. **Push to GitHub:**
   ```bash
   git add -A
   git commit -m "description of what changed"
   git push
   ```

4. **Deploy to dev environment** — either:
   - **Automatic:** GitHub Actions auto-deploys when `src/` or `lambda/` files change on the `dev` branch
   - **Manual (CloudShell):** Run the deploy commands below using the `dev` branch

5. **Test** at https://dev.d1p2543h8l2mfc.amplifyapp.com

### Promoting to Production

When you're happy with the dev version:

1. **Merge dev into main:**
   ```bash
   git checkout main
   git merge dev
   git push
   ```

2. **Deploy to production** — either:
   - **Automatic:** GitHub Actions auto-deploys when `main` is updated
   - **Manual (CloudShell):** Run the deploy commands below using the `main` branch

3. **Verify** at https://main.d1p2543h8l2mfc.amplifyapp.com

### Manual Deployment via GitHub Actions

You can also trigger a deploy manually from the GitHub Actions tab:
1. Go to https://github.com/danielmatlock/workspaces-well-architected-review/actions
2. Select "Deploy WorkSpaces WAFR Tool"
3. Click "Run workflow" and choose `dev` or `production`

---

## Deploy Frontend (index.html → Amplify)

Run in CloudShell (replace `BRANCH` with `dev` or `main`):

```bash
BRANCH=dev  # or: BRANCH=main (for production)

rm -f /tmp/deploy.zip /tmp/index.html
curl -o /tmp/index.html https://raw.githubusercontent.com/danielmatlock/workspaces-well-architected-review/$BRANCH/src/index.html
cd /tmp && zip deploy.zip index.html
DEPLOY=$(aws amplify create-deployment --app-id d1p2543h8l2mfc --branch-name $BRANCH --region eu-west-2 --output json)
UPLOAD_URL=$(echo $DEPLOY | python3 -c "import sys,json; print(json.load(sys.stdin)['zipUploadUrl'])")
JOB_ID=$(echo $DEPLOY | python3 -c "import sys,json; print(json.load(sys.stdin)['jobId'])")
curl -T /tmp/deploy.zip "$UPLOAD_URL"
aws amplify start-deployment --app-id d1p2543h8l2mfc --branch-name $BRANCH --job-id $JOB_ID --region eu-west-2
```

### Important Notes
- The zip must contain `index.html` at the **root** (NOT inside a `src/` folder)
- Always `rm -f /tmp/deploy.zip` first to avoid stale zip contents
- Deployment takes ~30 seconds to go live

---

## Deploy Lambda (wafr-email-report.py)

Run in CloudShell (replace `BRANCH` and `FUNCTION_NAME` for dev or prod):

```bash
BRANCH=dev                        # or: BRANCH=main
FUNCTION_NAME=wafr-email-report-dev  # or: FUNCTION_NAME=wafr-email-report

curl -o /tmp/wafr-email-report.py https://raw.githubusercontent.com/danielmatlock/workspaces-well-architected-review/$BRANCH/lambda/wafr-email-report.py
cd /tmp && zip lambda.zip wafr-email-report.py
aws lambda update-function-code --function-name $FUNCTION_NAME --zip-file fileb:///tmp/lambda.zip --region eu-west-2
```

### Lambda Environment Variables

The dev Lambda uses environment variables to point at dev resources:

| Variable | Dev Value | Prod Value (default fallback) |
|----------|-----------|-------------------------------|
| `REPORTS_BUCKET` | `wafr-reports-danmmat-dev` | `wafr-reports-danmmat-9219112` |
| `SENDER_EMAIL` | `danmmat@amazon.co.uk` | `danmmat@amazon.co.uk` |
| `MODEL_ID` | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` |

Production Lambda doesn't need env vars set — it falls back to hardcoded defaults.

---

## Workflow Summary

| What changed | Dev deploy | Prod deploy |
|-------------|-----------|-------------|
| `src/index.html` | Push to `dev` → auto-deploys (or run CloudShell frontend commands with `BRANCH=dev`) | Merge `dev` → `main` → auto-deploys (or run CloudShell with `BRANCH=main`) |
| `lambda/wafr-email-report.py` | Push to `dev` → auto-deploys to `wafr-email-report-dev` (or run CloudShell lambda commands) | Merge `dev` → `main` → auto-deploys to `wafr-email-report` (or run CloudShell) |

**Quick reference:**
1. Work on `dev` branch → push → test at https://dev.d1p2543h8l2mfc.amplifyapp.com
2. Happy? → `git checkout main && git merge dev && git push`
3. Verify production at https://main.d1p2543h8l2mfc.amplifyapp.com

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 404 after deploy | Zip structure wrong — must be `index.html` at root, not nested in `src/` |
| 404 on root URL `/` but `/index.html` works | Rewrite rules missing or lost — see "Rewrite Rules" section below |
| Empty zip | CloudShell session expired — re-curl the file from GitHub |
| Pending job blocking new deploy | Stop it: `aws amplify stop-job --app-id d1p2543h8l2mfc --branch-name main --job-id <JOB_ID> --region eu-west-2` |
| curl from GitHub returns 404 | Repo may be private — ensure it's public, or clone via `git clone` in CloudShell |
| Lambda timeout | Current timeout is 90s, memory 256MB — increase if Bedrock calls grow |
| Amplify not updating | Check `Last updated` in Amplify console — ensure job status is "Succeed" |

---

## Rewrite Rules

Amplify requires a custom rewrite rule to serve `index.html` when accessing the root URL `/`. This was added on 2026-07-14 after a 404 occurred on the root path.

**Current rule:**
```json
[{"source": "/<*>", "target": "/index.html", "status": "200"}]
```

This routes all paths to `index.html`. If this rule is ever lost (e.g. app recreated), restore it with:

```bash
aws amplify update-app --app-id d1p2543h8l2mfc --region eu-west-2 --custom-rules '[{"source": "/<*>", "target": "/index.html", "status": "200"}]'
```

Then redeploy for the rule to take effect.

---

## Stuck/Pending Deployments

If a deployment fails mid-way (e.g. zip upload didn't complete), it leaves a pending job that blocks new deployments.

**Diagnose:**
```bash
aws amplify list-jobs --app-id d1p2543h8l2mfc --branch-name main --region eu-west-2 --max-items 3
```

**Fix — cancel the stuck job:**
```bash
aws amplify stop-job --app-id d1p2543h8l2mfc --branch-name main --job-id <JOB_ID> --region eu-west-2
```

Then re-run the deploy commands.
