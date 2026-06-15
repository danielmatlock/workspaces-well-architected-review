# WorkSpaces WAFR Tool — AWS Amplify Deployment Guide

## Overview

This is the cloud-hosted version of the Amazon WorkSpaces Well-Architected Framework Review tool. It adds:

- **User authentication** (Cognito) — each TAM has their own account
- **Cloud storage** (DynamoDB via AppSync) — reviews and templates stored centrally
- **File storage** (S3) — exported reports stored in the cloud
- **Offline fallback** — works with localStorage when cloud is unavailable
- **Multi-user** — each user sees their own reviews; shared templates available to all

## Architecture

```
CloudFront (via Amplify Hosting)
        │
        ▼
   S3 (Static site — index.html)
        │
        ▼
   Cognito (User authentication)
        │
        ▼
   AppSync (GraphQL API)
        │
        ▼
   DynamoDB (Templates + Reviews tables)
        │
   S3 (Exported report storage)
```

## Prerequisites

- **Node.js** v18+ and npm
- **AWS CLI** configured with appropriate credentials
- **Amplify CLI** v12+

```bash
npm install -g @aws-amplify/cli
amplify configure
```

When running `amplify configure`, select:
- Region: `eu-west-2` (or your preferred region)
- Create a new IAM user for Amplify (follow the prompts)

## Step-by-Step Setup

### 1. Clone/copy this folder

```bash
cd ~/projects
cp -r /path/to/workspaces-wafr-amplify .
cd workspaces-wafr-amplify
npm install
```

### 2. Initialise Amplify

```bash
amplify init
```

When prompted:
- **Project name:** `wafrapp`
- **Environment:** `dev`
- **Default editor:** Visual Studio Code (or your preference)
- **App type:** JavaScript
- **Framework:** None
- **Source directory:** `src`
- **Distribution directory:** `src`
- **Build command:** (leave empty)
- **Start command:** `npx serve src`

### 3. Add Authentication (Cognito)

```bash
amplify add auth
```

When prompted:
- **Default configuration** or Manual? → Default configuration
- **How do you want users to sign in?** → Email
- **Do you want to configure advanced settings?** → No

### 4. Add API (AppSync + DynamoDB)

```bash
amplify add api
```

When prompted:
- **Select service type:** GraphQL
- **API name:** `wafrapi`
- **Authorisation type:** Amazon Cognito User Pool
- **Additional auth types?** → No
- **Schema template:** → Choose "Blank Schema"
- **Edit schema now?** → Yes

The schema file will open. It should already contain the correct schema from `amplify/backend/api/wafrapi/schema.graphql`. If not, paste:

```graphql
type Template @model @auth(rules: [{allow: owner}, {allow: groups, groups: ["Admins"], operations: [create, update, delete, read]}]) {
  id: ID!
  name: String!
  description: String
  pillars: AWSJSON!
  isDefault: Boolean
  createdBy: String!
  createdAt: AWSDateTime!
  updatedAt: AWSDateTime!
}

type Review @model @auth(rules: [{allow: owner}]) {
  id: ID!
  templateId: String!
  templateName: String!
  customerName: String!
  reviewerName: String!
  reviewDate: String!
  answers: AWSJSON!
  notes: AWSJSON!
  status: String!
  overallScore: Float
  pillarScores: AWSJSON
  createdAt: AWSDateTime!
  updatedAt: AWSDateTime!
}
```

### 5. Add Storage (S3 — for exported reports)

```bash
amplify add storage
```

When prompted:
- **Content (Images, audio, video, etc.)** → Yes
- **Bucket name:** `wafrreports`
- **Who should have access?** → Auth users only
- **What access?** → create/update, read, delete

### 6. Deploy the Backend

```bash
amplify push
```

This creates all the AWS resources (Cognito user pool, AppSync API, DynamoDB tables, S3 bucket). It takes 3-5 minutes.

### 7. Configure the Frontend

