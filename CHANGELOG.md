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
- Lambda actions added: `saveReport`, `listReports`, `getReport`, `deleteReport` (presigned URLs, 5 min expiry)
- Added IAM inline policy `wafr-reports-s3` to `lambda-ses-email-role` (PutObject, GetObject, ListBucket, DeleteObject)
- "Saved Reports" button on home page review cards and review dashboard topbar
- Modal shows table with report type, timestamp, Preview (HTML), Download, and Delete buttons

### C-Level Deck: S3 Grounding & S3-Only Save
- Modal now shows dropdowns populated from saved reports in S3 (So What + WAFR reports)
- Selected reports fetched via presigned URL, HTML stripped to text, passed as AI grounding context
- Removed PDF.js library dependency (no longer needed)
- Reduces hallucinations by grounding Bedrock recommendations in actual report content
- PPTX saves to S3 only (no local file download) — user accesses via Saved Reports modal

### Delete Saved Reports
- Added Delete button (red) to Saved Reports modal for each report
- Confirm dialog before deletion to prevent accidental removal
- Lambda `deleteReport` action removes object from S3
- Modal refreshes automatically after deletion

### Rename: Standard Report → WAFR Report
- Display label in Saved Reports modal changed from "Standard Report" to "WAFR Report"
- Internal `reportType` key remains `'standard'` for backward compatibility

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

## 2026-07-20 (Dev Branch)

### Auto WAFR - AWS Account Connection & Automated Assessment
- **Connect Account** feature: connect to any AWS account via cross-account IAM role
  - CloudFormation template (`cfn/wafr-readonly-role.yaml`) for one-click role setup
  - Connect Account modal with 2-step flow (deploy template, paste Role ARN)
  - Green/red status dot on button shows connection state
  - Connection details saved to review (persisted to DynamoDB)
- **Auto WAFR** button (blue) - one-click environment scan + AI-powered report
  - Scans 20+ data sources from the connected AWS account:
    - Fleet: WorkSpaces count, protocols, running modes, encryption, states
    - Identity: Directories (AD Connector/Managed AD), MFA/RADIUS, SSO
    - Networking: VPCs, subnets, AZs, NAT Gateways, VPC Endpoints, Security Groups, Route Tables
    - Security: Encryption status, IP Access Control Groups, open SGs flagged
    - Monitoring: CloudWatch alarms, dashboards, log groups, active metrics
    - Auditing: CloudTrail trails, logging status, multi-region, log validation
    - Cost: 90-day spend breakdown by month
    - Utilisation: Connection status (identifies WorkSpaces unused 30+ days)
    - Images: Custom images, OS version, age
    - Bundles: Custom bundle compute specs
    - Governance: Tagging compliance (sampled)
    - Automation: EventBridge rules (WorkSpaces-related)
    - Backup/DR: AWS Backup plans, connection aliases
    - Patching: SSM managed instances, patch compliance
    - IAM: WorkSpaces-related roles, BYOL/tenancy config
    - Client: Reconnect settings, log upload
    - Snapshots: Rebuild/restore availability
    - Config: AWS Config compliance rules
  - Bedrock generates comprehensive assessment with:
    - Executive summary for leadership
    - Findings by WAF pillar (Observation, Recommendation, Target State, Priority, RAG)
    - AWS documentation links per finding
    - "Areas Not Assessed" section with suggested manual actions
  - Two-call architecture to avoid API Gateway 30s timeout (scan then analyse)
  - Report saved to S3 as `autowafr` type

### ORR-Specific Features
- ORR reviews show different topbar buttons (no So What, no C-Level, no Arch Info)
- **ORR Report** button (orange) - AI-powered report with 5 fields per question:
  - Observation, Recommendation, Target State, Steps to Green, Priority
- Separate Lambda handler (`generateOrr` action) with ORR-specific Bedrock prompt
- ORR prompt grounded in ORR Best Practices (failure modeling, operational processes, etc.)
- All answered questions sent to Bedrock (not just those with notes)

### C-Level Deck Redesign
- Complete rewrite of `buildCuratedCLevelPptx` to match manual Executive Briefing:
  - Cover: dark Squid Ink + orange left accent bar + "Must/Should/Could conversation"
  - Executive Summary: single paragraph text + 2x2 KPI stat boxes (aligned)
  - Scorecard: horizontal RAG bars sorted highest to lowest, 70%+ = green
  - Critical Findings: 2x2 card grid with colored top accents
  - Must/Should/Could: 3 equal columns with colored header bands + flow arrow
  - Quick Wins: 2x2 cards with green accents + effort pill badges (colored shapes)
  - Avoidable Crises: side-by-side cards + "NEEDS MORE RESEARCH" callout
  - SHOULD: 3x2 card grid + amber effort badges
  - COULD: 2x2 card grid + effort badges
  - Cost: table + "Needs more research" sidebar callout
  - 90-Day Roadmap: 4 equal columns (This Week/30/60/90 Days) + "THE ASK" bar
  - Closing: dark background with "Where do we start?"
- Fuzzy deduplication on roadmap items (first 4 words matching)
- Scorecard sorted highest to lowest, 70%+ threshold for green

### So What Report Enhancements
- Added **"What this means for users"** field (end-user impact perspective)
- Bedrock prompt now generates 3 fields: observation, recommendation, userImpact
- Blue-accented box in report for user impact section

### UI Improvements
- **My Reviews grouped by template type**: "Amazon WorkSpaces WAFR" (orange) and "Operational Readiness Review - ORR" (blue) sections
- **Version bumped to v4.1**
- Saved reports sorted: So What > Auto WAFR > ORR > C-Level > WAFR
- Type labels updated across all report displays

### Encoding Fixes
- Fixed `a` character corruption in So What report (em dashes replaced with HTML entities)
- Added `sanitizeForHTML()` for AI-generated content
- Fixed emoji icons in Architecture Assessment (replaced with HTML entities)
- Customer name sanitised in report headings
- Saved reports from S3 sanitised on retrieval

### DynamoDB Sync Optimisation
- `saveReviews()` no longer syncs ALL reviews on every change
- `updateReview()` syncs only the specific changed review
- Import review flow now explicitly syncs to DynamoDB

### Deployment Infrastructure
- Dev/prod environment separation (Amplify `dev` branch, `wafr-email-report-dev` Lambda)
- Amplify custom rewrite rule for root URL routing
- Updated DEPLOYMENT.md with troubleshooting (rewrite rules, stuck jobs, private repo)
- Cognito SES email configuration documented

### AWS Resources (Dev Environment)
| Resource | Identifier | Region |
|----------|-----------|--------|
| Amplify Branch | `dev` | eu-west-2 |
| Lambda Function | `wafr-email-report-dev` (300s, 256MB) | eu-west-2 |
| API Gateway (HTTP) | `6m3zxv0zxa` | eu-west-2 |
| S3 Bucket | `wafr-reports-danmmat-dev` | eu-west-2 |
| CFN Template | `cfn/wafr-readonly-role.yaml` | - |
| Cross-Account Role | `WAFRReviewToolReadOnly` (in customer account) | - |

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
