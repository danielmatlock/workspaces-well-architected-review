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

## 2025-06-29

### Template Updates
- Removed AWS Systems Manager Distributor from OPS-WS-09 best practice
- AI Guidance panel: "What to ask the customer" renamed to "Questions to think about" in responses

### Email Report Feature
- Created IAM role `lambda-ses-email-role` with SES + Bedrock permissions
- Created Lambda function `wafr-email-report` (Python 3.12, 90s timeout, 256MB)
- Added SES email sending (sender: danmmat@amazon.co.uk, sandbox mode)
- Added Email Report button to question view topbar

## 2025-07-02

### Professional Observations Rewrite
- Lambda sends reviewer notes to Bedrock Claude Haiku, returns `{observation, recommendation}` per question
- Report rendering: grey Observations box shows Bedrock-rewritten prose
- Report rendering: blue Tailored Recommendation box shows bullets + clickable Further Reading URLs
- Falls back to raw notes if Bedrock unavailable

### UI Updates
- Print Report and Email Report buttons added to question view topbar
- Cognito user added: Andrew Wood (anwod@amazon.co.uk)

## 2025-07-06

### CSV Import
- Added "Import from Spreadsheet" file picker to New Review modal
- Parses CSV columns: ID, Pillar, Question, Assessment Status, Info from Customer, Best Practice
- Maps Assessment Status to internal scores (fully/partial/not/na)

### Cloud Sync Fixes
- Fixed `gql` helper to throw on GraphQL errors
- Fixed upsert logic: tries `createReview` first, falls back to `updateReview` on ConditionalCheckFailed

### Sync Log Panel
- Added floating log panel accessible via "Sync Log" button in sidebar footer
- Shows timestamped DynamoDB events (create/update/load/error)

## 2025-07-07

## 2025-07-07

### Saved Reports (S3 Auto-Save)
- All three report types (Standard, So What, C-Level Deck) now auto-save to S3 after generation
- Created S3 bucket `wafr-reports-danmmat-9219112` (eu-west-2)
- Lambda actions added: `saveReport`, `listReports`, `getReport` (presigned URLs, 5 min expiry)
- Added IAM inline policy `wafr-reports-s3` to `lambda-ses-email-role`
- "Saved Reports" button on home page review cards and review dashboard topbar
- Modal shows table with report type, timestamp, Preview (HTML) and Download buttons

### C-Level Deck: S3 Grounding (replaces local PDF upload)
- Modal now shows dropdowns populated from saved reports in S3 (So What + Standard)
- Selected reports fetched via presigned URL, HTML stripped to text, passed as AI grounding context
- Removed PDF.js library dependency (no longer needed)
- Reduces hallucinations by grounding Bedrock recommendations in actual report content

### Report Generation Fixes
- Fixed API Gateway body wrapper parsing (`data.body` is a JSON string)
- Lambda parallelised: questions batched (5 per batch) with ThreadPoolExecutor (4 workers)
- Lambda config: timeout increased to 90s, memory to 256MB
- Frontend batching: sends 5 questions per API call (sequential) to stay within API Gateway 29s limit

### So What Report
- Added "So What Report" button (orange, btn-primary) to review summary page and question view topbar
- Generates focused executive report: only Bedrock observations ("What we found") and recommendations ("What to do")
- No RAG colours, Target State, or To Reach Green sections
- Includes clickable AWS documentation links
- Print/Close buttons at top (hidden when printing via @media print)
- Reuses cached `window._lastRecommendations` from last report generation

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
| Lambda Function | `wafr-explain` (30s, 128MB) | eu-west-2 |
| Lambda Function | `wafr-email-report` (90s, 256MB) | eu-west-2 |
| S3 Bucket | `wafr-reports-danmmat-9219112` | eu-west-2 |
| API Gateway | `6ylrfwa3d8` | eu-west-2 |
| IAM Role | `github-actions-amplify-deploy` | global |
| IAM Role | `appsync-dynamodb-role` | global |
| IAM Role | `lambda-bedrock-role` | global |
| IAM Role | `lambda-ses-email-role` | global |
| IAM Role | `amplify-service-role` | global |
| Bedrock Model | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` | eu-west-2 |
