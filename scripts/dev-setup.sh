#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# DEV ENVIRONMENT SETUP — WorkSpaces WAFR Tool
# ═══════════════════════════════════════════════════════════════════════════════
# Run this script in AWS CloudShell (eu-west-2) to create a fully independent
# development environment. Run it ONCE — subsequent deploys use the standard
# deploy commands in DEPLOYMENT.md.
#
# Prerequisites:
#   - CloudShell in eu-west-2 (account 590183747733)
#   - The 'dev' branch must exist in GitHub before deploying frontend
#
# What this creates:
#   - Cognito groups (Dev, Prod, Admins) on existing User Pool
#   - S3 bucket for dev reports
#   - DynamoDB tables for dev (reviews + templates)
#   - AppSync API for dev (pointing to dev DynamoDB tables)
#   - Lambda functions for dev (wafr-explain-dev, wafr-email-report-dev)
#   - API Gateway HTTP API for dev
#   - Amplify 'dev' branch
#
# Shared resources (NOT duplicated):
#   - Cognito User Pool (eu-west-2_Wy0eJHyN3)
#   - Bedrock (stateless — same model used by dev and prod)
#   - SES (same verified sender)
# ═══════════════════════════════════════════════════════════════════════════════

set -e

REGION="eu-west-2"
ACCOUNT_ID="590183747733"
COGNITO_POOL_ID="eu-west-2_Wy0eJHyN3"
AMPLIFY_APP_ID="d1p2543h8l2mfc"

echo "═══════════════════════════════════════════════════════════"
echo "  WAFR Tool — Dev Environment Setup"
echo "  Region: $REGION | Account: $ACCOUNT_ID"
echo "═══════════════════════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────
# STEP 1: Cognito Groups
# ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Step 1: Creating Cognito groups..."

for GROUP in Dev Prod Admins; do
  if aws cognito-idp get-group --user-pool-id $COGNITO_POOL_ID --group-name $GROUP --region $REGION 2>/dev/null; then
    echo "  ✓ Group '$GROUP' already exists"
  else
    aws cognito-idp create-group \
      --user-pool-id $COGNITO_POOL_ID \
      --group-name $GROUP \
      --description "$GROUP environment access" \
      --region $REGION
    echo "  ✓ Created group '$GROUP'"
  fi
done

# Add current user to Admins (adjust username as needed)
echo "  ℹ To add yourself to Admins, run:"
echo "    aws cognito-idp admin-add-user-to-group --user-pool-id $COGNITO_POOL_ID --username YOUR_EMAIL --group-name Admins --region $REGION"

# ─────────────────────────────────────────────────────────────
# STEP 2: S3 Bucket for Dev Reports
# ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Step 2: Creating dev S3 bucket..."

DEV_BUCKET="wafr-reports-danmmat-dev"
if aws s3 ls "s3://$DEV_BUCKET" --region $REGION 2>/dev/null; then
  echo "  ✓ Bucket '$DEV_BUCKET' already exists"
else
  aws s3 mb "s3://$DEV_BUCKET" --region $REGION
  echo "  ✓ Created bucket '$DEV_BUCKET'"
fi

# ─────────────────────────────────────────────────────────────
# STEP 3: DynamoDB Tables for Dev
# ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Step 3: Creating dev DynamoDB tables..."

for TABLE in wafr-reviews-dev wafr-templates-dev; do
  if aws dynamodb describe-table --table-name $TABLE --region $REGION 2>/dev/null; then
    echo "  ✓ Table '$TABLE' already exists"
  else
    aws dynamodb create-table \
      --table-name $TABLE \
      --attribute-definitions AttributeName=id,AttributeType=S \
      --key-schema AttributeName=id,KeyType=HASH \
      --billing-mode PAY_PER_REQUEST \
      --region $REGION
    echo "  ✓ Created table '$TABLE'"

    # Enable PITR
    aws dynamodb update-continuous-backups \
      --table-name $TABLE \
      --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
      --region $REGION
    echo "  ✓ Enabled PITR on '$TABLE'"
  fi
done

# ─────────────────────────────────────────────────────────────
# STEP 4: IAM Role for Dev Lambda (reuse existing role)
# ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Step 4: IAM role setup..."
echo "  ℹ Reusing existing 'lambda-ses-email-role' — ensure its policy allows:"
echo "    - s3:PutObject, GetObject, ListBucket, DeleteObject on '$DEV_BUCKET'"
echo ""
echo "  Run this to update the S3 policy (if needed):"
cat <<'POLICY'
  aws iam put-role-policy --role-name lambda-ses-email-role --policy-name wafr-reports-s3-dev --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject"],
      "Resource": ["arn:aws:s3:::wafr-reports-danmmat-dev", "arn:aws:s3:::wafr-reports-danmmat-dev/*"]
    }]
  }'
