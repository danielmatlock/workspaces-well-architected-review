import json
import re
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

ses = boto3.client('ses', region_name='eu-west-2')
bedrock = boto3.client('bedrock-runtime', region_name='eu-west-2')
SENDER = 'danmmat@amazon.co.uk'
MODEL_ID = 'eu.anthropic.claude-haiku-4-5-20251001-v1:0'

def generate_tailored_recommendations(questions_with_notes):
    if not questions_with_notes:
        return {}
    prompt_items = []
    for item in questions_with_notes:
        prompt_items.append("ID: " + item['id'] + "\nQuestion: " + item['question'] + "\nScore: " + item['score'] + "\nCustomer Notes: " + item['notes'] + "\nBest Practice: " + item['best'])
    joined = "\n\n".join(prompt_items)
    prompt = ("You are an AWS Solutions Architect writing a formal Well-Architected Review report. "
               "For each question below, produce two things:\n"
               "1. 'observation': Rewrite the raw customer notes as polished, professional prose. "
               "Fix spelling and grammar, write in full sentences, maintain all factual content, use third-person formal tone (e.g. 'The customer currently manages...'). "
               "Keep it concise (2-4 sentences).\n"
               "2. 'recommendation': Structured as: a brief acknowledgement of current state (1-2 sentences), "
               "then 2-3 next-step bullet points starting with '• ', "
               "then a 'Further Reading:' line with 1-2 real https://docs.aws.amazon.com URLs. "
               "IMPORTANT: You MUST include the Further Reading line for EVERY question. Never omit it.\n"
               "Format as JSON: {\"QUESTION-ID\": {\"observation\": \"...\", \"recommendation\": \"...\"}}. "
               "Respond with ONLY valid JSON, no markdown fences.\n\nQuestions:\n" + joined)

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 4096,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        result = json.loads(response['body'].read())
        text = result['content'][0]['text'].strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return json.loads(text)
    except Exception as e:
        return {"_error": str(e)}

def handler(event, context):
    try:
        body = json.loads(event['body']) if 'body' in event else event
        action = body.get('action', 'email')
        
        if action == 'generate':
            questions_with_notes = body.get('questions', [])
            recommendations = generate_tailored_recommendations(questions_with_notes)
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'recommendations': recommendations})
            }
        
        if action == 'email':
            recipient = body['recipient']
            html_report = body['htmlReport']
            customer_name = body['customerName']
            review_date = body['reviewDate']
            msg = MIMEMultipart('mixed')
            msg['Subject'] = f'AWS Well-Architected Review Report - {customer_name} ({review_date})'
            msg['From'] = SENDER
            msg['To'] = recipient
            body_html = f"""<html><body>
<p>Hi,</p>
<p>Please find attached the AWS Well-Architected Framework Review report for <strong>{customer_name}</strong>, dated {review_date}.</p>
<p>Open the attached HTML file in your browser to view the full report. You can also print it to PDF using Cmd+P / Ctrl+P.</p>
<p>Regards,<br>AWS Technical Account Management</p>
</body></html>"""
            body_part = MIMEText(body_html, 'html')
            msg.attach(body_part)
            attachment = MIMEApplication(html_report.encode('utf-8'))
            filename = f"{customer_name.replace(' ', '-').lower()}-wafr-report-{review_date}.html"
            attachment.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(attachment)
            ses.send_raw_email(Source=SENDER, Destinations=[recipient], RawMessage={'Data': msg.as_string()})
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Report sent successfully'})
            }
        
        return {
            'statusCode': 400,
            'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Invalid action'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
