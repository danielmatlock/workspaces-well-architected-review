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
| 2025-06-23 | Fixed: deleteReview now removes from DynamoDB (not just localStorage) |
| 2025-06-23 | Fixed: cloud sync replaces local cache (deletions in DynamoDB reflected immediately) |
| 2025-06-29 | Removed AWS Systems Manager Distributor from OPS-WS-09 best practice |
| 2025-06-29 | AI Guidance panel: "What to ask the customer" renamed to "Questions to think about" in responses |
| 2025-06-29 | Email Report feature added (SES + Lambda, sender: danmmat@amazon.co.uk) |
| 2025-07-02 | Tailored AI recommendations added to reports (Bedrock generates context-aware guidance based on notes) |
| 2025-07-02 | Print Report and Email Report buttons added to question view topbar |
| 2025-07-02 | Professional Observations rewrite: Lambda sends reviewer notes to Bedrock Claude Haiku, returns `{observation, recommendation}` per question |
| 2025-07-02 | Report rendering updated: Observations box shows Bedrock-rewritten prose; Tailored Recommendation box shows bullets + clickable Further Reading URLs (falls back to raw notes if Bedrock unavailable) |
| 2025-07-06 | CSV import from Excel spreadsheet added to New Review modal (columns: ID, Pillar, Question, Info from Customer, Best Practice) |
| 2025-07-06 | Fixed cloud sync: gql now throws on GraphQL errors; upsert logic tries createReview then falls back to updateReview on conflict |
| 2025-07-06 | Added Sync Log panel: timestamped DynamoDB events (create/update/load/error) accessible via sidebar footer |
| 2025-07-07 | Fixed report generation: parse API Gateway body wrapper so Bedrock recommendations render correctly |
| 2025-07-07 | Lambda parallelised: questions batched (5 per batch) with ThreadPoolExecutor to avoid API Gateway 29s timeout |
| 2025-07-07 | Lambda config: timeout increased to 90s, memory to 256MB |
| 2025-07-07 | Frontend batching: sends 5 questions per API call (sequential) to stay within API Gateway 29s limit |
| 2025-07-07 | So What Report: focused executive report showing only Bedrock observations and recommendations with AWS doc links (no RAG colours or Target State sections) |
| 2025-07-07 | So What Report: focused executive report showing only Bedrock observations and recommendations with AWS doc links (no RAG colours or Target State sections) |