POLICY

# ─────────────────────────────────────────────────────────────
# STEP 5: Lambda Functions for Dev
# ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Step 5: Creating dev Lambda functions..."

# wafr-email-report-dev
if aws lambda get-function --function-name wafr-email-report-dev --region $REGION 2>/dev/null; then
  echo "  ✓ Function 'wafr-email-report-dev' already exists"
else
  # Create a placeholder zip
  echo "def handler(event, context): return {'statusCode': 200}" > /tmp/placeholder.py
  cd /tmp && zip -q placeholder.zip placeholder.py

  aws lambda create-function \
    --function-name wafr-email-report-dev \
    --runtime python3.12 \
    --handler wafr-email-report.lambda_handler \
    --role "arn:aws:iam::${ACCOUNT_ID}:role/lambda-ses-email-role" \
    --timeout 90 \
    --memory-size 256 \
    --environment "Variables={REPORTS_BUCKET=$DEV_BUCKET,SENDER_EMAIL=danmmat@amazon.co.uk,MODEL_ID=eu.anthropic.claude-haiku-4-5-20251001-v1:0}" \
    --zip-file fileb:///tmp/placeholder.zip \
    --region $REGION
  echo "  ✓ Created 'wafr-email-report-dev'"

  rm -f /tmp/placeholder.py /tmp/placeholder.zip
fi

# wafr-explain-dev
if aws lambda get-function --function-name wafr-explain-dev --region $REGION 2>/dev/null; then
  echo "  ✓ Function 'wafr-explain-dev' already exists"
else
  echo "def handler(event, context): return {'statusCode': 200}" > /tmp/placeholder.py
  cd /tmp && zip -q placeholder.zip placeholder.py

  aws lambda create-function \
    --function-name wafr-explain-dev \
    --runtime python3.12 \
    --handler wafr-explain.lambda_handler \
    --role "arn:aws:iam::${ACCOUNT_ID}:role/lambda-bedrock-role" \
    --timeout 30 \
    --memory-size 256 \
    --zip-file fileb:///tmp/placeholder.zip \
    --region $REGION
  echo "  ✓ Created 'wafr-explain-dev'"

  rm -f /tmp/placeholder.py /tmp/placeholder.zip
fi

# ─────────────────────────────────────────────────────────────
# STEP 6: API Gateway HTTP API for Dev
# ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Step 6: Creating dev API Gateway..."

DEV_API_NAME="wafr-dev-api"
EXISTING_API=$(aws apigatewayv2 get-apis --region $REGION --query "Items[?Name=='$DEV_API_NAME'].ApiId" --output text 2>/dev/null)

if [ -n "$EXISTING_API" ] && [ "$EXISTING_API" != "None" ]; then
  DEV_API_ID=$EXISTING_API
  echo "  ✓ API '$DEV_API_NAME' already exists: $DEV_API_ID"
