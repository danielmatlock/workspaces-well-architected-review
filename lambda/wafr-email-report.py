import json
import re
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from botocore.config import Config

ses = boto3.client('ses', region_name='eu-west-2')
bedrock = boto3.client('bedrock-runtime', region_name='eu-west-2')
s3 = boto3.client('s3', region_name='eu-west-2', endpoint_url='https://s3.eu-west-2.amazonaws.com', config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
SENDER = 'danmmat@amazon.co.uk'
MODEL_ID = 'eu.anthropic.claude-haiku-4-5-20251001-v1:0'
REPORTS_BUCKET = 'wafr-reports-danmmat-9219112'

def generate_tailored_recommendations(questions_with_notes, reference_context=''):
    if not questions_with_notes:
        return {}
    prompt_items = []
    for item in questions_with_notes:
        prompt_items.append("ID: " + item['id'] + "\nQuestion: " + item['question'] + "\nScore: " + item['score'] + "\nCustomer Notes: " + item['notes'] + "\nBest Practice: " + item['best'])
    joined = "\n\n".join(prompt_items)
    
    grounding = ''
    if reference_context:
        grounding = ("\n\nIMPORTANT REFERENCE DATA:\n"
                     "The following is extracted from existing reports for this customer. "
                     "Use this as your primary source of truth. Do NOT invent findings not present in this data. "
                     "Cross-reference your recommendations against these reports to ensure accuracy and reduce hallucinations.\n\n"
                     + reference_context + "\n\n--- END REFERENCE DATA ---\n\n")
    
    prompt = ("You are an AWS Solutions Architect writing a formal Well-Architected Review report. "
               "For each question below, produce two things:\n"
               "1. 'observation': Rewrite the raw customer notes as polished, professional prose. "
               "Fix spelling and grammar, write in full sentences, maintain all factual content, use third-person formal tone (e.g. 'The customer currently manages...'). "
               "Keep it concise (2-4 sentences).\n"
               "2. 'recommendation': Structured as: a brief acknowledgement of current state (1-2 sentences), "
               "then 2-3 next-step bullet points starting with '\u2022 ', "
               "then a 'Further Reading:' line with 1-2 real https://docs.aws.amazon.com URLs. "
               "IMPORTANT: You MUST include the Further Reading line for EVERY question. Never omit it.\n"
               + grounding +
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
        
        if action == 'saveReport':
            review_id = body['reviewId']
            report_type = body['reportType']  # 'standard', 'sowhat', 'clevel'
            content = body['content']  # base64 for pptx, raw html for others
            content_type = body.get('contentType', 'text/html')
            extension = body.get('extension', 'html')
            customer = body.get('customer', 'review')
            from datetime import datetime
            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H%M%S')
            key = f"{review_id}/{report_type}_{timestamp}.{extension}"
            import base64
            file_bytes = base64.b64decode(content) if extension == 'pptx' else content.encode('utf-8')
            s3.put_object(
                Bucket=REPORTS_BUCKET, Key=key, Body=file_bytes,
                ContentType=content_type,
                Metadata={'customer': customer, 'reportType': report_type, 'timestamp': timestamp}
            )
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Report saved', 'key': key})
            }

        if action == 'listReports':
            review_id = body['reviewId']
            prefix = f"{review_id}/"
            response = s3.list_objects_v2(Bucket=REPORTS_BUCKET, Prefix=prefix)
            reports = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                filename = key.split('/')[-1]
                parts = filename.rsplit('.', 1)
                name_part = parts[0]  # e.g. 'standard_2025-06-15T143200'
                ext = parts[1] if len(parts) > 1 else ''
                type_and_time = name_part.split('_', 1)
                report_type = type_and_time[0]
                timestamp = type_and_time[1] if len(type_and_time) > 1 else ''
                reports.append({'key': key, 'reportType': report_type, 'timestamp': timestamp, 'extension': ext, 'size': obj['Size']})
            reports.sort(key=lambda r: r['timestamp'], reverse=True)
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'reports': reports})
            }

        if action == 'getReport':
            import base64
            key = body['key']
            obj = s3.get_object(Bucket=REPORTS_BUCKET, Key=key)
            content = obj['Body'].read()
            content_type = obj.get('ContentType', 'application/octet-stream')
            b64 = base64.b64encode(content).decode('utf-8')
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'data': b64, 'contentType': content_type, 'filename': key.split('/')[-1]})
            }

        if action == 'deleteReport':
            key = body['key']
            s3.delete_object(Bucket=REPORTS_BUCKET, Key=key)
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'deleted': key})
            }

        if action == 'generate':
            questions_with_notes = body.get('questions', [])
            reference_context = body.get('referenceContext', '')
            recommendations = generate_tailored_recommendations(questions_with_notes, reference_context)
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
        
        if action == 'notify':
            recipient = body['recipient']
            subject = body['subject']
            html_body = body['htmlBody']
            ses.send_email(
                Source=SENDER,
                Destination={'ToAddresses': [recipient]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {'Html': {'Data': '<html><body>' + html_body + '<br><p style="color:#5f6b7a;font-size:12px;">— AWS WorkSpaces WAFR Tool</p></body></html>'}}
                }
            )
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Notification sent'})
            }

        if action == 'curateDeck':
            findings = body.get('findings', [])
            overall_score = body.get('overallScore', 0)
            pillar_scores = body.get('pillarScores', [])
            customer_name = body.get('customerName', 'Customer')
            reference_context = body.get('referenceContext', '')

            findings_text = []
            for f in findings:
                findings_text.append(
                    f"ID: {f['id']}\nPillar: {f['pillar']}\nQuestion: {f['question']}\n"
                    f"RAG: {f['score']}\nNotes: {f.get('notes', '')}\n"
                    f"Observation: {f.get('observation', '')}\nRecommendation: {f.get('recommendation', '')}"
                )
            joined_findings = "\n\n---\n\n".join(findings_text)

            pillar_summary = "\n".join([f"- {p['name']}: {p['score']}% ({p['rag']})" for p in pillar_scores])

            grounding = ''
            if reference_context:
                grounding = (
                    "\n\nREFERENCE DATA (use as primary source of truth, do NOT invent findings not present here):\n"
                    + reference_context[:20000] + "\n--- END REFERENCE DATA ---\n\n"
                )

            curation_prompt = f"""You are an AWS Solutions Architect preparing a C-level executive briefing from a WorkSpaces Well-Architected Review.

CUSTOMER: {customer_name}
OVERALL SCORE: {overall_score}%
PILLAR SCORES:
{pillar_summary}
{grounding}
FINDINGS:
{joined_findings}

YOUR TASK: Curate these findings into a boardroom-ready narrative. Do NOT map mechanically (RED=MUST, AMBER=SHOULD, GREEN=COULD). Instead, curate intelligently:

RULES:
1. CRITICAL FINDINGS: Select exactly 4 board-level risks. For each, provide a business-framed headline (e.g. "PCoIP to DCV Protocol Migration" not "How do you manage the migration...") and a 2-3 sentence consequence explanation (e.g. compliance failure, security exposure, cost risk).
2. MUST tier: Genuine board-level risks + true low-effort quick wins. Only items that create a preventable crisis or are simple to fix with high impact. Usually 3-5 items max.
3. SHOULD tier: The 4-6 highest-value items to resource this quarter. Not every AMBER — only the ones that move the needle.
4. COULD tier: Strategic, longer-term items. 4-6 items max.
5. For each item in any tier, provide: the original ID, a business-framed headline (5-8 words, no "How do you..."), and a one-sentence action summary.
6. NEVER present already-implemented items (scored "fully") as gaps or quick wins.
7. Cost optimisation: Only quantify savings where the source data provides figures. Otherwise write "Requires fleet inventory and billing data to quantify."
8. 90-Day Roadmap: Assign curated items to Week 1-2 (urgent MUST), Week 3-6 (remaining MUST + top SHOULD), Week 7-12 (SHOULD + COULD).

WORDING RULES (CRITICAL - apply to ALL text you generate):
9. NEVER use the words "customer", "the customer", or "Customer-1" in any output text. These are BANNED. Use the organisation name "{customer_name}", or "the estate", "the fleet", "your WorkSpaces environment", or address the subject directly.
10. Rewrite "Customer recognizes the need to X" as "X is not yet in place" or "The fleet currently lacks X". State what IS and what it RISKS. Use executive voice.
11. Keep all text concise — headlines 5-8 words, actions max 2 sentences, consequences max 3 sentences. This is a scannable exec deck, not a report.
12. executiveSummary must be exactly 3-4 SHORT sentences (max 30 words each). State posture, key risks, and recommended focus. No paragraph walls.

Respond with ONLY valid JSON in this exact structure:
{{
  "criticalFindings": [
    {{"id": "OPS-WS-11", "headline": "PCoIP to DCV Migration", "consequence": "2-3 sentence business consequence", "rag": "red"}}
  ],
  "must": [
    {{"id": "OPS-WS-11", "headline": "Short business headline", "action": "One sentence action", "effort": "low|medium|high", "isQuickWin": true}}
  ],
  "should": [
    {{"id": "...", "headline": "...", "action": "...", "effort": "low|medium|high"}}
  ],
  "could": [
    {{"id": "...", "headline": "...", "action": "...", "effort": "medium|high"}}
  ],
  "costInsights": {{
    "hasData": false,
    "summary": "Overall cost assessment in 2-3 sentences",
    "items": [{{"id": "COST-WS-01", "headline": "...", "insight": "..."}}]
  }},
  "roadmap": {{
    "week1_2": [{{"id": "...", "headline": "..."}}],
    "week3_6": [{{"id": "...", "headline": "..."}}],
    "week7_12": [{{"id": "...", "headline": "..."}}]
  }},
  "executiveSummary": "A 3-4 sentence executive summary suitable for a board audience, stating the overall posture, key risks, and recommended focus areas."
}}"""

            try:
                response = bedrock.invoke_model(
                    modelId=MODEL_ID,
                    contentType='application/json',
                    accept='application/json',
                    body=json.dumps({
                        'anthropic_version': 'bedrock-2023-05-31',
                        'max_tokens': 8192,
                        'messages': [{'role': 'user', 'content': curation_prompt}]
                    })
                )
                result = json.loads(response['body'].read())
                text = result['content'][0]['text'].strip()
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
                curated = json.loads(text)
                return {
                    'statusCode': 200,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'curated': curated})
                }
            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Curation failed: ' + str(e)})
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
