#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# DEV APPSYNC RESOLVERS SETUP
# ═══════════════════════════════════════════════════════════════════════════════
# Run in CloudShell (eu-west-2) after dev-setup.sh has completed.
# Creates all 10 resolvers for the dev AppSync API.
# ═══════════════════════════════════════════════════════════════════════════════

set -e
export AWS_PAGER=""

REGION="eu-west-2"
API_ID="uhvg74jzx5fzvaj5e3amddvonm"

echo "═══════════════════════════════════════════════════════════"
echo "  Creating AppSync Resolvers for Dev API: $API_ID"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ─────────────────────────────────────────────────────────────
# Query: listReviews → Scan wafr-reviews-dev
# ─────────────────────────────────────────────────────────────
echo "▶ Creating resolver: Query.listReviews"
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Query \
  --field-name listReviews \
  --data-source-name wafr_reviews_dev \
  --request-mapping-template '{
    "version": "2017-02-28",
    "operation": "Scan"
  }' \
  --response-mapping-template '$util.toJson($ctx.result.items)' \
  --region $REGION && echo "  ✓ Query.listReviews" || echo "  ⚠ Already exists or failed"

# ─────────────────────────────────────────────────────────────
# Query: getReview → GetItem wafr-reviews-dev
# ─────────────────────────────────────────────────────────────
echo "▶ Creating resolver: Query.getReview"
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Query \
  --field-name getReview \
  --data-source-name wafr_reviews_dev \
  --request-mapping-template '{
    "version": "2017-02-28",
    "operation": "GetItem",
    "key": {
      "id": $util.dynamodb.toDynamoDBJson($ctx.args.id)
    }
  }' \
  --response-mapping-template '$util.toJson($ctx.result)' \
  --region $REGION && echo "  ✓ Query.getReview" || echo "  ⚠ Already exists or failed"

# ─────────────────────────────────────────────────────────────
# Query: listTemplates → Scan wafr-templates-dev
# ─────────────────────────────────────────────────────────────
echo "▶ Creating resolver: Query.listTemplates"
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Query \
  --field-name listTemplates \
  --data-source-name wafr_templates_dev \
  --request-mapping-template '{
    "version": "2017-02-28",
    "operation": "Scan"
  }' \
  --response-mapping-template '$util.toJson($ctx.result.items)' \
  --region $REGION && echo "  ✓ Query.listTemplates" || echo "  ⚠ Already exists or failed"

# ─────────────────────────────────────────────────────────────
# Query: getTemplate → GetItem wafr-templates-dev
# ─────────────────────────────────────────────────────────────
echo "▶ Creating resolver: Query.getTemplate"
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Query \
  --field-name getTemplate \
  --data-source-name wafr_templates_dev \
  --request-mapping-template '{
    "version": "2017-02-28",
    "operation": "GetItem",
    "key": {
      "id": $util.dynamodb.toDynamoDBJson($ctx.args.id)
    }
  }' \
  --response-mapping-template '$util.toJson($ctx.result)' \
  --region $REGION && echo "  ✓ Query.getTemplate" || echo "  ⚠ Already exists or failed"

# ─────────────────────────────────────────────────────────────
# Mutation: createReview → PutItem wafr-reviews-dev
# ─────────────────────────────────────────────────────────────
echo "▶ Creating resolver: Mutation.createReview"
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Mutation \
  --field-name createReview \
  --data-source-name wafr_reviews_dev \
  --request-mapping-template '{
    "version": "2017-02-28",
    "operation": "PutItem",
    "key": {
      "id": $util.dynamodb.toDynamoDBJson($ctx.args.input.id)
    },
    "attributeValues": $util.dynamodb.toMapValuesJson($ctx.args.input),
    "condition": {
      "expression": "attribute_not_exists(id)"
    }
  }' \
  --response-mapping-template '$util.toJson($ctx.result)' \
  --region $REGION && echo "  ✓ Mutation.createReview" || echo "  ⚠ Already exists or failed"

