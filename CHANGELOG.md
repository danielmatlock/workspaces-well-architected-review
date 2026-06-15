# Changelog

All notable changes to this project are documented in this file.

## 2026-06-15

### Infrastructure Setup
- Created GitHub repo `danielmatlock/workspaces-well-architected-review`
- Created OIDC identity provider in AWS account `590183747733` for GitHub Actions
- Created IAM role `github-actions-amplify-deploy` scoped to this repo + main branch only
- Created GitHub Actions workflow (manual dispatch only, paused)
- Created Amplify Hosting app (`d1p2543h8l2mfc`) in eu-west-2
- Deployed app via manual zip upload (presigned URL method)

### Authentication
- Created Cognito User Pool `wafr-users` (`eu-west-2_Wy0eJHyN3`)
- Created app client `wafr-web` (`1kj98mt2cjbci4sa9okfg4o5dk`)
- Created user `danmmat@amazon.co.uk`
- Replaced non-functional Amplify v6 UMD bundle with `amazon-cognito-identity-js` CDN
- Auth uses SRP authentication with JWT token for API calls

### Cloud Storage (AppSync + DynamoDB)
- Created DynamoDB table `wafr-reviews` (PAY_PER_REQUEST)
- Created DynamoDB table `wafr-templates` (PAY_PER_REQUEST)
- Enabled Point-in-Time Recovery (PITR) on both tables
- Created IAM role `appsync-dynamodb-role` for AppSync → DynamoDB access
- Created AppSync GraphQL API `wafr-api` (`4up36qgqubd6tcuekx5cmexmii`)
- Created schema with Template and Review types + CRUD operations
- Created data sources: `TemplatesTable`, `ReviewsTable`
- Created resolvers for all Query and Mutation fields
- Fixed `createReview` resolver — replaced manual attribute mapping with `$util.dynamodb.toMapValuesJson`

### AI Guidance (Bedrock via Lambda + API Gateway)
- Created IAM role `lambda-bedrock-role` with Bedrock InvokeModel permissions
- Created Lambda function `wafr-explain` (Python 3.12, 30s timeout)
- Uses `eu.anthropic.claude-haiku-4-5-20251001-v1:0` (EU inference profile)
- Prompt generates concise TAM review guidance (max 512 tokens)
- Created API Gateway HTTP API `wafr-explain-api` (`6ylrfwa3d8`)
- Route: `POST /explain` → Lambda integration
- CORS enabled (all origins, POST/OPTIONS)
- API endpoint: `https://6ylrfwa3d8.execute-api.eu-west-2.amazonaws.com/explain`

### App Fixes
- Fixed multiline string syntax error on line 1045 (single quote → backtick)
- Fixed SUS-WS-05 question — removed appended reference/appendix content from best practice answer
- Fixed cloud sync — replaced `amplifyClient.graphql()` with direct `fetch()` to AppSync endpoint
- Fixed `loadFromCloud` — handles answers as objects (DynamoDB Map type) not just strings
- Fixed `loadFromCloud` — attaches `pillars` from matching template so reviews render correctly
- Fixed field name mapping between app (`customer`, `reviewer`, `date`) and DynamoDB (`customerName`, `reviewerName`, `reviewDate`)

### UI Improvements
- Added expandable pillar breakdown on home page review cards (▸ toggle)
- Fixed sidebar pillar score alignment — `progress-text` now fixed-width and right-aligned
- Added expandable question list per pillar in sidebar (▸ arrow expands question IDs)
- Answered questions highlighted green in sidebar list
- Added AI Guidance panel to the right of each question (auto-loads from Bedrock)
- Panel minimise/expand button keeps panel width, only hides/shows content

### Documentation
- Created `docs/ARCHITECTURE.md` with Mermaid diagrams (updated with all services)
- Created `docs/AMPLIFY-SETUP.md` (original Amplify deployment guide)
- Created `CHANGELOG.md` (this file)
- Updated `README.md` with changelog summary

## Deployment Process (Current)

Since Amplify CI/CD with GitHub isn't working (IAM service role issue), deployments are manual:

1. Make changes locally to `src/index.html`
2. `cd src && zip -r /tmp/wafr-deploy.zip .`
3. `git add -A && git commit -m "message" && git push origin main`
4. In CloudShell: `aws amplify create-deployment --app-id d1p2543h8l2mfc --branch-name main --region eu-west-2`
5. From Mac: `curl -T /tmp/wafr-deploy.zip '<PRESIGNED_URL>'`
6. In CloudShell: `aws amplify start-deployment --app-id d1p2543h8l2mfc --branch-name main --job-id <JOB_ID> --region eu-west-2`

## Known Issues

- Amplify CI/CD via GitHub not functional — "Unable to assume specified IAM Role" even with service-linked role. Using manual deployment as workaround.
- GitHub personal access token has limited scope — webhook permissions required for repo connection.
- Claude 3 Haiku/Sonnet base model IDs don't work on-demand — must use inference profile IDs (e.g. `eu.anthropic.claude-haiku-4-5-20251001-v1:0`).
- `amplify-service-role` IAM role exists but is unused (Amplify CI/CD not working).

## AWS Resources Summary

| Resource | Identifier | Region |
|----------|-----------|--------|
| Amplify App | `d1p2543h8l2mfc` | eu-west-2 |
| Cognito User Pool | `eu-west-2_Wy0eJHyN3` | eu-west-2 |
| Cognito Client | `1kj98mt2cjbci4sa9okfg4o5dk` | eu-west-2 |
| AppSync API | `4up36qgqubd6tcuekx5cmexmii` | eu-west-2 |
| DynamoDB Table | `wafr-reviews` | eu-west-2 |
| DynamoDB Table | `wafr-templates` | eu-west-2 |
| Lambda Function | `wafr-explain` | eu-west-2 |
| API Gateway | `6ylrfwa3d8` | eu-west-2 |
| IAM Role | `github-actions-amplify-deploy` | global |
| IAM Role | `appsync-dynamodb-role` | global |
| IAM Role | `lambda-bedrock-role` | global |
| IAM Role | `amplify-service-role` | global |
| Bedrock Model | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` | eu-west-2 |
