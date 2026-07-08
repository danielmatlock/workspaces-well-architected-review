---
inclusion: auto
---

# WorkSpaces WAFR Tool — Deployment Process

After any code changes are committed and pushed to GitHub, remind the user to deploy using CloudShell (eu-west-2). The deployment is NOT automatic from GitHub — it requires manual steps.

## Frontend (index.html changed)

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

## Lambda (lambda/wafr-email-report.py changed)

```bash
curl -o /tmp/wafr-email-report.py https://raw.githubusercontent.com/danielmatlock/workspaces-well-architected-review/main/lambda/wafr-email-report.py
cd /tmp && zip lambda.zip wafr-email-report.py
aws lambda update-function-code --function-name wafr-email-report --zip-file fileb:///tmp/lambda.zip --region eu-west-2
```

## Key Rules

- The zip for Amplify must contain `index.html` at the ROOT (not inside `src/`)
- Always `rm -f /tmp/deploy.zip` first to avoid stale contents
- App URL: https://main.d1p2543h8l2mfc.amplifyapp.com
- No local AWS credentials — must use CloudShell
- After `git push`, always ask: "Ready to deploy to Amplify/Lambda via CloudShell?"