else
  DEV_API_ID=$(aws apigatewayv2 create-api \
    --name $DEV_API_NAME \
    --protocol-type HTTP \
    --cors-configuration AllowOrigins='*',AllowMethods='POST,OPTIONS',AllowHeaders='Content-Type,Authorization' \
    --region $REGION \
    --query 'ApiId' --output text)
  echo "  ✓ Created API: $DEV_API_ID"

  # Create $default stage with auto-deploy
  aws apigatewayv2 create-stage \
    --api-id $DEV_API_ID \
    --stage-name '$default' \
    --auto-deploy \
    --region $REGION
  echo "  ✓ Created \$default stage"

  # Integration: wafr-email-report-dev
  EMAIL_INTEGRATION=$(aws apigatewayv2 create-integration \
    --api-id $DEV_API_ID \
    --integration-type AWS_PROXY \
    --integration-uri "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:wafr-email-report-dev" \
    --payload-format-version "2.0" \
    --region $REGION \
    --query 'IntegrationId' --output text)

  aws apigatewayv2 create-route \
    --api-id $DEV_API_ID \
    --route-key "POST /email-report" \
    --target "integrations/$EMAIL_INTEGRATION" \
    --region $REGION
  echo "  ✓ Route: POST /email-report → wafr-email-report-dev"

  # Integration: wafr-explain-dev
  EXPLAIN_INTEGRATION=$(aws apigatewayv2 create-integration \
    --api-id $DEV_API_ID \
    --integration-type AWS_PROXY \
    --integration-uri "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:wafr-explain-dev" \
    --payload-format-version "2.0" \
    --region $REGION \
    --query 'IntegrationId' --output text)

  aws apigatewayv2 create-route \
    --api-id $DEV_API_ID \
    --route-key "POST /explain" \
    --target "integrations/$EXPLAIN_INTEGRATION" \
    --region $REGION
  echo "  ✓ Route: POST /explain → wafr-explain-dev"

  # Grant API Gateway permission to invoke Lambdas
  aws lambda add-permission \
    --function-name wafr-email-report-dev \
    --statement-id apigateway-dev-email \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${DEV_API_ID}/*" \
    --region $REGION 2>/dev/null || true

  aws lambda add-permission \
    --function-name wafr-explain-dev \
    --statement-id apigateway-dev-explain \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${DEV_API_ID}/*" \
    --region $REGION 2>/dev/null || true
  echo "  ✓ Lambda invoke permissions granted"
fi

DEV_API_URL="https://${DEV_API_ID}.execute-api.${REGION}.amazonaws.com"
echo ""
echo "  ★ Dev API URL: $DEV_API_URL"
echo "  ★ Update index.html ENV block DEV_API_ID with: $DEV_API_ID"

# ─────────────────────────────────────────────────────────────
# STEP 7: AppSync API for Dev
# ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Step 7: Creating dev AppSync API..."

DEV_APPSYNC_NAME="wafr-dev-api"
EXISTING_APPSYNC=$(aws appsync list-graphql-apis --region $REGION --query "graphqlApis[?name=='$DEV_APPSYNC_NAME'].apiId" --output text 2>/dev/null)

if [ -n "$EXISTING_APPSYNC" ] && [ "$EXISTING_APPSYNC" != "None" ]; then
  DEV_APPSYNC_ID=$EXISTING_APPSYNC
  echo "  ✓ AppSync API '$DEV_APPSYNC_NAME' already exists: $DEV_APPSYNC_ID"
else
  DEV_APPSYNC_ID=$(aws appsync create-graphql-api \
    --name $DEV_APPSYNC_NAME \
    --authentication-type AMAZON_COGNITO_USER_POOLS \
    --user-pool-config "userPoolId=$COGNITO_POOL_ID,awsRegion=$REGION,defaultAction=ALLOW" \
    --region $REGION \
    --query 'graphqlApi.apiId' --output text)
  echo "  ✓ Created AppSync API: $DEV_APPSYNC_ID"

  # Create schema
  SCHEMA=$(cat <<'EOF'
type Template {
  id: ID!
  name: String!
  description: String
  pillars: AWSJSON!
  isDefault: Boolean
  createdBy: String!
  createdAt: AWSDateTime!
  updatedAt: AWSDateTime!
}

type Review {
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

input CreateReviewInput {
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
}

input UpdateReviewInput {
  id: ID!
  templateId: String
  templateName: String
  customerName: String
  reviewerName: String
  reviewDate: String
  answers: AWSJSON
  notes: AWSJSON
  status: String
  overallScore: Float
  pillarScores: AWSJSON
}

input CreateTemplateInput {
  id: ID!
  name: String!
  description: String
  pillars: AWSJSON!
  isDefault: Boolean
  createdBy: String!
}

input UpdateTemplateInput {
  id: ID!
  name: String
  description: String
  pillars: AWSJSON
  isDefault: Boolean
}

type Query {
  listReviews: [Review]
  getReview(id: ID!): Review
  listTemplates: [Template]
  getTemplate(id: ID!): Template
}

type Mutation {
  createReview(input: CreateReviewInput!): Review
  updateReview(input: UpdateReviewInput!): Review
  deleteReview(id: ID!): Review
  createTemplate(input: CreateTemplateInput!): Template
  updateTemplate(input: UpdateTemplateInput!): Template
  deleteTemplate(id: ID!): Template
}

schema {
  query: Query
  mutation: Mutation
}
EOF
)

  echo "$SCHEMA" > /tmp/dev-schema.graphql
  aws appsync start-schema-creation \
    --api-id $DEV_APPSYNC_ID \
    --definition fileb:///tmp/dev-schema.graphql \
    --region $REGION
  echo "  ✓ Schema uploaded (processing...)"

  # Wait for schema
  sleep 5

  # Create DynamoDB data source for reviews
  aws appsync create-data-source \
    --api-id $DEV_APPSYNC_ID \
    --name "wafr_reviews_dev" \
    --type AMAZON_DYNAMODB \
    --dynamodb-config "tableName=wafr-reviews-dev,awsRegion=$REGION" \
    --service-role-arn "arn:aws:iam::${ACCOUNT_ID}:role/appsync-dynamodb-role" \
    --region $REGION
  echo "  ✓ Data source: wafr-reviews-dev"

  # Create DynamoDB data source for templates
  aws appsync create-data-source \
    --api-id $DEV_APPSYNC_ID \
    --name "wafr_templates_dev" \
    --type AMAZON_DYNAMODB \
    --dynamodb-config "tableName=wafr-templates-dev,awsRegion=$REGION" \
    --service-role-arn "arn:aws:iam::${ACCOUNT_ID}:role/appsync-dynamodb-role" \
    --region $REGION
  echo "  ✓ Data source: wafr-templates-dev"

  echo ""
  echo "  ⚠ NOTE: You need to create resolvers manually in the AppSync console"
  echo "    for the dev API to match the production resolvers (Scan, PutItem, etc.)."
  echo "    Alternatively, copy them from the production AppSync API."
fi

DEV_APPSYNC_URL=$(aws appsync get-graphql-api --api-id $DEV_APPSYNC_ID --region $REGION --query 'graphqlApi.uris.GRAPHQL' --output text 2>/dev/null || echo "PENDING")
echo ""
echo "  ★ Dev AppSync URL: $DEV_APPSYNC_URL"
echo "  ★ Update index.html ENV block DEV_APPSYNC_ID with the ID from the URL"

# ─────────────────────────────────────────────────────────────
# STEP 8: Amplify Dev Branch
# ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Step 8: Creating Amplify dev branch..."

if aws amplify get-branch --app-id $AMPLIFY_APP_ID --branch-name dev --region $REGION 2>/dev/null; then
  echo "  ✓ Amplify 'dev' branch already exists"
else
  aws amplify create-branch \
    --app-id $AMPLIFY_APP_ID \
    --branch-name dev \
    --description "Development environment" \
    --region $REGION
  echo "  ✓ Created Amplify 'dev' branch"
fi

# ─────────────────────────────────────────────────────────────
# STEP 9: Update IAM policy for dev resources
# ─────────────────────────────────────────────────────────────
echo ""
echo "▶ Step 9: Updating IAM policies for dev resources..."

# Add dev bucket to Lambda role
aws iam put-role-policy \
  --role-name lambda-ses-email-role \
  --policy-name wafr-reports-s3-dev \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"s3:PutObject\", \"s3:GetObject\", \"s3:ListBucket\", \"s3:DeleteObject\"],
      \"Resource\": [\"arn:aws:s3:::$DEV_BUCKET\", \"arn:aws:s3:::$DEV_BUCKET/*\"]
    }]
  }" 2>/dev/null && echo "  ✓ Added S3 dev bucket to lambda-ses-email-role" || echo "  ⚠ Could not update policy (may need manual action)"

# Add dev DynamoDB tables to AppSync role
aws iam put-role-policy \
  --role-name appsync-dynamodb-role \
  --policy-name wafr-dynamodb-dev \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"dynamodb:GetItem\", \"dynamodb:PutItem\", \"dynamodb:UpdateItem\", \"dynamodb:DeleteItem\", \"dynamodb:Scan\", \"dynamodb:Query\"],
      \"Resource\": [
        \"arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/wafr-reviews-dev\",
        \"arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/wafr-templates-dev\"
      ]
    }]
  }" 2>/dev/null && echo "  ✓ Added DynamoDB dev tables to appsync-dynamodb-role" || echo "  ⚠ Could not update policy (may need manual action)"

# ─────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  SETUP COMPLETE"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Dev API Gateway:  $DEV_API_URL"
echo "  Dev AppSync:      $DEV_APPSYNC_URL"
echo "  Dev S3 Bucket:    $DEV_BUCKET"
echo "  Dev DynamoDB:     wafr-reviews-dev, wafr-templates-dev"
echo "  Dev Lambdas:      wafr-email-report-dev, wafr-explain-dev"
echo "  Dev Amplify URL:  https://dev.${AMPLIFY_APP_ID}.amplifyapp.com"
echo ""
echo "  NEXT STEPS:"
echo "  1. Update src/index.html ENV block with the dev API/AppSync IDs above"
echo "  2. Create Cognito groups and assign users:"
echo "     aws cognito-idp admin-add-user-to-group --user-pool-id $COGNITO_POOL_ID --username USER_EMAIL --group-name Dev --region $REGION"
echo "     aws cognito-idp admin-add-user-to-group --user-pool-id $COGNITO_POOL_ID --username USER_EMAIL --group-name Prod --region $REGION"
echo "  3. Deploy Lambda code to dev functions (from DEPLOYMENT.md)"
echo "  4. Create AppSync resolvers (copy from production or configure in console)"
echo "  5. Push 'dev' branch and deploy frontend"
echo ""
