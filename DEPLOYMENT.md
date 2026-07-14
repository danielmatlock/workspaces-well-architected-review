# Deployment Guide — WorkSpaces WAFR Tool

## App Details
- **Amplify App ID:** `d1p2543h8l2mfc`
- **Branch:** `main`
- **Region:** `eu-west-2`
- **URL:** https://main.d1p2543h8l2mfc.amplifyapp.com
- **Lambda Function:** `wafr-email-report` (eu-west-2)
- **S3 Bucket:** `wafr-reports-danmmat-9219112` (eu-west-2) — auto-saved reports
- **Lambda Role:** `lambda-ses-email-role` (inline policy `wafr-reports-s3`: PutObject, GetObject, ListBucket, DeleteObject)

## Prerequisites
- AWS CloudShell (open in **eu-west-2** region)
- GitHub repo is public: `danielmatlock/workspaces-well-architected-review`

---

## Deploy Frontend (index.html → Amplify)

Run in CloudShell:

```bash
rm -f /tmp/deploy.zip /tmp/index.html
curl -o /tmp/index.html https://raw.githubusercontent.com/danielmatlock/workspaces-well-architected-review/main/src/index.html
cd /tmp && zip deploy.zip index.html
DEPLOY=$(aws amplify create-deployment --app-id d1p2543h8l2mfc --branch-name main --region eu-west-2 --output json)
UPLOAD_URL=$(echo $DEPLOY | python3 -c "import sys,json; print(json.load(sys.stdin)['zipUploadUrl'])")
JOB_ID=$(echo $DEPLOY | python3 -c "import sys,json; print(json.load(sys.stdin)['jobId'])")
curl -T /tmp/deploy.zip "$UPLOAD_URL"
aws amplify start-deployment --app-id d1p2543h8l2mfc --branch-name main --job-id $JOB_ID --region eu-west-2
```

### Important Notes
- The zip must contain `index.html` at the **root** (NOT inside a `src/` folder)
- Always `rm -f /tmp/deploy.zip` first to avoid stale zip contents
- Deployment takes ~30 seconds to go live

---

## Deploy Lambda (wafr-email-report.py)

Run in CloudShell:

```bash
curl -o /tmp/wafr-email-report.py https://raw.githubusercontent.com/danielmatlock/workspaces-well-architected-review/main/lambda/wafr-email-report.py
cd /tmp && zip lambda.zip wafr-email-report.py
aws lambda update-function-code --function-name wafr-email-report --zip-file fileb:///tmp/lambda.zip --region eu-west-2
```

---

## Workflow Summary

1. Make changes locally on Mac (`~/Scripts/Github/workspaces-well-architected-review/`)
2. `git add -A && git commit -m "message" && git push`
3. Open CloudShell in eu-west-2
4. Run frontend deploy commands (if `index.html` changed)
5. Run Lambda deploy commands (if `lambda/wafr-email-report.py` changed)
6. Verify at https://main.d1p2543h8l2mfc.amplifyapp.com

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
