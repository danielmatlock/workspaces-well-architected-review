# WorkSpaces Well-Architected Review

Custom app for conducting AWS WorkSpaces Well-Architected Framework Reviews.

## Architecture

- **Frontend:** Single-page HTML app
- **Auth:** Amazon Cognito
- **API:** AWS AppSync (GraphQL)
- **Database:** DynamoDB
- **Storage:** S3 (exported reports)
- **Hosting:** AWS Amplify
- **Account:** 590183747733
- **Region:** eu-west-2

## Deployment

Deployed via GitHub Actions (manual trigger only). Uses OIDC federation — no long-lived credentials.

To deploy: Actions tab → "Deploy WorkSpaces WAFR Amplify App" → Run workflow

## Changelog

| Date | Change |
|------|--------|
| 2025-06-15 | Initial repo setup, Amplify app imported, GitHub Actions workflow created (paused) |
| 2025-06-15 | OIDC role created in 590183747733 (`github-actions-amplify-deploy`), scoped to this repo + main branch only |
| 2026-06-15 | App deployed to Amplify Hosting (manual deployment, app ID: `d1p2543h8l2mfc`) |
| 2026-06-15 | Cognito auth configured (User Pool: `eu-west-2_Wy0eJHyN3`) |
| 2026-06-15 | AppSync API + DynamoDB tables created for cloud storage (`wafr-templates`, `wafr-reviews`) |
| 2026-06-15 | Fixed multiline string syntax error (line 1045) |
| 2025-06-15 | Cognito user added: Andrew Wood (anwod@amazon.co.uk) |
