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
