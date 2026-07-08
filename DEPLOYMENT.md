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
| Empty zip | CloudShell session expired — re-curl the file from GitHub |
| Lambda timeout | Current timeout is 90s, memory 256MB — increase if Bedrock calls grow |
| Amplify not updating | Check `Last updated` in Amplify console — ensure job status is "Succeed" |
