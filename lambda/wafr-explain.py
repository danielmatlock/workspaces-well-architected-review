import json
import os
import boto3

bedrock = boto3.client('bedrock-runtime', region_name='eu-west-2')
MODEL_ID = os.environ.get('MODEL_ID', 'eu.anthropic.claude-haiku-4-5-20251001-v1:0')

# Template-specific system prompts
TEMPLATE_PROMPTS = {
    'workspaces-default': (
        "You are an AWS Solutions Architect providing concise guidance during a "
        "Well-Architected Framework Review specifically for Amazon WorkSpaces deployments. "
        "A TAM is reviewing this question with a customer who runs Amazon WorkSpaces. "
        "Your guidance should be specific to WorkSpaces architecture, security, operations, "
        "performance, cost optimisation, and sustainability best practices.\n\n"
    ),
    'orr-default': (
        "You are an AWS Solutions Architect providing concise guidance during an "
        "Operational Readiness Review (ORR). A TAM is conducting an ORR workshop with a "
        "customer who is preparing to launch or operate an application on AWS.\n\n"
        "CONTEXT ABOUT ORR:\n"
        "The AWS ORR is a mechanism to help teams validate they can safely operate their "
        "workloads. It distills learnings from years of AWS operational incidents into "
        "curated checklist questions - preventing recurrence of known failure modes.\n\n"
        "ORR covers four major categories:\n"
        "1. Architectural recommendations - resilience, blast radius, dependencies\n"
        "2. Operational processes - incident management, change management, on-call\n"
        "3. Event management - monitoring, alerting, escalation, communication\n"
        "4. Release quality - CI/CD, safe deployment, testing, rollback\n\n"
        "The goal is to achieve smaller, fewer, and shorter incidents without slowing "
        "builders down. ORRs should run during design, development, pre-launch, and "
        "periodically (at least annually) after launch.\n\n"
        "Your guidance should focus on operational readiness for going live - not specific "
        "to any single AWS service. Help the TAM assess whether the customer's application "
        "meets the operational bar for production. Reference AWS Well-Architected Framework "
        "principles, especially the Operational Excellence and Reliability pillars.\n\n"
    )
}

def get_prompt(template_id, question, best_practice):
    """Build the full prompt based on template type."""
    system_context = TEMPLATE_PROMPTS.get(template_id, TEMPLATE_PROMPTS['workspaces-default'])
    
    prompt = (
        system_context +
        f"Question being assessed: {question}\n\n"
        f"Best Practice: {best_practice}\n\n"
        "Provide:\n"
        "1. A brief explanation of why this matters (2-3 sentences)\n"
        "2. Key things to look for when assessing this (3-4 bullet points)\n"
        "3. Questions to think about when discussing with the customer (3-4 bullet points)\n\n"
        "Keep it concise and actionable. Use markdown formatting."
    )
    return prompt


def handler(event, context):
    try:
        body = json.loads(event['body']) if 'body' in event else event
        question = body.get('question', '')
        best_practice = body.get('bestPractice', '')
        template_id = body.get('templateId', 'workspaces-default')

        prompt = get_prompt(template_id, question, best_practice)

        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 512,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        result = json.loads(response['body'].read())
        explanation = result['content'][0]['text'].strip()

        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
            'body': json.dumps({'explanation': explanation})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
