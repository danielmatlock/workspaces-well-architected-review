---
inclusion: auto
---

# AWS Security Policy - Isengard Account Constraints

This project runs in an AWS Isengard-managed account (590183747733). All infrastructure changes MUST comply with the organisation's security policies enforced by Palisade, Epoxy, and SCPs.

## Mandatory Rules

### 1. No Public Lambda Access
- NEVER create Lambda Function URLs with `auth-type NONE`
- NEVER add resource-based policies that grant `Principal: "*"` to Lambda functions
- If a Lambda needs to be called externally, use API Gateway with appropriate auth
- Palisade will auto-detect and Epoxy will auto-mitigate any world-accessible Lambda

### 2. No Public S3 Buckets
- NEVER create S3 buckets with public access enabled
- NEVER add bucket policies granting public read/write
- Block Public Access settings must remain enabled on all buckets

### 3. Cross-Account Access
- Cross-account IAM roles MUST use External IDs to prevent confused deputy
- Trust policies should specify the exact role ARN, not just account root where possible
- STS AssumeRole from Lambda requires both: inline/managed policy on the Lambda role AND trust policy on the target role

### 4. API Gateway
- HTTP APIs (v2) have a hard 30-second timeout that CANNOT be increased
- For long-running operations (>30s), use async patterns:
  - Lambda self-invoke with `InvocationType='Event'`
  - Save results to S3, frontend polls for completion
  - NEVER rely on API Gateway keeping the connection open beyond 30s

### 5. Lambda Function URLs
- BLOCKED by organisation SCPs/Palisade in this account
- Do NOT attempt to use them as a workaround for API Gateway timeouts
- Use async self-invoke pattern instead

### 6. IAM Permissions
- Lambda execution roles need explicit `lambda:InvokeFunction` permission to self-invoke
- `sts:AssumeRole` permission needed for cross-account access
- IAM policy simulation (`simulate-principal-policy`) may show "allowed" but SCPs can still block at runtime
- Always test with real invocations, not just simulations

### 7. SES Email
- SES in this account sends from `danmmat@amazon.co.uk`
- Cannot use custom domains (don't control DNS)
- Cognito user invites should use SES (not Cognito default) to avoid spam filtering
- Recipients within Amazon will see "EXT UNVERIFIED SENDER" - this is cosmetic

## When Unsure

If a design decision involves any of the following, ASK the user before implementing:
- Creating any publicly-accessible endpoint
- Granting `Principal: "*"` in any policy
- Cross-account trust relationships
- New IAM roles or policies
- Changes to authentication/authorisation
- Anything that exposes resources to the internet
- Network configuration changes (security groups, NACLs)
- Encryption settings changes

## Async Pattern (Approved)

For operations exceeding 30 seconds (e.g. Bedrock AI calls):

```
1. Frontend calls API Gateway action (fast, <5s)
2. Lambda saves input to S3
3. Lambda invokes itself with InvocationType='Event' (async)
4. Async Lambda execution runs the slow operation (up to 300s)
5. Async Lambda saves result to S3
6. Frontend polls a status action every 5s until result appears
```

This pattern is approved and working. It does NOT require public access.