After `amplify push`, a file called `src/aws-exports.js` (or `amplifyconfiguration.json`) is generated. Open `src/index.html` and update the `amplifyConfig` object near the top of the `<script>` block with your actual values:

```javascript
var amplifyConfig = {
  Auth: {
    Cognito: {
      userPoolId: 'eu-west-2_XXXXXXX',        // from aws-exports
      userPoolClientId: 'XXXXXXXXXXXXXXXXX',    // from aws-exports
      identityPoolId: 'eu-west-2:XXXX-XXXX'   // from aws-exports
    }
  },
  API: {
    GraphQL: {
      endpoint: 'https://XXXXX.appsync-api.eu-west-2.amazonaws.com/graphql',
      region: 'eu-west-2',
      defaultAuthMode: 'userPool'
    }
  },
  Storage: {
    S3: {
      bucket: 'wafrreportsXXXXX-dev',
      region: 'eu-west-2'
    }
  }
};
```

### 8. Deploy the Frontend (Hosting)

```bash
amplify add hosting
```

When prompted:
- **Plugin module:** Hosting with Amplify Console
- **Type:** Manual deployment

Then:

```bash
amplify publish
```

This deploys your frontend to Amplify Hosting with a CloudFront URL.

### 9. Access Your App

After `amplify publish`, you'll get a URL like:
```
https://dev.XXXXXXXXXX.amplifyapp.com
```

Share this with your team!

## Managing Users

### Create an Admin user

```bash
# Add user to Admins group (can edit shared templates)
aws cognito-idp admin-add-user-to-group \
  --user-pool-id eu-west-2_XXXXXXX \
  --username user@email.com \
  --group-name Admins
```

### Create the Admins group first

```bash
aws cognito-idp create-group \
  --user-pool-id eu-west-2_XXXXXXX \
  --group-name Admins \
  --description "WAFR Tool administrators — can manage shared templates"
```

## How It Works

| Feature | Offline Mode | Cloud Mode |
|---------|-------------|------------|
| Templates | localStorage | DynamoDB (shared) |
| Reviews | localStorage | DynamoDB (per-user) |
| Export JSON | Download file | Download file + S3 backup |
| Multi-user | No | Yes — each user sees their own reviews |
| Shared templates | No | Yes — Admins create, all users read |
| Auth | Skip (offline button) | Cognito email/password |

The app always saves to localStorage first (instant), then syncs to the cloud in the background. If the cloud is unavailable, localStorage is the source of truth.

## Folder Structure

```
workspaces-wafr-amplify/
├── amplify/
│   └── backend/
│       └── api/
│           └── wafrapi/
│               └── schema.graphql    ← DynamoDB data model
├── src/
│   └── index.html                    ← Main app (single file)
├── amplify.yml                       ← Amplify build spec
├── package.json                      ← Dependencies
└── README.md                         ← This file
```

## Updating the App

To make changes:

1. Edit `src/index.html`
2. Test locally: `npx serve src` → open `http://localhost:3000`
3. Deploy: `amplify publish`

## Custom Domain

To add a custom domain (e.g., `wafr.yourdomain.com`):

1. Go to the Amplify Console in AWS
2. Select your app → Domain management
3. Add your domain and follow the DNS verification steps

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Amplify not configured" in console | Update `amplifyConfig` in index.html with values from aws-exports |
| Login fails | Check Cognito user pool settings; ensure email verification is enabled |
| Data not syncing | Check AppSync console for errors; verify auth rules in schema |
| Can't create templates | User needs to be in the "Admins" group |
| Reviews not loading | Check DynamoDB table in AWS console; verify owner auth rule |

## Costs

This setup uses AWS Free Tier-eligible services:
- **Cognito:** 50,000 MAU free
- **AppSync:** 250,000 queries/month free
- **DynamoDB:** 25 GB free storage, 25 WCU/RCU free
- **S3:** 5 GB free storage
- **Amplify Hosting:** 1,000 build minutes/month free, 15 GB served/month free

For a team of TAMs, this will likely remain within free tier.
