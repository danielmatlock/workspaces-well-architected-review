# Architecture Diagram

## Current State (Offline Mode)

```mermaid
flowchart TD
    User[TAM / Reviewer] -->|HTTPS| CF[CloudFront CDN]
    CF --> S3[S3 - Static Site via Amplify Hosting]
    S3 --> Browser[Browser - index.html]
    Browser --> LS[localStorage - Reviews & Templates]
```

## Target State (Cloud Mode)

```mermaid
flowchart TD
    User[TAM / Reviewer] -->|HTTPS| CF[CloudFront CDN]
    CF --> S3[S3 - Static Site via Amplify Hosting]
    S3 --> Browser[Browser - index.html]
    
    Browser -->|Auth| Cognito[Amazon Cognito User Pool]
    Browser -->|GraphQL| AppSync[AWS AppSync API]
    AppSync --> DDB[DynamoDB - Templates & Reviews]
    Browser -->|File Export| S3Export[S3 - Report Storage]

    subgraph AWS Account 590183747733
        CF
        S3
        Cognito
        AppSync
        DDB
        S3Export
    end
```

## Deployment Pipeline

```mermaid
flowchart LR
    Dev[Developer - Local] -->|git push| GH[GitHub - main branch]
    GH -->|Manual deploy| Amplify[AWS Amplify Hosting]
    Amplify -->|Serves| CF[CloudFront]
    CF -->|Delivers| Users[End Users]
    
    GH -.->|OIDC| Role[IAM Role - github-actions-amplify-deploy]
    Role -.->|Future| CFN[CloudFormation - Backend Resources]
```

## Network Flow

```
User (Browser)
    │
    ▼ HTTPS (TLS 1.2+)
CloudFront (d1p2543h8l2mfc.amplifyapp.com)
    │
    ▼
S3 Origin (Amplify Managed)
    │
    ▼ (JavaScript in browser)
┌─────────────────────────────────────┐
│  Offline Mode: localStorage only    │
│  Cloud Mode:                        │
│    → Cognito (auth)                 │
│    → AppSync (data)                 │
│    → S3 (exports)                   │
└─────────────────────────────────────┘
```

## Services Used

| Service | Purpose | Status |
|---------|---------|--------|
| Amplify Hosting | Static site hosting + CDN | ✅ Deployed |
| CloudFront | Content delivery | ✅ Auto (via Amplify) |
| S3 | Static assets | ✅ Auto (via Amplify) |
| Cognito | User authentication | ⏳ Not yet configured |
| AppSync | GraphQL API | ⏳ Not yet configured |
| DynamoDB | Data storage (reviews, templates) | ⏳ Not yet configured |
| S3 (exports) | Report file storage | ⏳ Not yet configured |
| IAM (OIDC) | GitHub Actions → AWS auth | ✅ Configured |
