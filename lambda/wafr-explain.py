import json
import os
import boto3

bedrock = boto3.client('bedrock-runtime', region_name='eu-west-2')
MODEL_ID = os.environ.get('MODEL_ID', 'eu.anthropic.claude-haiku-4-5-20251001-v1:0')

def handler(event, context):
    try:
        body = json.loads(event['body']) if 'body' in event else event
        question = body.get('question', '')
        best_practice = body.get('bestPractice', '')

        prompt = (
            "You are an AWS Solutions Architect providing concise guidance during a Well-Architected Review. "
            "A TAM is reviewing this question with a customer.\n\n"
            f"Question: {question}\n\n"
            f"Best Practice: {best_practice}\n\n"
            "Provide:\n"
            "1. A brief explanation of why this matters (2-3 sentences)\n"
            "2. Key things to look for when assessing this (3-4 bullet points)\n"
            "3. Questions to think about when discussing with the customer (3-4 bullet points)\n\n"
            "Keep it concise and actionable. Use markdown formatting."
        )

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