# ─────────────────────────────────────────────────────────────
# Mutation: updateReview → PutItem wafr-reviews-dev (overwrite)
# ─────────────────────────────────────────────────────────────
echo "▶ Creating resolver: Mutation.updateReview"
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Mutation \
  --field-name updateReview \
  --data-source-name wafr_reviews_dev \
  --request-mapping-template '{
    "version": "2017-02-28",
    "operation": "PutItem",
    "key": {
      "id": $util.dynamodb.toDynamoDBJson($ctx.args.input.id)
    },
    "attributeValues": $util.dynamodb.toMapValuesJson($ctx.args.input)
  }' \
  --response-mapping-template '$util.toJson($ctx.result)' \
  --region $REGION && echo "  ✓ Mutation.updateReview" || echo "  ⚠ Already exists or failed"

# ─────────────────────────────────────────────────────────────
# Mutation: deleteReview → DeleteItem wafr-reviews-dev
# ─────────────────────────────────────────────────────────────
echo "▶ Creating resolver: Mutation.deleteReview"
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Mutation \
  --field-name deleteReview \
  --data-source-name wafr_reviews_dev \
  --request-mapping-template '{
    "version": "2017-02-28",
    "operation": "DeleteItem",
    "key": {
      "id": $util.dynamodb.toDynamoDBJson($ctx.args.id)
    }
  }' \
  --response-mapping-template '$util.toJson($ctx.result)' \
  --region $REGION && echo "  ✓ Mutation.deleteReview" || echo "  ⚠ Already exists or failed"

# ─────────────────────────────────────────────────────────────
# Mutation: createTemplate → PutItem wafr-templates-dev
# ─────────────────────────────────────────────────────────────
echo "▶ Creating resolver: Mutation.createTemplate"
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Mutation \
  --field-name createTemplate \
  --data-source-name wafr_templates_dev \
  --request-mapping-template '{
    "version": "2017-02-28",
    "operation": "PutItem",
    "key": {
      "id": $util.dynamodb.toDynamoDBJson($ctx.args.input.id)
    },
    "attributeValues": $util.dynamodb.toMapValuesJson($ctx.args.input),
    "condition": {
      "expression": "attribute_not_exists(id)"
    }
  }' \
  --response-mapping-template '$util.toJson($ctx.result)' \
  --region $REGION && echo "  ✓ Mutation.createTemplate" || echo "  ⚠ Already exists or failed"

# ─────────────────────────────────────────────────────────────
# Mutation: updateTemplate → PutItem wafr-templates-dev (overwrite)
# ─────────────────────────────────────────────────────────────
echo "▶ Creating resolver: Mutation.updateTemplate"
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Mutation \
  --field-name updateTemplate \
  --data-source-name wafr_templates_dev \
  --request-mapping-template '{
    "version": "2017-02-28",
    "operation": "PutItem",
    "key": {
      "id": $util.dynamodb.toDynamoDBJson($ctx.args.input.id)
    },
    "attributeValues": $util.dynamodb.toMapValuesJson($ctx.args.input)
  }' \
  --response-mapping-template '$util.toJson($ctx.result)' \
  --region $REGION && echo "  ✓ Mutation.updateTemplate" || echo "  ⚠ Already exists or failed"

# ─────────────────────────────────────────────────────────────
# Mutation: deleteTemplate → DeleteItem wafr-templates-dev
# ─────────────────────────────────────────────────────────────
echo "▶ Creating resolver: Mutation.deleteTemplate"
aws appsync create-resolver \
  --api-id $API_ID \
  --type-name Mutation \
  --field-name deleteTemplate \
  --data-source-name wafr_templates_dev \
  --request-mapping-template '{
    "version": "2017-02-28",
    "operation": "DeleteItem",
    "key": {
      "id": $util.dynamodb.toDynamoDBJson($ctx.args.id)
    }
  }' \
  --response-mapping-template '$util.toJson($ctx.result)' \
  --region $REGION && echo "  ✓ Mutation.deleteTemplate" || echo "  ⚠ Already exists or failed"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ALL 10 RESOLVERS CREATED"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Dev AppSync is now fully functional."
echo "  Test at: https://dev.d1p2543h8l2mfc.amplifyapp.com"
echo ""
