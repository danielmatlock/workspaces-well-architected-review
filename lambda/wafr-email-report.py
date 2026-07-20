import json
import re
import os
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from botocore.config import Config

ses = boto3.client('ses', region_name='eu-west-2')
bedrock = boto3.client('bedrock-runtime', region_name='eu-west-2')
s3 = boto3.client('s3', region_name='eu-west-2', endpoint_url='https://s3.eu-west-2.amazonaws.com', config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
SENDER = os.environ.get('SENDER_EMAIL', 'danmmat@amazon.co.uk')
MODEL_ID = os.environ.get('MODEL_ID', 'eu.anthropic.claude-haiku-4-5-20251001-v1:0')
REPORTS_BUCKET = os.environ.get('REPORTS_BUCKET', 'wafr-reports-danmmat-9219112')

# ─── ORR Best Practices Reference ───────────────────────────────────────────────
# Condensed from AWS Operational Readiness Reviews whitepaper and Well-Architected
# Framework OPS07-BP02. Injected as grounding context when templateId is orr-default.
ORR_BEST_PRACTICES = """
AWS OPERATIONAL READINESS REVIEW (ORR) BEST PRACTICES REFERENCE

PURPOSE: The ORR helps teams validate they can safely operate workloads by preventing
recurrence of known failure modes. It drives smaller, fewer, and shorter incidents.

═══ 1. FAILURE MODELING & BLAST RADIUS ═══
• Every service MUST have a documented failure model covering: component/dependency,
  failure type, service impact, and customer impact.
• Address outage scenarios at largest blast radius unit (cell, AZ, Region) plus total
  infrastructure outage.
• Identify single points of failure and document mitigations.
• Define static stability - the system should continue operating if a dependency fails.
• Implement bulkhead patterns to isolate failures (cells, shuffle sharding).
• Quantify blast radius for every change type (deployment, config, data).

═══ 2. OPERATIONAL PROCESSES ═══
• Runbooks MUST exist for every operational scenario (deploy, rollback, failover, scaling).
• On-call rotation MUST be staffed with trained engineers who have access to all systems.
• Incident management process MUST define severity levels, escalation paths, and
  communication templates.
• Change management MUST include pre/post deployment validation, canary analysis, and
  automatic rollback triggers.
• Capacity planning MUST account for peak load + headroom (typically 2x normal).
• Dependency management MUST document all upstream/downstream services, their SLAs,
  and fallback behaviour when unavailable.

═══ 3. EVENT MANAGEMENT (MONITORING & ALERTING) ═══
• Every critical path MUST have alarms with defined thresholds tied to customer impact.
• Dashboards MUST show real-time health at service, dependency, and customer-experience level.
• Alarms MUST route to on-call with actionable runbook links (not just "something is wrong").
• Canary monitoring MUST validate customer-facing workflows continuously.
• Log aggregation MUST support rapid root-cause analysis (structured logs, correlation IDs).
• Metrics MUST cover: availability, latency (p50/p99), error rates, saturation, and
  dependency health.
• Alarm fatigue MUST be managed - every alarm should be actionable or removed.

═══ 4. RELEASE QUALITY & SAFE DEPLOYMENT ═══
• CI/CD pipeline MUST include: unit tests, integration tests, and deployment validation.
• Deployments MUST use progressive rollout (canary, linear, blue/green) with automatic
  rollback on alarm.
• One-box/canary stage MUST bake for sufficient duration before wider rollout.
• Rollback MUST be tested and executable within minutes (not just theoretically possible).
• Feature flags SHOULD decouple deployment from release.
• Database migrations MUST be backward-compatible (no breaking schema changes in-place).
• Deploy frequency SHOULD be high (small batches reduce blast radius per change).

═══ 5. RESILIENCE & RECOVERY ═══
• RTO (Recovery Time Objective) and RPO (Recovery Point Objective) MUST be defined and tested.
• Disaster recovery procedures MUST be exercised regularly (game days, chaos engineering).
• Data backup and restore MUST be validated (not just configured).
• Multi-AZ or multi-Region architecture SHOULD be used for critical workloads.
• Circuit breakers and retry with jitter MUST protect against cascade failures.
• Graceful degradation MUST be designed for non-critical features.

═══ 6. SECURITY & COMPLIANCE READINESS ═══
• Least-privilege IAM MUST be enforced for all service roles and human access.
• Secrets rotation MUST be automated (no long-lived credentials).
• Network segmentation MUST isolate workload from untrusted traffic.
• Vulnerability scanning MUST run in CI/CD pipeline.
• Audit logging MUST capture all administrative actions (CloudTrail, VPC Flow Logs).
• Compliance controls MUST be codified and continuously validated.

═══ 7. ORR LIFECYCLE INTEGRATION ═══
• ORR MUST run during design phase (architecture questions).
• ORR MUST run during development (testing and operational readiness questions).
• ORR MUST run pre-launch (full checklist completion + risk mitigation plan).
• ORR MUST run periodically post-launch (at least annually) to catch drift.
• Lessons learned from incidents (COE/post-mortem) MUST feed back into ORR questions.
• New best practices MUST be incorporated as they emerge from operational experience.

═══ KEY PRINCIPLE ═══
The ORR is NOT a blocking gate - it is a self-service mechanism that helps teams
identify and mitigate operational risks proactively. The goal is to surface risks
early so they can be addressed before they become customer-impacting incidents.
"""

def generate_orr_recommendations(questions_with_notes, reference_context=''):
    """Generate detailed ORR recommendations with observation, recommendation, target state, and steps to green."""
    if not questions_with_notes:
        return {}
    prompt_items = []
    for item in questions_with_notes:
        prompt_items.append("ID: " + item['id'] + "\nQuestion: " + item['question'] + "\nScore: " + item['score'] + "\nReviewer Notes: " + item['notes'] + "\nBest Practice: " + item['best'])
    joined = "\n\n".join(prompt_items)
    
    grounding = ''
    if reference_context:
        grounding = ("\n\nREFERENCE DATA (use as source of truth, do not invent findings):\n"
                     + reference_context + "\n--- END REFERENCE DATA ---\n\n")
    
    orr_grounding = ("\n\nORR BEST PRACTICES REFERENCE:\n" + ORR_BEST_PRACTICES + "\n--- END ORR REFERENCE ---\n\n")
    
    prompt = (
        "You are a senior AWS Solutions Architect conducting a formal Operational Readiness Review (ORR). "
        "The ORR validates whether a workload is ready for production operation by assessing operational "
        "maturity against proven best practices.\n\n"
        "For each question below, produce a JSON object with these FIVE fields:\n\n"
        "1. 'observation': A professional summary of the current state based on the reviewer notes. "
        "Fix spelling/grammar, write in third-person formal tone (e.g. 'The team currently...'), "
        "2-4 sentences. Be specific about what IS in place.\n\n"
        "2. 'recommendation': Structured guidance to improve. Format as:\n"
        "   - Brief acknowledgement of current readiness posture (1 sentence)\n"
        "   - 3-4 actionable bullet points starting with '\u2022 ' that address specific gaps\n"
        "   - Reference relevant ORR domains (failure modeling, operational processes, event management, "
        "release quality, resilience, security)\n"
        "   - End with 'Further Reading:' followed by 1-2 real https://docs.aws.amazon.com URLs\n\n"
        "3. 'targetState': Describe what FULLY IMPLEMENTED looks like for this specific question. "
        "This is the green-state vision - what the team should be aiming for. 2-3 sentences, concrete and measurable.\n\n"
        "4. 'stepsToGreen': An ordered list of 3-5 specific steps the team must take to move from their "
        "current state to fully implemented (green). Each step should be actionable and sequenced logically. "
        "Format as an array of strings, each starting with a number: ['1. First step...', '2. Second step...', ...]\n\n"
        "5. 'priority': Rate the urgency: 'Critical' (blocks production readiness), 'High' (significant risk), "
        "'Medium' (improvement needed), or 'Low' (nice to have). Base this on the gap between current state and best practice.\n\n"
        + orr_grounding + grounding +
        "Format as JSON: {\"QUESTION-ID\": {\"observation\": \"...\", \"recommendation\": \"...\", "
        "\"targetState\": \"...\", \"stepsToGreen\": [\"1. ...\", \"2. ...\"], \"priority\": \"...\"}}. "
        "Respond with ONLY valid JSON, no markdown fences.\n\nQuestions:\n" + joined)

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 8192,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        result = json.loads(response['body'].read())
        text = result['content'][0]['text'].strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        # Extract just the JSON object
        brace_count = 0
        json_end = 0
        for ci, ch in enumerate(text):
            if ch == '{': brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = ci + 1
                    break
        if json_end > 0:
            text = text[:json_end]
        return json.loads(text)
    except Exception as e:
        return {"_error": str(e)}


def map_scan_to_findings(scan_data):
    """Map raw AWS API scan data to WAFR review question findings with evidence and auto-scores."""
    findings = {}
    ws_count = scan_data.get('workspaceCount', 0)
    protocols = scan_data.get('protocols', {})
    running_modes = scan_data.get('runningModes', {})
    directories = scan_data.get('directories', [])
    ws_dirs = scan_data.get('wsDirectories', [])
    ip_groups = scan_data.get('ipGroups', [])
    encrypted_count = scan_data.get('encryptedCount', 0)
    az_count = scan_data.get('azCount', 0)
    nat_count = scan_data.get('natGateways', 0)
    alarms_count = scan_data.get('workspacesAlarms', 0)
    monthly_cost = scan_data.get('monthlyCost', 'N/A')
    bundles = scan_data.get('bundles', {})

    # ─── OPS-WS-04: Monitoring ───
    if alarms_count > 2:
        findings['OPS-WS-04'] = {'score': 'fully', 'evidence': f'CloudWatch monitoring active with {alarms_count} WorkSpaces-related alarms configured. Metrics are being tracked.'}
    elif alarms_count > 0:
        findings['OPS-WS-04'] = {'score': 'partial', 'evidence': f'Basic monitoring in place with {alarms_count} alarm(s). Consider expanding to cover Unhealthy, SessionLaunchTime, InSessionLatency, and ConnectionFailure metrics.'}
    else:
        findings['OPS-WS-04'] = {'score': 'not', 'evidence': f'No WorkSpaces-specific CloudWatch alarms detected. Fleet of {ws_count} WorkSpaces has no proactive health monitoring.'}

    # ─── OPS-WS-06: Tagging ───
    # (Would need tag:GetResources call - mark as needing manual review)
    findings['OPS-WS-06'] = {'score': '', 'evidence': f'Fleet: {ws_count} WorkSpaces across {len(bundles)} bundle type(s). Tagging compliance requires manual review of tag policies and enforcement.'}

    # ─── OPS-WS-11: PCoIP to DCV Migration ───
    pcoip_count = protocols.get('PCOIP', 0) + protocols.get('PCoIP', 0)
    dcv_count = protocols.get('WSP', 0) + protocols.get('DCV', 0)
    total_proto = pcoip_count + dcv_count
    if total_proto > 0:
        if pcoip_count == 0:
            findings['OPS-WS-11'] = {'score': 'fully', 'evidence': f'All {dcv_count} WorkSpaces are on Amazon DCV protocol. PCoIP migration complete.'}
        elif dcv_count > 0:
            findings['OPS-WS-11'] = {'score': 'partial', 'evidence': f'Mixed protocol fleet: {dcv_count} on DCV, {pcoip_count} still on PCoIP ({round(pcoip_count/total_proto*100)}% remaining to migrate).'}
        else:
            findings['OPS-WS-11'] = {'score': 'not', 'evidence': f'Entire fleet ({pcoip_count} WorkSpaces) on PCoIP. No DCV migration has begun. PCoIP is legacy and approaching end-of-support.'}

    # ─── SEC-WS-01: Directory Integration ───
    if directories:
        dir_info = []
        for d in directories:
            dir_info.append(f"{d['type']} ({d['name']}) - Status: {d.get('status', 'N/A')}")
        findings['SEC-WS-01'] = {'score': 'partial', 'evidence': f'Directory services configured: {"; ".join(dir_info)}. Directory health and least-privilege assessment requires manual review.'}
    else:
        findings['SEC-WS-01'] = {'score': '', 'evidence': 'No directories found via API. May require manual verification.'}

    # ─── SEC-WS-02: MFA ───
    mfa_configured = any(d.get('radiusStatus') not in ['None', None, ''] for d in directories)
    if mfa_configured:
        findings['SEC-WS-02'] = {'score': 'partial', 'evidence': f'RADIUS/MFA configuration detected on directory. Verify MFA is enforced for all connections and fallback procedures exist.'}
    else:
        findings['SEC-WS-02'] = {'score': 'not', 'evidence': f'No RADIUS/MFA configuration detected on any directory ({len(directories)} directories scanned). MFA is not enforced for WorkSpaces connections.'}

    # ─── SEC-WS-03: Device Access Controls ───
    if ip_groups and len(ip_groups) > 0:
        total_rules = sum(len(g.get('UserRules', [])) for g in ip_groups)
        findings['SEC-WS-03'] = {'score': 'partial', 'evidence': f'{len(ip_groups)} IP Access Control Group(s) configured with {total_rules} total rules. Verify groups are attached to directories and cover all required network ranges.'}
    else:
        findings['SEC-WS-03'] = {'score': 'not', 'evidence': 'No IP Access Control Groups configured. Any device from any network can connect to WorkSpaces (subject to credentials only).'}

    # ─── SEC-WS-04: Data at Rest Encryption ───
    if ws_count > 0:
        enc_pct = round(encrypted_count / ws_count * 100)
        if enc_pct >= 95:
            findings['SEC-WS-04'] = {'score': 'fully', 'evidence': f'{encrypted_count}/{ws_count} WorkSpaces have volume encryption enabled ({enc_pct}%). Encryption covers root and/or user volumes using KMS.'}
        elif enc_pct > 0:
            findings['SEC-WS-04'] = {'score': 'partial', 'evidence': f'{encrypted_count}/{ws_count} WorkSpaces have volume encryption ({enc_pct}%). {ws_count - encrypted_count} WorkSpaces have unencrypted volumes.'}
        else:
            findings['SEC-WS-04'] = {'score': 'not', 'evidence': f'No WorkSpaces have volume encryption enabled (0/{ws_count}). Data at rest is not protected by KMS encryption.'}

    # ─── SEC-WS-07: Network Security ───
    evidence_parts = []
    if az_count >= 2:
        evidence_parts.append(f'WorkSpaces subnets span {az_count} Availability Zones')
    else:
        evidence_parts.append(f'WorkSpaces in single AZ only')
    if nat_count > 0:
        evidence_parts.append(f'{nat_count} NAT Gateway(s) detected')
    else:
        evidence_parts.append('No NAT Gateways detected - WorkSpaces may have direct internet access or no egress')
    findings['SEC-WS-07'] = {'score': 'partial' if nat_count > 0 else 'not', 'evidence': '. '.join(evidence_parts) + '.'}

    # ─── REL-WS-01: VPC/Subnet Resilience ───
    if az_count >= 2:
        findings['REL-WS-01'] = {'score': 'fully', 'evidence': f'WorkSpaces subnets configured across {az_count} Availability Zones ({", ".join(scan_data.get("azList", []))}). Multi-AZ resilience is in place.'}
    elif az_count == 1:
        findings['REL-WS-01'] = {'score': 'not', 'evidence': f'WorkSpaces deployed in a single Availability Zone only. No AZ-level resilience - an AZ failure would affect all WorkSpaces.'}

    # ─── REL-WS-02: Directory HA ───
    if directories:
        managed_ad = [d for d in directories if d['type'] in ['MicrosoftAD', 'SharedMicrosoftAD']]
        if managed_ad:
            findings['REL-WS-02'] = {'score': 'fully', 'evidence': f'AWS Managed Microsoft AD deployed ({managed_ad[0]["name"]}). Managed AD provides multi-AZ domain controllers by default.'}
        else:
            ad_connector = [d for d in directories if d['type'] == 'ADConnector']
            if ad_connector:
                findings['REL-WS-02'] = {'score': 'partial', 'evidence': f'AD Connector in use ({ad_connector[0]["name"]}). HA depends on the on-premises domain controllers it targets. Verify multiple DCs are configured.'}

    # ─── COST-WS-01: Running Mode Optimisation ───
    autostop = running_modes.get('AUTO_STOP', 0)
    alwayson = running_modes.get('ALWAYS_ON', 0)
    if ws_count > 0:
        autostop_pct = round(autostop / ws_count * 100)
        findings['COST-WS-01'] = {'score': 'partial' if autostop_pct > 50 else 'not', 'evidence': f'Running modes: {autostop} AutoStop ({autostop_pct}%), {alwayson} AlwaysOn ({100 - autostop_pct}%). Monthly WorkSpaces cost: {monthly_cost} {scan_data.get("costCurrency", "USD")}. Review whether AutoStop/AlwaysOn assignment matches actual usage patterns (breakeven ~80 hours/month).'}

    # ─── COST-WS-04: Bundle Right-Sizing ───
    if len(bundles) == 1:
        findings['COST-WS-04'] = {'score': 'not', 'evidence': f'Single bundle type in use for all {ws_count} WorkSpaces. No persona-based right-sizing. All users receive the same compute regardless of workload requirements.'}
    elif len(bundles) <= 3:
        findings['COST-WS-04'] = {'score': 'partial', 'evidence': f'{len(bundles)} bundle types in use across {ws_count} WorkSpaces. Some differentiation exists but verify bundles are matched to user personas based on utilisation data.'}
    else:
        findings['COST-WS-04'] = {'score': 'fully', 'evidence': f'{len(bundles)} bundle types in use across {ws_count} WorkSpaces. Bundle diversity suggests persona-based sizing is in place.'}

    # ─── PERF-WS-01: Protocol Selection ───
    if total_proto > 0:
        if pcoip_count == 0:
            findings['PERF-WS-01'] = {'score': 'fully', 'evidence': f'All WorkSpaces on Amazon DCV - the strategic protocol with superior features (bidirectional audio/video, 4K, certificate-based auth).'}
        elif dcv_count > pcoip_count:
            findings['PERF-WS-01'] = {'score': 'partial', 'evidence': f'Majority on DCV ({dcv_count}) but {pcoip_count} still on PCoIP. DCV migration is underway.'}
        else:
            findings['PERF-WS-01'] = {'score': 'not', 'evidence': f'Majority ({pcoip_count}/{total_proto}) on PCoIP (legacy). DCV offers better performance, lower bandwidth, and is the strategic direction.'}

    # ─── SUS-WS-01: Resource Provisioning ───
    if ws_count > 0 and autostop > 0:
        findings['SUS-WS-01'] = {'score': 'partial' if autostop_pct >= 70 else 'not', 'evidence': f'{autostop_pct}% of fleet uses AutoStop mode. Stopped WorkSpaces consume minimal resources. Target: majority of fleet on AutoStop unless specific always-on requirement justified.'}

    return findings


def generate_tailored_recommendations(questions_with_notes, reference_context='', template_id='workspaces-default'):
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
    
    # ORR-specific prompt framing
    if template_id == 'orr-default':
        orr_grounding = ("\n\nORR BEST PRACTICES REFERENCE (use to ground your recommendations):\n"
                         + ORR_BEST_PRACTICES + "\n--- END ORR REFERENCE ---\n\n")
        prompt = (
            "You are an AWS Solutions Architect writing a formal Operational Readiness Review (ORR) report. "
            "The ORR assesses whether a workload is ready for production operation. "
            "For each question below, produce two things:\n"
            "1. 'observation': Rewrite the raw reviewer notes as polished, professional prose. "
            "Fix spelling and grammar, write in full sentences, maintain all factual content, use third-person formal tone (e.g. 'The team currently manages...'). "
            "Keep it concise (2-4 sentences).\n"
            "2. 'recommendation': Structured as: a brief acknowledgement of current operational readiness state (1-2 sentences), "
            "then 2-3 next-step bullet points starting with '\u2022 ', focusing on operational readiness gaps and how to close them. "
            "Reference the ORR best practices where relevant (failure modeling, operational processes, event management, release quality, resilience). "
            "Then a 'Further Reading:' line with 1-2 real https://docs.aws.amazon.com URLs related to operational readiness. "
            "IMPORTANT: You MUST include the Further Reading line for EVERY question. Never omit it.\n"
            + orr_grounding + grounding +
            "Format as JSON: {\"QUESTION-ID\": {\"observation\": \"...\", \"recommendation\": \"...\"}}. "
            "Respond with ONLY valid JSON, no markdown fences.\n\nQuestions:\n" + joined)
    else:
        prompt = ("You are an AWS Solutions Architect writing a formal Well-Architected Review report. "
                   "For each question below, produce THREE things:\n"
                   "1. 'observation': Rewrite the raw customer notes as polished, professional prose. "
                   "Fix spelling and grammar, write in full sentences, maintain all factual content, use third-person formal tone (e.g. 'The customer currently manages...'). "
                   "Keep it concise (2-4 sentences).\n"
                   "2. 'recommendation': Structured as: a brief acknowledgement of current state (1-2 sentences), "
                   "then 2-3 next-step bullet points starting with '\u2022 ', "
                   "then a 'Further Reading:' line with 1-2 real https://docs.aws.amazon.com URLs. "
                   "IMPORTANT: You MUST include the Further Reading line for EVERY question. Never omit it.\n"
                   "3. 'userImpact': Explain what this finding means for end users of WorkSpaces (the people who log in and use them daily). "
                   "Focus on tangible impacts: performance changes, required actions (e.g. client updates, password resets), "
                   "downtime, improved experience, or no impact. Write in plain language suitable for non-technical users. "
                   "1-2 sentences. If the finding has no direct end-user impact, state 'No direct impact on end users.'\n"
                   + grounding +
                   "Format as JSON: {\"QUESTION-ID\": {\"observation\": \"...\", \"recommendation\": \"...\", \"userImpact\": \"...\"}}. "
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
                # Skip architecture info files
                if '/arch/' in key:
                    continue
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
            is_arch_analysis = body.get('isArchAnalysis', False)
            review_id = body.get('reviewId', '')
            template_id = body.get('templateId', 'workspaces-default')
            
            # If arch analysis, load context from S3 instead of request body
            if is_arch_analysis and review_id and not reference_context:
                prefix = f"{review_id}/arch/"
                s3_response = s3.list_objects_v2(Bucket=REPORTS_BUCKET, Prefix=prefix)
                context_parts = []
                for obj in s3_response.get('Contents', []):
                    key = obj['Key']
                    if key.endswith('.extracted.txt'):
                        text_obj = s3.get_object(Bucket=REPORTS_BUCKET, Key=key)
                        text = text_obj['Body'].read().decode('utf-8')
                        source_filename = key.replace('.extracted.txt', '').split('/')[-1].split('_', 1)[-1]
                        context_parts.append(f"=== {source_filename} ===\n{text}")
                reference_context = '\n\n'.join(context_parts)
            
            if is_arch_analysis and reference_context:
                # Special architecture analysis mode — use Haiku with a focused prompt
                arch_prompt = (
                    "You are an AWS Solutions Architect assessing architecture documentation against the "
                    "AWS Well-Architected Framework. Based on the architecture documentation below, provide:\n\n"
                    "1. 'observation': A 3-4 sentence summary of the architecture's overall posture — "
                    "what's in place, what patterns are used, and the general maturity level.\n\n"
                    "2. 'recommendation': A JSON object with these keys:\n"
                    "   • GAPS: array of strings (max 5 items, each 1-2 sentences)\n"
                    "   • RISKS: array of strings (max 5 items, each 1-2 sentences)\n"
                    "   • IMPROVEMENTS_NEEDED: array of strings (max 8 items, each 1-2 sentences)\n"
                    "   • POSITIVES: array of strings (max 5 items, each 1-2 sentences)\n\n"
                    "IMPORTANT: Keep each item CONCISE (1-2 sentences max). Prioritise the most critical items. "
                    "Be specific — reference actual services, components, or patterns from the documentation. "
                    "Do NOT give generic advice. Only assess what is evidenced.\n\n"
                    "Format response as JSON ONLY:\n"
                    "{\"ARCH-ANALYSIS\": {\"observation\": \"summary here\", \"recommendation\": {\"GAPS\": [\"...\"], \"RISKS\": [\"...\"], \"IMPROVEMENTS_NEEDED\": [\"...\"], \"POSITIVES\": [\"...\"]}}}\n\n"
                    "ARCHITECTURE DOCUMENTATION:\n" + reference_context[:25000]
                )
                try:
                    response = bedrock.invoke_model(
                        modelId=MODEL_ID,
                        contentType='application/json',
                        accept='application/json',
                        body=json.dumps({
                            'anthropic_version': 'bedrock-2023-05-31',
                            'max_tokens': 8192,
                            'messages': [{'role': 'user', 'content': arch_prompt}]
                        })
                    )
                    result = json.loads(response['body'].read())
                    text = result['content'][0]['text'].strip()
                    text = re.sub(r'^```(?:json)?\s*', '', text)
                    text = re.sub(r'\s*```$', '', text)
                    # Extract just the JSON object (handle extra text after closing brace)
                    brace_count = 0
                    json_end = 0
                    for ci, ch in enumerate(text):
                        if ch == '{': brace_count += 1
                        elif ch == '}': 
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = ci + 1
                                break
                    if json_end > 0:
                        text = text[:json_end]
                    recommendations = json.loads(text)
                except Exception as e:
                    recommendations = {"ARCH-ANALYSIS": {"observation": "Architecture analysis unavailable.", "recommendation": "Error: " + str(e)}}
            else:
                recommendations = generate_tailored_recommendations(questions_with_notes, reference_context, template_id)
            
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'recommendations': recommendations})
            }
        
        if action == 'generateOrr':
            questions_with_notes = body.get('questions', [])
            reference_context = body.get('referenceContext', '')
            recommendations = generate_orr_recommendations(questions_with_notes, reference_context)
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
        
        if action == 'chat':
            question = body['question']
            context_text = body.get('context', '')
            history = body.get('history', [])
            customer_name = body.get('customerName', 'Customer')

            messages = []
            system_prompt = (
                f"You are an AWS Solutions Architect assistant for {customer_name}'s WorkSpaces Well-Architected Review. "
                "Answer questions concisely and accurately using ONLY the review data provided below. "
                "If the answer is not in the context, say so. Use bullet points for lists. "
                "Keep answers to 2-4 sentences unless more detail is specifically requested.\n\n"
                "REVIEW CONTEXT:\n" + context_text[:25000]
            )

            # Add conversation history
            for msg in history[-6:]:  # Keep last 6 messages for context
                messages.append({'role': msg['role'], 'content': msg['content']})
            messages.append({'role': 'user', 'content': question})

            try:
                response = bedrock.invoke_model(
                    modelId=MODEL_ID,
                    contentType='application/json',
                    accept='application/json',
                    body=json.dumps({
                        'anthropic_version': 'bedrock-2023-05-31',
                        'max_tokens': 1024,
                        'system': system_prompt,
                        'messages': messages
                    })
                )
                result = json.loads(response['body'].read())
                answer = result['content'][0]['text'].strip()
                return {
                    'statusCode': 200,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'answer': answer})
                }
            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Chat failed: ' + str(e)})
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
            template_id = body.get('templateId', 'workspaces-default')

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

            # ORR-specific curation prompt
            if template_id == 'orr-default':
                orr_context = (
                    "\n\nORR BEST PRACTICES REFERENCE (use to assess operational readiness gaps):\n"
                    + ORR_BEST_PRACTICES + "\n--- END ORR REFERENCE ---\n\n"
                )
                curation_prompt = f"""You are an AWS Solutions Architect preparing a C-level executive briefing from an Operational Readiness Review (ORR).

The ORR assesses whether this workload is operationally ready for production. It covers failure modeling,
operational processes, event management, release quality, resilience, and security readiness.

CUSTOMER: {customer_name}
OVERALL SCORE: {overall_score}%
CATEGORY SCORES:
{pillar_summary}
{orr_context}{grounding}
FINDINGS:
{joined_findings}

YOUR TASK: Curate these ORR findings into a boardroom-ready narrative focused on operational risk and production readiness. Do NOT map mechanically (RED=MUST, AMBER=SHOULD, GREEN=COULD). Instead, curate intelligently based on operational impact:

RULES:
1. CRITICAL FINDINGS: Select exactly 4 items that pose the highest operational risk — things that could cause production incidents, extended outages, or compliance failures. For each, provide a business-framed headline (e.g. "No Tested Disaster Recovery Plan" not "How do you validate recovery...") and a 2-3 sentence consequence explanation focusing on operational impact (incident duration, blast radius, customer impact, compliance exposure).
2. MUST tier: Items that must be resolved before launch OR immediately if already in production. Focus on: missing failure models, no rollback capability, absent monitoring/alerting, no incident management process, untested recovery. Usually 3-5 items max.
3. SHOULD tier: The 4-6 highest-value operational improvements for this quarter. Focus on: capacity planning gaps, incomplete runbooks, missing canary deployments, alarm fatigue, dependency risks without fallbacks.
4. COULD tier: Strategic operational maturity items. 4-6 items max. Focus on: chaos engineering, advanced observability, multi-region readiness, automated remediation, game day exercises.
5. For each item in any tier, provide: the original ID, a business-framed headline (5-8 words, no "How do you..."), and a one-sentence action summary.
6. NEVER present already-implemented items (scored "fully") as gaps or quick wins.
7. Cost optimisation: Only relevant if operational gaps have cost implications (e.g. over-provisioning due to missing auto-scaling, lack of right-sizing). Otherwise write "Cost impacts are secondary to operational readiness gaps identified above."
8. 90-Day Roadmap: Assign curated items to Week 1-2 (urgent pre-launch blockers), Week 3-6 (operational foundation: monitoring, runbooks, incident process), Week 7-12 (operational maturity: chaos engineering, game days, automation).

WORDING RULES (CRITICAL - apply to ALL text you generate):
9. NEVER use the words "customer", "the customer", or "Customer-1" in any output text. These are BANNED. Use the organisation name "{customer_name}", or "the team", "the workload", "the application", or address the subject directly.
10. Rewrite "Customer recognizes the need to X" as "X is not yet in place" or "The workload currently lacks X". State what IS and what it RISKS operationally. Use executive voice.
11. Keep all text concise — headlines 5-8 words, actions max 2 sentences, consequences max 3 sentences. This is a scannable exec deck, not a report.
12. executiveSummary must be exactly 3-4 SHORT sentences (max 30 words each). State operational readiness posture, key risks to production stability, and recommended focus areas.

Respond with ONLY valid JSON in this exact structure:
{{
  "criticalFindings": [
    {{"id": "ORR-01", "headline": "No Tested Disaster Recovery Plan", "consequence": "2-3 sentence operational consequence", "rag": "red"}}
  ],
  "must": [
    {{"id": "ORR-01", "headline": "Short operational headline", "action": "One sentence action", "effort": "low|medium|high", "isQuickWin": true}}
  ],
  "should": [
    {{"id": "...", "headline": "...", "action": "...", "effort": "low|medium|high"}}
  ],
  "could": [
    {{"id": "...", "headline": "...", "action": "...", "effort": "medium|high"}}
  ],
  "costInsights": {{
    "hasData": false,
    "summary": "Cost assessment focused on operational efficiency in 2-3 sentences",
    "items": [{{"id": "...", "headline": "...", "insight": "..."}}]
  }},
  "roadmap": {{
    "week1_2": [{{"id": "...", "headline": "..."}}],
    "week3_6": [{{"id": "...", "headline": "..."}}],
    "week7_12": [{{"id": "...", "headline": "..."}}]
  }},
  "executiveSummary": "A 3-4 sentence executive summary stating operational readiness posture, key risks to production stability, and recommended focus areas."
}}"""
            else:
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

        if action == 'uploadArchInfo':
            import base64
            from datetime import datetime
            review_id = body['reviewId']
            filename = body['filename']
            content_b64 = body['content']
            content_type = body.get('contentType', 'application/pdf')
            file_bytes = base64.b64decode(content_b64)
            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H%M%S')
            key = f"{review_id}/arch/{timestamp}_{filename}"

            # Store original file in S3
            s3.put_object(
                Bucket=REPORTS_BUCKET, Key=key, Body=file_bytes,
                ContentType=content_type,
                Metadata={'filename': filename, 'timestamp': timestamp, 'extracted': 'false'}
            )

            # Extract text using Bedrock Sonnet (supports document understanding)
            SONNET_MODEL = 'eu.anthropic.claude-sonnet-4-5-20250929-v1:0'
            extract_prompt = (
                "You are an architecture document analyst. Extract ALL meaningful content from this document including:\n"
                "- Architecture descriptions and decisions\n"
                "- Component names, services, and their relationships\n"
                "- Data flows and integration points\n"
                "- Security controls and boundaries\n"
                "- Resilience and availability patterns\n"
                "- Performance considerations\n"
                "- Cost-related decisions\n"
                "- Operational procedures\n\n"
                "Return the extracted information as structured plain text. Preserve all technical details. "
                "If the document contains diagrams, describe them in text form."
            )

            try:
                # Determine media type for Bedrock document block
                if content_type == 'application/pdf':
                    doc_format = 'pdf'
                elif content_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                    doc_format = 'docx'
                else:
                    doc_format = 'pdf'

                # Choose content block type based on file type
                is_image = content_type in ['image/png', 'image/jpeg']

                if is_image:
                    # Use image block for diagrams/screenshots
                    image_format = 'png' if content_type == 'image/png' else 'jpeg'
                    content_block = {
                        'image': {
                            'format': image_format,
                            'source': {
                                'bytes': file_bytes
                            }
                        }
                    }
                else:
                    # Use document block for PDF/Word
                    content_block = {
                        'document': {
                            'name': filename.replace(' ', '_').replace('.', '_'),
                            'format': doc_format,
                            'source': {
                                'bytes': file_bytes
                            }
                        }
                    }

                # Use Converse API for document/image understanding
                response = bedrock.converse(
                    modelId=SONNET_MODEL,
                    messages=[{
                        'role': 'user',
                        'content': [
                            content_block,
                            {
                                'text': extract_prompt
                            }
                        ]
                    }],
                    inferenceConfig={
                        'maxTokens': 8192
                    }
                )
                extracted_text = response['output']['message']['content'][0]['text'].strip()

                # Store extracted text alongside original
                text_key = key + '.extracted.txt'
                s3.put_object(
                    Bucket=REPORTS_BUCKET, Key=text_key,
                    Body=extracted_text.encode('utf-8'),
                    ContentType='text/plain',
                    Metadata={'source_file': key, 'model': SONNET_MODEL}
                )

                # Update original file metadata to mark as extracted
                s3.copy_object(
                    Bucket=REPORTS_BUCKET, Key=key,
                    CopySource={'Bucket': REPORTS_BUCKET, 'Key': key},
                    ContentType=content_type,
                    Metadata={'filename': filename, 'timestamp': timestamp, 'extracted': 'true'},
                    MetadataDirective='REPLACE'
                )

                return {
                    'statusCode': 200,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'message': 'Uploaded and processed', 'key': key, 'extractedChars': len(extracted_text)})
                }
            except Exception as extract_err:
                # File uploaded but extraction failed — log and return error details
                import traceback
                print(f"EXTRACTION ERROR: {type(extract_err).__name__}: {str(extract_err)}")
                print(traceback.format_exc())
                return {
                    'statusCode': 200,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'message': 'Uploaded but extraction failed', 'key': key, 'extractionError': str(extract_err), 'errorType': type(extract_err).__name__})
                }

        if action == 'getArchInfo':
            review_id = body['reviewId']
            prefix = f"{review_id}/arch/"
            response = s3.list_objects_v2(Bucket=REPORTS_BUCKET, Prefix=prefix)
            files = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                # Skip extracted text files
                if key.endswith('.extracted.txt'):
                    continue
                filename_part = key.split('/')[-1]
                # Parse timestamp_filename format
                parts = filename_part.split('_', 1)
                timestamp = parts[0] if len(parts) > 1 else ''
                original_filename = parts[1] if len(parts) > 1 else filename_part
                # Check if extracted text exists
                text_key = key + '.extracted.txt'
                extracted = False
                try:
                    s3.head_object(Bucket=REPORTS_BUCKET, Key=text_key)
                    extracted = True
                except:
                    pass
                files.append({
                    'key': key,
                    'filename': original_filename,
                    'timestamp': timestamp,
                    'size': obj['Size'],
                    'extracted': extracted
                })
            files.sort(key=lambda f: f['timestamp'], reverse=True)
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'files': files})
            }

        if action == 'deleteArchInfo':
            review_id = body['reviewId']
            key = body['key']
            # Delete the original file and its extracted text
            s3.delete_object(Bucket=REPORTS_BUCKET, Key=key)
            try:
                s3.delete_object(Bucket=REPORTS_BUCKET, Key=key + '.extracted.txt')
            except:
                pass
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'deleted': key})
            }

        if action == 'analyseArchitecture':
            # Pre-analysis: Sonnet analyses arch docs against Well-Architected pillars
            # Returns structured findings per pillar + overall assessment
            review_id = body['reviewId']
            customer_name = body.get('customerName', 'Customer')
            pillar_names = body.get('pillars', [
                'Operational Excellence', 'Security', 'Reliability',
                'Performance Efficiency', 'Cost Optimisation', 'Sustainability'
            ])

            # Collect all extracted architecture text
            prefix = f"{review_id}/arch/"
            response = s3.list_objects_v2(Bucket=REPORTS_BUCKET, Prefix=prefix)
            context_parts = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key.endswith('.extracted.txt'):
                    text_obj = s3.get_object(Bucket=REPORTS_BUCKET, Key=key)
                    text = text_obj['Body'].read().decode('utf-8')
                    source_filename = key.replace('.extracted.txt', '').split('/')[-1].split('_', 1)[-1]
                    context_parts.append(f"=== {source_filename} ===\n{text}")

            if not context_parts:
                return {
                    'statusCode': 200,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'findings': [], 'summary': '', 'hasData': False})
                }

            combined_context = '\n\n'.join(context_parts)

            SONNET_MODEL = 'eu.anthropic.claude-sonnet-4-5-20250929-v1:0'
            analysis_prompt = f"""You are an AWS Solutions Architect performing a Well-Architected Review assessment. 
You have been provided with architecture documentation for {customer_name}.

Analyse this architecture against the AWS Well-Architected Framework pillars and identify:
1. Gaps and risks — what's missing or concerning
2. What needs improvement — specific actionable items
3. What's done well — positive aspects to acknowledge

For each pillar, provide:
- A RAG status (red/amber/green) based on what you can determine from the documentation
- 2-4 key findings (gaps, risks, or improvements needed)
- Brief justification for the RAG rating

IMPORTANT RULES:
- Only assess what is evidenced in the documentation. If a pillar has no relevant information, say so.
- Be specific — reference actual components, services, or patterns mentioned in the docs.
- Focus on actionable findings, not generic advice.
- Do NOT use the word "customer" — use "{customer_name}" or "the environment".

Respond with ONLY valid JSON in this exact structure:
{{
  "summary": "2-3 sentence overall architecture assessment",
  "pillars": [
    {{
      "name": "Pillar Name",
      "rag": "red|amber|green",
      "rationale": "1 sentence justification for RAG",
      "findings": [
        {{
          "type": "gap|risk|improvement|positive",
          "finding": "Specific finding description",
          "recommendation": "What should be done (omit for positive type)"
        }}
      ]
    }}
  ],
  "crossCutting": [
    {{
      "finding": "Finding that spans multiple pillars",
      "pillars": ["Pillar1", "Pillar2"],
      "recommendation": "What should be done"
    }}
  ]
}}

ARCHITECTURE DOCUMENTATION:
{combined_context}"""

            try:
                response = bedrock.converse(
                    modelId=SONNET_MODEL,
                    messages=[{
                        'role': 'user',
                        'content': [{'text': analysis_prompt}]
                    }],
                    inferenceConfig={'maxTokens': 8192}
                )
                result_text = response['output']['message']['content'][0]['text'].strip()
                # Clean markdown fences if present
                result_text = re.sub(r'^```(?:json)?\s*', '', result_text)
                result_text = re.sub(r'\s*```$', '', result_text)
                findings = json.loads(result_text)
                return {
                    'statusCode': 200,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'findings': findings, 'hasData': True})
                }
            except Exception as e:
                print(f"ARCHITECTURE ANALYSIS ERROR: {type(e).__name__}: {str(e)}")
                return {
                    'statusCode': 200,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'findings': None, 'hasData': False, 'error': str(e)})
                }

        if action == 'getArchContext':
            # Returns all extracted architecture text for a review (used by report generation)
            review_id = body['reviewId']
            prefix = f"{review_id}/arch/"
            response = s3.list_objects_v2(Bucket=REPORTS_BUCKET, Prefix=prefix)
            context_parts = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key.endswith('.extracted.txt'):
                    text_obj = s3.get_object(Bucket=REPORTS_BUCKET, Key=key)
                    text = text_obj['Body'].read().decode('utf-8')
                    source_filename = key.replace('.extracted.txt', '').split('/')[-1].split('_', 1)[-1]
                    context_parts.append(f"=== Architecture Document: {source_filename} ===\n{text}")
            combined = '\n\n'.join(context_parts)
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'context': combined, 'documentCount': len(context_parts)})
            }

        if action == 'scanAccount':
            role_arn = body['roleArn']
            external_id = body['externalId']
            target_region = body.get('region', 'eu-west-2')
            review_id = body.get('reviewId', '')

            # Assume the cross-account role - use eu-west-2 STS regional endpoint
            sts = boto3.client('sts', region_name='eu-west-2',
                endpoint_url='https://sts.eu-west-2.amazonaws.com')
            try:
                assumed = sts.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName='WAFRReviewToolScan',
                    ExternalId=external_id,
                    DurationSeconds=3600
                )
            except Exception as e:
                return {
                    'statusCode': 200,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'error': f'Failed to assume role: {str(e)}. Check the Role ARN, External ID, and trust policy.'})
                }

            creds = assumed['Credentials']
            session_kwargs = {
                'aws_access_key_id': creds['AccessKeyId'],
                'aws_secret_access_key': creds['SecretAccessKey'],
                'aws_session_token': creds['SessionToken'],
                'region_name': target_region
            }

            # Create clients with assumed credentials
            ws_client = boto3.client('workspaces', **session_kwargs)
            ds_client = boto3.client('ds', **session_kwargs)
            ec2_client = boto3.client('ec2', **session_kwargs)
            cw_client = boto3.client('cloudwatch', **session_kwargs)
            ce_client = boto3.client('ce', region_name='us-east-1',
                aws_access_key_id=creds['AccessKeyId'],
                aws_secret_access_key=creds['SecretAccessKey'],
                aws_session_token=creds['SessionToken'])

            findings = {}
            scan_data = {}

            # ─── WORKSPACES FLEET ─────────────────────────────────────────
            try:
                all_workspaces = []
                paginator = ws_client.get_paginator('describe_workspaces')
                for page in paginator.paginate():
                    all_workspaces.extend(page.get('Workspaces', []))
                scan_data['workspaces'] = all_workspaces
                scan_data['workspaceCount'] = len(all_workspaces)

                # Protocol analysis
                protocols = {}
                bundles_used = {}
                running_modes = {}
                encrypted_count = 0
                for ws in all_workspaces:
                    proto = ws.get('WorkspaceProperties', {}).get('Protocols', ['PCOIP'])
                    for p in (proto if isinstance(proto, list) else [proto]):
                        protocols[p] = protocols.get(p, 0) + 1
                    bundle = ws.get('BundleId', 'Unknown')
                    bundles_used[bundle] = bundles_used.get(bundle, 0) + 1
                    mode = ws.get('WorkspaceProperties', {}).get('RunningMode', 'AUTO_STOP')
                    running_modes[mode] = running_modes.get(mode, 0) + 1
                    if ws.get('RootVolumeEncryptionEnabled') or ws.get('UserVolumeEncryptionEnabled'):
                        encrypted_count += 1

                scan_data['protocols'] = protocols
                scan_data['bundles'] = bundles_used
                scan_data['runningModes'] = running_modes
                scan_data['encryptedCount'] = encrypted_count
            except Exception as e:
                scan_data['workspacesError'] = str(e)

            # ─── DIRECTORIES ──────────────────────────────────────────────
            try:
                dirs_response = ds_client.describe_directories()
                directories = dirs_response.get('DirectoryDescriptions', [])
                scan_data['directories'] = []
                for d in directories:
                    scan_data['directories'].append({
                        'id': d.get('DirectoryId'),
                        'name': d.get('Name'),
                        'type': d.get('Type'),
                        'size': d.get('Size'),
                        'edition': d.get('Edition', 'N/A'),
                        'status': d.get('Stage'),
                        'vpcId': d.get('VpcSettings', {}).get('VpcId'),
                        'subnetIds': d.get('VpcSettings', {}).get('SubnetIds', []),
                        'dnsIpAddrs': d.get('DnsIpAddrs', []),
                        'radiusStatus': d.get('RadiusSettings', {}).get('RadiusStatus', 'None'),
                        'ssoEnabled': d.get('SsoEnabled', False)
                    })
            except Exception as e:
                scan_data['directoriesError'] = str(e)

            # ─── WORKSPACES DIRECTORIES (IP Access, Device Settings) ──────
            try:
                ws_dirs = ws_client.describe_workspace_directories()
                scan_data['wsDirectories'] = []
                for wd in ws_dirs.get('Directories', []):
                    scan_data['wsDirectories'].append({
                        'directoryId': wd.get('DirectoryId'),
                        'directoryType': wd.get('DirectoryType'),
                        'state': wd.get('State'),
                        'ipGroupIds': wd.get('ipGroupIds', []),
                        'selfServicePermissions': wd.get('SelfservicePermissions', {}),
                        'workspaceAccessProperties': wd.get('WorkspaceAccessProperties', {}),
                        'workspaceCreationProperties': wd.get('WorkspaceCreationProperties', {})
                    })
            except Exception as e:
                scan_data['wsDirectoriesError'] = str(e)

            # ─── IP ACCESS GROUPS ─────────────────────────────────────────
            try:
                ip_groups = ws_client.describe_ip_groups()
                scan_data['ipGroups'] = ip_groups.get('Result', [])
            except Exception as e:
                scan_data['ipGroupsError'] = str(e)

            # ─── VPC / NETWORKING ─────────────────────────────────────────
            try:
                # Get VPCs used by directories
                vpc_ids = set()
                for d in scan_data.get('directories', []):
                    if d.get('vpcId'):
                        vpc_ids.add(d['vpcId'])
                # If no VPCs from directories, get all VPCs in the account
                if not vpc_ids:
                    all_vpcs = ec2_client.describe_vpcs()
                    vpc_ids = set(v['VpcId'] for v in all_vpcs.get('Vpcs', []))
                    scan_data['vpcs'] = all_vpcs.get('Vpcs', [])
                else:
                    vpcs = ec2_client.describe_vpcs(VpcIds=list(vpc_ids))
                    scan_data['vpcs'] = vpcs.get('Vpcs', [])
                # Get all subnets in those VPCs
                if vpc_ids:
                    subnets = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': list(vpc_ids)}])
                    scan_data['subnets'] = subnets.get('Subnets', [])
                    azs = set(s['AvailabilityZone'] for s in scan_data['subnets'])
                    scan_data['azCount'] = len(azs)
                    scan_data['azList'] = list(azs)
                    scan_data['subnetCount'] = len(scan_data['subnets'])
                    # NAT Gateways
                    nats = ec2_client.describe_nat_gateways(
                        Filter=[{'Name': 'vpc-id', 'Values': list(vpc_ids)}, {'Name': 'state', 'Values': ['available']}]
                    )
                    scan_data['natGateways'] = len(nats.get('NatGateways', []))
                    # VPC Endpoints
                    endpoints = ec2_client.describe_vpc_endpoints(Filters=[{'Name': 'vpc-id', 'Values': list(vpc_ids)}])
                    scan_data['vpcEndpoints'] = [e.get('ServiceName', '').split('.')[-1] for e in endpoints.get('VpcEndpoints', [])]
                    # Security Groups
                    sgs = ec2_client.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': list(vpc_ids)}])
                    scan_data['securityGroups'] = []
                    for sg in sgs.get('SecurityGroups', []):
                        open_to_all = any('0.0.0.0/0' in str(r.get('IpRanges', [])) for r in sg.get('IpPermissions', []))
                        scan_data['securityGroups'].append({
                            'name': sg.get('GroupName'),
                            'id': sg.get('GroupId'),
                            'inboundRules': len(sg.get('IpPermissions', [])),
                            'outboundRules': len(sg.get('IpPermissionsEgress', [])),
                            'openToAll': open_to_all
                        })
            except Exception as e:
                scan_data['networkingError'] = str(e)

            # ─── CLOUDWATCH & CLOUDTRAIL ─────────────────────────────────
            try:
                from datetime import datetime, timedelta
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=7)
                # Check for Unhealthy WorkSpaces metric
                unhealthy = cw_client.get_metric_statistics(
                    Namespace='AWS/WorkSpaces',
                    MetricName='Unhealthy',
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=['Maximum']
                )
                scan_data['unhealthyMetric'] = unhealthy.get('Datapoints', [])
                # All alarms
                alarms = cw_client.describe_alarms(MaxRecords=100)
                all_alarms = alarms.get('MetricAlarms', [])
                ws_alarms = [a for a in all_alarms if 'WorkSpaces' in a.get('Namespace', '') or 'workspace' in a.get('AlarmName', '').lower()]
                scan_data['workspacesAlarms'] = len(ws_alarms)
                scan_data['totalAlarms'] = len(all_alarms)
                scan_data['alarmNames'] = [a['AlarmName'] for a in ws_alarms[:10]]
                # CloudWatch dashboards
                dashboards = cw_client.list_dashboards()
                scan_data['dashboards'] = [d['DashboardName'] for d in dashboards.get('DashboardEntries', [])]
                # CloudWatch Log Groups (WorkSpaces related)
                logs_client = boto3.client('logs', **session_kwargs)
                log_groups = logs_client.describe_log_groups(limit=50)
                scan_data['logGroups'] = [lg['logGroupName'] for lg in log_groups.get('logGroups', [])]
                scan_data['wsLogGroups'] = [lg for lg in scan_data['logGroups'] if 'workspace' in lg.lower() or 'workspaces' in lg.lower()]
                # Active WorkSpaces metrics
                metrics = cw_client.list_metrics(Namespace='AWS/WorkSpaces')
                scan_data['activeMetrics'] = list(set(m['MetricName'] for m in metrics.get('Metrics', [])))
            except Exception as e:
                scan_data['monitoringError'] = str(e)

            # ─── CLOUDTRAIL ───────────────────────────────────────────────
            try:
                ct_client = boto3.client('cloudtrail', **session_kwargs)
                trails = ct_client.describe_trails()
                scan_data['cloudTrail'] = []
                for trail in trails.get('trailList', []):
                    trail_status = ct_client.get_trail_status(Name=trail['TrailARN'])
                    scan_data['cloudTrail'].append({
                        'name': trail.get('Name'),
                        'isMultiRegion': trail.get('IsMultiRegionTrail', False),
                        'isOrganizationTrail': trail.get('IsOrganizationTrail', False),
                        'isLogging': trail_status.get('IsLogging', False),
                        'hasLogFileValidation': trail.get('LogFileValidationEnabled', False),
                        's3Bucket': trail.get('S3BucketName', ''),
                        'cloudWatchLogGroup': trail.get('CloudWatchLogsLogGroupArn', 'None')
                    })
            except Exception as e:
                scan_data['cloudTrailError'] = str(e)

            # ─── WORKSPACES IMAGES ────────────────────────────────────────
            try:
                images = ws_client.describe_workspace_images(ImageType='OWNED')
                scan_data['images'] = [{'id': img.get('ImageId'), 'name': img.get('Name', ''), 'os': img.get('OperatingSystem', {}).get('Type', ''), 'state': img.get('State', ''), 'created': str(img.get('Created', ''))} for img in images.get('Images', [])]
            except Exception as e:
                scan_data['imagesError'] = str(e)

            # ─── WORKSPACES BUNDLES (custom) ──────────────────────────────
            try:
                bundles_resp = ws_client.describe_workspace_bundles(Owner='AMAZON')
                custom_bundles = ws_client.describe_workspace_bundles()
                scan_data['customBundles'] = [{'id': b.get('BundleId'), 'name': b.get('Name', ''), 'compute': b.get('ComputeType', {}).get('Name', ''), 'rootStorage': b.get('RootStorage', {}).get('Capacity', ''), 'userStorage': b.get('UserStorage', {}).get('Capacity', '')} for b in custom_bundles.get('Bundles', []) if b.get('Owner') != 'Amazon']
            except Exception as e:
                scan_data['bundlesError'] = str(e)

            # ─── CONNECTION STATUS (unused WorkSpaces) ────────────────────
            try:
                from datetime import datetime, timedelta
                conn_status = ws_client.describe_workspaces_connection_status()
                inactive_count = 0
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                for cs in conn_status.get('WorkspacesConnectionStatus', []):
                    last_known = cs.get('LastKnownUserConnectionTimestamp')
                    if last_known and last_known.replace(tzinfo=None) < thirty_days_ago:
                        inactive_count += 1
                    elif not last_known:
                        inactive_count += 1
                scan_data['inactiveWorkspaces'] = inactive_count
                scan_data['totalConnectionStatuses'] = len(conn_status.get('WorkspacesConnectionStatus', []))
            except Exception as e:
                scan_data['connectionStatusError'] = str(e)

            # ─── TAGS (sample WorkSpaces for tagging compliance) ──────────
            try:
                tagged_count = 0
                untagged_count = 0
                sample_tags = {}
                for ws in all_workspaces[:10]:
                    try:
                        tags_resp = ws_client.describe_tags(ResourceId=ws['WorkspaceId'])
                        tags = tags_resp.get('TagList', [])
                        if tags:
                            tagged_count += 1
                            for t in tags:
                                sample_tags[t['Key']] = sample_tags.get(t['Key'], 0) + 1
                        else:
                            untagged_count += 1
                    except:
                        untagged_count += 1
                scan_data['tagging'] = {'tagged': tagged_count, 'untagged': untagged_count, 'sampleSize': min(len(all_workspaces), 10), 'tagKeys': list(sample_tags.keys())}
            except Exception as e:
                scan_data['taggingError'] = str(e)

            # ─── ROUTE TABLES ─────────────────────────────────────────────
            try:
                if vpc_ids:
                    route_tables = ec2_client.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': list(vpc_ids)}])
                    scan_data['routeTables'] = []
                    for rt in route_tables.get('RouteTables', []):
                        has_igw = any('igw-' in str(r.get('GatewayId', '')) for r in rt.get('Routes', []))
                        has_nat = any('nat-' in str(r.get('NatGatewayId', '')) for r in rt.get('Routes', []))
                        scan_data['routeTables'].append({'id': rt['RouteTableId'], 'hasInternetGateway': has_igw, 'hasNatGateway': has_nat, 'routeCount': len(rt.get('Routes', []))})
            except Exception as e:
                scan_data['routeTablesError'] = str(e)

            # ─── EVENTBRIDGE RULES ────────────────────────────────────────
            try:
                eb_client = boto3.client('events', **session_kwargs)
                rules = eb_client.list_rules(Limit=50)
                ws_rules = [r for r in rules.get('Rules', []) if 'workspace' in r.get('Name', '').lower() or 'workspace' in str(r.get('Description', '')).lower() or 'aws.workspaces' in str(r.get('EventPattern', '')).lower()]
                scan_data['eventBridgeRules'] = {'total': len(rules.get('Rules', [])), 'workspacesRelated': len(ws_rules), 'ruleNames': [r['Name'] for r in ws_rules[:5]]}
            except Exception as e:
                scan_data['eventBridgeError'] = str(e)

            # ─── AWS BACKUP ───────────────────────────────────────────────
            try:
                backup_client = boto3.client('backup', **session_kwargs)
                plans = backup_client.list_backup_plans()
                scan_data['backupPlans'] = [{'name': p.get('BackupPlanName', ''), 'id': p.get('BackupPlanId', '')} for p in plans.get('BackupPlansList', [])]
                # Check for protected WorkSpaces resources
                try:
                    protected = backup_client.list_protected_resources(MaxResults=100)
                    ws_protected = [r for r in protected.get('Results', []) if 'workspaces' in r.get('ResourceType', '').lower() or 'ec2' in r.get('ResourceType', '').lower()]
                    scan_data['backupProtectedResources'] = len(ws_protected)
                except:
                    scan_data['backupProtectedResources'] = 0
            except Exception as e:
                scan_data['backupError'] = str(e)

            # ─── IAM (WorkSpaces-related roles) ───────────────────────────
            try:
                iam_client = boto3.client('iam', **session_kwargs)
                roles = iam_client.list_roles(MaxItems=100)
                ws_roles = [r['RoleName'] for r in roles.get('Roles', []) if 'workspace' in r['RoleName'].lower() or 'workspaces' in r.get('Description', '').lower()]
                scan_data['iamRoles'] = {'totalRoles': len(roles.get('Roles', [])), 'workspacesRoles': ws_roles}
            except Exception as e:
                scan_data['iamError'] = str(e)

            # ─── WORKSPACES ACCOUNT CONFIG (BYOL/Tenancy) ─────────────────
            try:
                account_info = ws_client.describe_account()
                scan_data['accountConfig'] = {
                    'dedicatedTenancy': account_info.get('DedicatedTenancySupport', 'DISABLED'),
                    'dedicatedTenancyManagementCidr': account_info.get('DedicatedTenancyManagementCidrRange', 'None'),
                    'dedicatedTenancyAuthorization': account_info.get('DedicatedTenancyAccountType', 'None')
                }
            except Exception as e:
                scan_data['accountConfigError'] = str(e)

            # ─── CLIENT PROPERTIES (redirection/reconnect) ────────────────
            try:
                dir_ids = [d.get('id') or d.get('DirectoryId', '') for d in scan_data.get('directories', [])] or [wd.get('directoryId', '') for wd in scan_data.get('wsDirectories', [])]
                if dir_ids and dir_ids[0]:
                    client_props = ws_client.describe_client_properties(ResourceIds=dir_ids[:5])
                    scan_data['clientProperties'] = [{'resourceId': cp.get('ResourceId', ''), 'reconnectEnabled': cp.get('ClientProperties', {}).get('ReconnectEnabled', ''), 'logUploadEnabled': cp.get('ClientProperties', {}).get('LogUploadEnabled', '')} for cp in client_props.get('ClientPropertiesList', [])]
            except Exception as e:
                scan_data['clientPropsError'] = str(e)

            # ─── WORKSPACE SNAPSHOTS (sample - first 5 WorkSpaces) ────────
            try:
                snapshot_data = []
                for ws in all_workspaces[:5]:
                    try:
                        snaps = ws_client.describe_workspace_snapshots(WorkspaceId=ws['WorkspaceId'])
                        rebuild_snaps = snaps.get('RebuildSnapshots', [])
                        restore_snaps = snaps.get('RestoreSnapshots', [])
                        snapshot_data.append({'workspaceId': ws['WorkspaceId'], 'rebuildSnapshots': len(rebuild_snaps), 'restoreSnapshots': len(restore_snaps)})
                    except:
                        pass
                scan_data['snapshots'] = snapshot_data
            except Exception as e:
                scan_data['snapshotsError'] = str(e)

            # ─── CONNECTION ALIASES (cross-region DR) ─────────────────────
            try:
                aliases = ws_client.describe_connection_aliases()
                scan_data['connectionAliases'] = [{'id': a.get('ConnectionAliasId', ''), 'state': a.get('State', ''), 'owner': a.get('OwnerAccountId', '')} for a in aliases.get('ConnectionAliases', [])]
            except Exception as e:
                scan_data['connectionAliasesError'] = str(e)

            # ─── SSM PATCH COMPLIANCE ─────────────────────────────────────
            try:
                ssm_client = boto3.client('ssm', **session_kwargs)
                instances = ssm_client.describe_instance_information(MaxResults=50)
                managed_instances = instances.get('InstanceInformationList', [])
                ws_managed = [i for i in managed_instances if 'workspace' in i.get('Name', '').lower() or i.get('ResourceType', '') == 'ManagedInstance']
                compliant_count = 0
                non_compliant_count = 0
                if managed_instances:
                    try:
                        compliance = ssm_client.list_compliance_summaries(
                            Filters=[{'Key': 'ComplianceType', 'Values': ['Patch'], 'Type': 'EQUAL'}]
                        )
                        for s in compliance.get('ComplianceSummaryItems', []):
                            compliant_count += s.get('CompliantSummary', {}).get('CompliantCount', 0)
                            non_compliant_count += s.get('NonCompliantSummary', {}).get('NonCompliantCount', 0)
                    except:
                        pass
                scan_data['ssmCompliance'] = {
                    'totalManagedInstances': len(managed_instances),
                    'workspacesManaged': len(ws_managed),
                    'patchCompliant': compliant_count,
                    'patchNonCompliant': non_compliant_count
                }
            except Exception as e:
                scan_data['ssmError'] = str(e)

            # ─── AWS CONFIG (compliance rules) ────────────────────────────
            try:
                config_client = boto3.client('config', **session_kwargs)
                rules = config_client.describe_config_rules(Limit=50) if hasattr(config_client, 'describe_config_rules') else {'ConfigRules': []}
                config_rules = rules.get('ConfigRules', [])
                ws_rules = [r['ConfigRuleName'] for r in config_rules if 'workspace' in r.get('ConfigRuleName', '').lower() or 'ec2' in r.get('ConfigRuleName', '').lower()]
                scan_data['configRules'] = {'totalRules': len(config_rules), 'relevantRules': ws_rules[:10]}
            except Exception as e:
                scan_data['configError'] = str(e)

            # ─── COST EXPLORER ────────────────────────────────────────────
            try:
                from datetime import datetime, timedelta
                end_date = datetime.utcnow().strftime('%Y-%m-%d')
                start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
                cost_response = ce_client.get_cost_and_usage(
                    TimePeriod={'Start': start_date, 'End': end_date},
                    Granularity='MONTHLY',
                    Metrics=['UnblendedCost'],
                    Filter={'Dimensions': {'Key': 'SERVICE', 'Values': ['Amazon WorkSpaces']}}
                )
                total_cost = 0
                for result in cost_response.get('ResultsByTime', []):
                    total_cost += float(result.get('Total', {}).get('UnblendedCost', {}).get('Amount', 0))
                scan_data['monthlyCost'] = round(total_cost, 2)
                scan_data['costCurrency'] = cost_response.get('ResultsByTime', [{}])[0].get('Total', {}).get('UnblendedCost', {}).get('Unit', 'USD') if cost_response.get('ResultsByTime') else 'USD'
            except Exception as e:
                scan_data['costError'] = str(e)

            # ─── MAP FINDINGS TO REVIEW QUESTIONS ─────────────────────────
            findings = map_scan_to_findings(scan_data)

            # Build raw evidence summary for Auto WAFR analysis
            raw_evidence = {}
            raw_evidence['fleet'] = f"Total WorkSpaces: {scan_data.get('workspaceCount', 0)}. Protocols: {scan_data.get('protocols', {})}. Running modes: {scan_data.get('runningModes', {})}. Bundle types: {len(scan_data.get('bundles', {}))} distinct. Encryption: {scan_data.get('encryptedCount', 0)}/{scan_data.get('workspaceCount', 0)} encrypted."
            if scan_data.get('directories'):
                dir_details = [f"Type: {d.get('type')}, Name: {d.get('name')}, Status: {d.get('status')}, RADIUS/MFA: {d.get('radiusStatus', 'None')}" for d in scan_data['directories']]
                raw_evidence['directories'] = f"{len(scan_data['directories'])} directories: " + "; ".join(dir_details)
            if scan_data.get('wsDirectories'):
                ws_dir_details = [f"ID: {wd.get('directoryId')}, Type: {wd.get('directoryType')}, IP Groups: {wd.get('ipGroupIds', [])}, Self-service: {wd.get('selfServicePermissions', {})}" for wd in scan_data['wsDirectories']]
                raw_evidence['directorySettings'] = "; ".join(ws_dir_details)
            if scan_data.get('ipGroups') is not None:
                if scan_data['ipGroups']:
                    raw_evidence['ipAccessGroups'] = f"{len(scan_data['ipGroups'])} IP Access Group(s): " + "; ".join([f"{g.get('groupName', 'unnamed')} with {len(g.get('UserRules', []))} rules" for g in scan_data['ipGroups']])
                else:
                    raw_evidence['ipAccessGroups'] = "No IP Access Control Groups configured. Any network can connect."
            if scan_data.get('azCount') is not None:
                vpc_info = f"VPCs: {len(scan_data.get('vpcs', []))}. "
                vpc_info += f"Subnets: {scan_data.get('subnetCount', 0)} across {scan_data.get('azCount', 0)} AZs ({scan_data.get('azList', [])}). "
                vpc_info += f"NAT Gateways: {scan_data.get('natGateways', 0)}. "
                if scan_data.get('vpcEndpoints'):
                    vpc_info += f"VPC Endpoints: {scan_data['vpcEndpoints']}. "
                if scan_data.get('securityGroups'):
                    sg_count = len(scan_data['securityGroups'])
                    open_sgs = [sg['name'] for sg in scan_data['securityGroups'] if sg.get('openToAll')]
                    vpc_info += f"Security Groups: {sg_count} total."
                    if open_sgs:
                        vpc_info += f" WARNING: {len(open_sgs)} SG(s) open to 0.0.0.0/0: {open_sgs}."
                raw_evidence['networking'] = vpc_info
            if scan_data.get('workspacesAlarms') is not None:
                mon_info = f"Total CloudWatch alarms: {scan_data.get('totalAlarms', 0)}. WorkSpaces-specific alarms: {scan_data.get('workspacesAlarms', 0)}."
                if scan_data.get('alarmNames'):
                    mon_info += f" Alarm names: {scan_data['alarmNames']}."
                if scan_data.get('dashboards'):
                    mon_info += f" Dashboards: {scan_data['dashboards']}."
                else:
                    mon_info += " No CloudWatch dashboards configured."
                if scan_data.get('activeMetrics'):
                    mon_info += f" Active WorkSpaces metrics: {scan_data['activeMetrics']}."
                if scan_data.get('wsLogGroups'):
                    mon_info += f" WorkSpaces log groups: {scan_data['wsLogGroups']}."
                else:
                    mon_info += " No WorkSpaces-specific log groups found."
                raw_evidence['monitoring'] = mon_info
            if scan_data.get('cloudTrail'):
                ct_info = f"{len(scan_data['cloudTrail'])} CloudTrail trail(s): "
                ct_details = []
                for ct in scan_data['cloudTrail']:
                    ct_details.append(f"{ct['name']} (logging: {ct['isLogging']}, multi-region: {ct['isMultiRegion']}, log validation: {ct['hasLogFileValidation']}, CloudWatch: {ct.get('cloudWatchLogGroup', 'None')})")
                ct_info += "; ".join(ct_details)
                raw_evidence['cloudTrail'] = ct_info
            elif scan_data.get('cloudTrailError'):
                raw_evidence['cloudTrail'] = f"CloudTrail scan error: {scan_data['cloudTrailError']}"
            else:
                raw_evidence['cloudTrail'] = "No CloudTrail trails configured in this account."
            if scan_data.get('monthlyCost') is not None:
                raw_evidence['cost'] = f"Monthly WorkSpaces cost: ${scan_data.get('monthlyCost', 0)} {scan_data.get('costCurrency', 'USD')}."
            # Images
            if scan_data.get('images'):
                img_details = [f"{img['name']} (OS: {img['os']}, State: {img['state']}, Created: {img['created']})" for img in scan_data['images']]
                raw_evidence['images'] = f"{len(scan_data['images'])} custom image(s): " + "; ".join(img_details)
            # Custom bundles
            if scan_data.get('customBundles'):
                bundle_details = [f"{b['name']} (Compute: {b['compute']}, Root: {b['rootStorage']}GB, User: {b['userStorage']}GB)" for b in scan_data['customBundles']]
                raw_evidence['customBundles'] = f"{len(scan_data['customBundles'])} custom bundle(s): " + "; ".join(bundle_details)
            # Connection status / unused WorkSpaces
            if scan_data.get('inactiveWorkspaces') is not None:
                raw_evidence['utilisation'] = f"Inactive WorkSpaces (no connection in 30+ days): {scan_data['inactiveWorkspaces']} of {scan_data.get('totalConnectionStatuses', 0)}."
            # Tagging
            if scan_data.get('tagging'):
                t = scan_data['tagging']
                raw_evidence['tagging'] = f"Tagging compliance (sample of {t['sampleSize']}): {t['tagged']} tagged, {t['untagged']} untagged. Tag keys found: {t['tagKeys']}."
            # Route tables
            if scan_data.get('routeTables'):
                rt_with_igw = len([r for r in scan_data['routeTables'] if r['hasInternetGateway']])
                rt_with_nat = len([r for r in scan_data['routeTables'] if r['hasNatGateway']])
                raw_evidence['routing'] = f"{len(scan_data['routeTables'])} route table(s). {rt_with_igw} with Internet Gateway, {rt_with_nat} with NAT Gateway."
            # EventBridge
            if scan_data.get('eventBridgeRules'):
                eb = scan_data['eventBridgeRules']
                raw_evidence['automation'] = f"EventBridge: {eb['total']} total rules, {eb['workspacesRelated']} WorkSpaces-related. Rule names: {eb['ruleNames']}."
            # Backup
            if scan_data.get('backupPlans') is not None:
                if scan_data['backupPlans']:
                    raw_evidence['backup'] = f"{len(scan_data['backupPlans'])} backup plan(s): {[p['name'] for p in scan_data['backupPlans']]}. Protected resources: {scan_data.get('backupProtectedResources', 0)}."
                else:
                    raw_evidence['backup'] = "No AWS Backup plans configured."
            # IAM
            if scan_data.get('iamRoles'):
                iam = scan_data['iamRoles']
                raw_evidence['iam'] = f"IAM: {iam['totalRoles']} total roles. WorkSpaces-related roles: {iam['workspacesRoles'] if iam['workspacesRoles'] else 'None found'}."
            # Account config (BYOL)
            if scan_data.get('accountConfig'):
                ac = scan_data['accountConfig']
                raw_evidence['accountConfig'] = f"Dedicated tenancy: {ac['dedicatedTenancy']}. Management CIDR: {ac['dedicatedTenancyManagementCidr']}."
            # Client properties
            if scan_data.get('clientProperties'):
                cp_details = [f"Dir {cp['resourceId']}: reconnect={cp['reconnectEnabled']}, logUpload={cp['logUploadEnabled']}" for cp in scan_data['clientProperties']]
                raw_evidence['clientSettings'] = f"Client properties: " + "; ".join(cp_details)
            # Snapshots
            if scan_data.get('snapshots'):
                total_rebuild = sum(s['rebuildSnapshots'] for s in scan_data['snapshots'])
                total_restore = sum(s['restoreSnapshots'] for s in scan_data['snapshots'])
                raw_evidence['snapshots'] = f"WorkSpace snapshots (sample of {len(scan_data['snapshots'])}): {total_rebuild} rebuild snapshot(s), {total_restore} restore snapshot(s) available."
            # Connection aliases (DR)
            if scan_data.get('connectionAliases') is not None:
                if scan_data['connectionAliases']:
                    raw_evidence['drReadiness'] = f"{len(scan_data['connectionAliases'])} connection alias(es) configured for cross-region failover."
                else:
                    raw_evidence['drReadiness'] = "No connection aliases configured. No cross-region DR capability for WorkSpaces."
            # SSM compliance
            if scan_data.get('ssmCompliance'):
                ssm = scan_data['ssmCompliance']
                raw_evidence['patchCompliance'] = f"SSM: {ssm['totalManagedInstances']} managed instances, {ssm['workspacesManaged']} WorkSpaces-managed. Patch compliance: {ssm['patchCompliant']} compliant, {ssm['patchNonCompliant']} non-compliant."
            # AWS Config
            if scan_data.get('configRules'):
                cfg = scan_data['configRules']
                raw_evidence['configCompliance'] = f"AWS Config: {cfg['totalRules']} rules. Relevant rules: {cfg['relevantRules'] if cfg['relevantRules'] else 'None WorkSpaces-specific'}."

            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'findings': findings, 'rawEvidence': raw_evidence, 'summary': {
                    'workspaceCount': scan_data.get('workspaceCount', 0),
                    'directoryCount': len(scan_data.get('directories', [])),
                    'protocols': scan_data.get('protocols', {}),
                    'runningModes': scan_data.get('runningModes', {}),
                    'azCount': scan_data.get('azCount', 0),
                    'monthlyCost': scan_data.get('monthlyCost', 'N/A'),
                    'encryptedCount': scan_data.get('encryptedCount', 0),
                    'alarmCount': scan_data.get('workspacesAlarms', 0)
                }})
            }

        if action == 'autoWafr':
            # Auto WAFR: scan account, gather all evidence, send to Bedrock for analysis
            role_arn = body['roleArn']
            external_id = body.get('externalId', '')
            target_region = body.get('region', 'eu-west-2')
            review_id = body.get('reviewId', '')

            # Step 1: Assume cross-account role
            sts = boto3.client('sts', region_name='eu-west-2',
                endpoint_url='https://sts.eu-west-2.amazonaws.com')
            try:
                assume_kwargs = {'RoleArn': role_arn, 'RoleSessionName': 'WAFRAutoScan', 'DurationSeconds': 3600}
                if external_id:
                    assume_kwargs['ExternalId'] = external_id
                assumed = sts.assume_role(**assume_kwargs)
            except Exception as e:
                return {
                    'statusCode': 200,
                    'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                    'body': json.dumps({'error': f'Failed to assume role: {str(e)}'})
                }

            creds = assumed['Credentials']
            session_kwargs = {
                'aws_access_key_id': creds['AccessKeyId'],
                'aws_secret_access_key': creds['SecretAccessKey'],
                'aws_session_token': creds['SessionToken'],
                'region_name': target_region
            }

            ws_client = boto3.client('workspaces', **session_kwargs)
            ds_client = boto3.client('ds', **session_kwargs)
            ec2_client = boto3.client('ec2', **session_kwargs)
            cw_client = boto3.client('cloudwatch', **session_kwargs)
            ce_client = boto3.client('ce', region_name='us-east-1',
                aws_access_key_id=creds['AccessKeyId'],
                aws_secret_access_key=creds['SecretAccessKey'],
                aws_session_token=creds['SessionToken'])

            # Step 2: Gather ALL evidence from the account
            evidence = {}

            # WorkSpaces fleet
            try:
                all_workspaces = []
                paginator = ws_client.get_paginator('describe_workspaces')
                for page in paginator.paginate():
                    all_workspaces.extend(page.get('Workspaces', []))
                protocols = {}
                bundles_used = {}
                running_modes = {}
                encrypted_count = 0
                states = {}
                for ws in all_workspaces:
                    proto = ws.get('WorkspaceProperties', {}).get('Protocols', ['PCOIP'])
                    for p in (proto if isinstance(proto, list) else [proto]):
                        protocols[p] = protocols.get(p, 0) + 1
                    bundle = ws.get('BundleId', 'Unknown')
                    bundles_used[bundle] = bundles_used.get(bundle, 0) + 1
                    mode = ws.get('WorkspaceProperties', {}).get('RunningMode', 'AUTO_STOP')
                    running_modes[mode] = running_modes.get(mode, 0) + 1
                    if ws.get('RootVolumeEncryptionEnabled') or ws.get('UserVolumeEncryptionEnabled'):
                        encrypted_count += 1
                    state = ws.get('State', 'UNKNOWN')
                    states[state] = states.get(state, 0) + 1
                evidence['fleet'] = f"Total WorkSpaces: {len(all_workspaces)}. Protocols: {protocols}. Running modes: {running_modes}. Bundle types: {len(bundles_used)} distinct. Encryption: {encrypted_count}/{len(all_workspaces)} encrypted. States: {states}."
            except Exception as e:
                evidence['fleet'] = f"Error scanning fleet: {str(e)}"

            # Directories
            try:
                dirs_response = ds_client.describe_directories()
                directories = dirs_response.get('DirectoryDescriptions', [])
                dir_details = []
                for d in directories:
                    dir_details.append(f"Type: {d.get('Type')}, Name: {d.get('Name')}, Status: {d.get('Stage')}, "
                        f"Size: {d.get('Size')}, Edition: {d.get('Edition', 'N/A')}, "
                        f"VPC: {d.get('VpcSettings', {}).get('VpcId')}, "
                        f"Subnets: {d.get('VpcSettings', {}).get('SubnetIds', [])}, "
                        f"DNS: {d.get('DnsIpAddrs', [])}, "
                        f"RADIUS/MFA: {d.get('RadiusSettings', {}).get('RadiusStatus', 'Not configured')}, "
                        f"SSO: {d.get('SsoEnabled', False)}")
                evidence['directories'] = f"{len(directories)} directory/directories: " + "; ".join(dir_details)
            except Exception as e:
                evidence['directories'] = f"Error: {str(e)}"

            # WorkSpaces directory settings
            try:
                ws_dirs = ws_client.describe_workspace_directories()
                dir_settings = []
                for wd in ws_dirs.get('Directories', []):
                    dir_settings.append(f"ID: {wd.get('DirectoryId')}, Type: {wd.get('DirectoryType')}, "
                        f"State: {wd.get('State')}, IP Groups: {wd.get('ipGroupIds', [])}, "
                        f"Self-service: {wd.get('SelfservicePermissions', {})}, "
                        f"Access props: {wd.get('WorkspaceAccessProperties', {})}, "
                        f"Creation props: {wd.get('WorkspaceCreationProperties', {})}")
                evidence['directorySettings'] = "; ".join(dir_settings)
            except Exception as e:
                evidence['directorySettings'] = f"Error: {str(e)}"

            # IP Access Groups
            try:
                ip_groups = ws_client.describe_ip_groups()
                groups = ip_groups.get('Result', [])
                if groups:
                    evidence['ipAccessGroups'] = f"{len(groups)} IP Access Group(s): " + "; ".join([f"{g.get('groupName', 'unnamed')} with {len(g.get('UserRules', []))} rules" for g in groups])
                else:
                    evidence['ipAccessGroups'] = "No IP Access Control Groups configured. Any network can connect."
            except Exception as e:
                evidence['ipAccessGroups'] = f"Error: {str(e)}"

            # VPC / Networking
            try:
                vpc_ids = set()
                subnet_ids = set()
                for d in directories:
                    vpc_id = d.get('VpcSettings', {}).get('VpcId')
                    if vpc_id:
                        vpc_ids.add(vpc_id)
                    subnet_ids.update(d.get('VpcSettings', {}).get('SubnetIds', []))
                if subnet_ids:
                    subnets = ec2_client.describe_subnets(SubnetIds=list(subnet_ids))
                    azs = set(s['AvailabilityZone'] for s in subnets.get('Subnets', []))
                    subnet_details = [f"{s['SubnetId']} ({s['AvailabilityZone']}, {s['AvailableIpAddressCount']} IPs free)" for s in subnets.get('Subnets', [])]
                    evidence['networking'] = f"VPCs: {list(vpc_ids)}. Subnets: {subnet_details}. AZ spread: {len(azs)} AZs ({list(azs)})."
                else:
                    evidence['networking'] = "No subnet information available."
                if vpc_ids:
                    nats = ec2_client.describe_nat_gateways(Filter=[{'Name': 'vpc-id', 'Values': list(vpc_ids)}, {'Name': 'state', 'Values': ['available']}])
                    nat_count = len(nats.get('NatGateways', []))
                    evidence['networking'] += f" NAT Gateways: {nat_count}."
                    # VPC Endpoints
                    endpoints = ec2_client.describe_vpc_endpoints(Filters=[{'Name': 'vpc-id', 'Values': list(vpc_ids)}])
                    ep_services = [e.get('ServiceName', '').split('.')[-1] for e in endpoints.get('VpcEndpoints', [])]
                    if ep_services:
                        evidence['networking'] += f" VPC Endpoints: {ep_services}."
            except Exception as e:
                evidence['networking'] = f"Error: {str(e)}"

            # Security Groups
            try:
                if vpc_ids:
                    sgs = ec2_client.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': list(vpc_ids)}])
                    sg_summary = []
                    for sg in sgs.get('SecurityGroups', [])[:10]:
                        inbound_rules = len(sg.get('IpPermissions', []))
                        open_to_all = any('0.0.0.0/0' in str(r.get('IpRanges', [])) for r in sg.get('IpPermissions', []))
                        sg_summary.append(f"{sg.get('GroupName')} ({inbound_rules} inbound rules, open-to-all: {open_to_all})")
                    evidence['securityGroups'] = f"{len(sgs.get('SecurityGroups', []))} security groups. Sample: " + "; ".join(sg_summary[:5])
            except Exception as e:
                evidence['securityGroups'] = f"Error: {str(e)}"

            # CloudWatch monitoring
            try:
                from datetime import datetime, timedelta
                alarms = cw_client.describe_alarms(MaxRecords=100)
                ws_alarms = [a for a in alarms.get('MetricAlarms', []) if 'WorkSpaces' in a.get('Namespace', '') or 'workspaces' in a.get('AlarmName', '').lower() or 'workspace' in a.get('AlarmName', '').lower()]
                all_alarm_count = len(alarms.get('MetricAlarms', []))
                evidence['monitoring'] = f"Total CloudWatch alarms: {all_alarm_count}. WorkSpaces-specific alarms: {len(ws_alarms)}."
                if ws_alarms:
                    evidence['monitoring'] += " Alarm names: " + ", ".join([a['AlarmName'] for a in ws_alarms[:5]])
                # Check for WorkSpaces metrics
                metrics = cw_client.list_metrics(Namespace='AWS/WorkSpaces')
                metric_names = set(m['MetricName'] for m in metrics.get('Metrics', []))
                evidence['monitoring'] += f" Active metrics: {list(metric_names)[:10]}."
            except Exception as e:
                evidence['monitoring'] = f"Error: {str(e)}"

            # Cost
            try:
                from datetime import datetime, timedelta
                end_date = datetime.utcnow().strftime('%Y-%m-%d')
                start_date = (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')
                cost_response = ce_client.get_cost_and_usage(
                    TimePeriod={'Start': start_date, 'End': end_date},
                    Granularity='MONTHLY', Metrics=['UnblendedCost'],
                    Filter={'Dimensions': {'Key': 'SERVICE', 'Values': ['Amazon WorkSpaces']}}
                )
                monthly_costs = []
                for r in cost_response.get('ResultsByTime', []):
                    period = r['TimePeriod']['Start']
                    amount = round(float(r.get('Total', {}).get('UnblendedCost', {}).get('Amount', 0)), 2)
                    monthly_costs.append(f"{period}: ${amount}")
                evidence['cost'] = f"WorkSpaces cost (last 90 days by month): {'; '.join(monthly_costs)}."
            except Exception as e:
                evidence['cost'] = f"Error: {str(e)}"

            # Step 3: Build the full evidence summary for Bedrock
            evidence_text = "\n".join([f"=== {k.upper()} ===\n{v}" for k, v in evidence.items()])

            # Step 4: Send to Bedrock for full analysis
            prompt = (
                "You are a senior AWS Solutions Architect conducting a Well-Architected Review of an Amazon WorkSpaces environment. "
                "Below is raw evidence gathered from an automated scan of the customer's AWS account. "
                "Based ONLY on this evidence, produce a comprehensive assessment.\n\n"
                "For each finding area you can assess, produce a JSON object with these fields:\n"
                "- 'title': Short descriptive title (e.g. 'Protocol Migration', 'Volume Encryption')\n"
                "- 'pillar': Which Well-Architected pillar (Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimisation, Sustainability)\n"
                "- 'observation': Professional summary of current state (2-4 sentences, third person)\n"
                "- 'recommendation': Actionable guidance - brief acknowledgement then 2-4 bullet points starting with bullet, then Further Reading with 1-2 AWS docs URLs\n"
                "- 'targetState': What fully implemented (green) looks like for this area (2-3 sentences)\n"
                "- 'stepsToGreen': Array of 3-5 ordered steps to reach green state\n"
                "- 'priority': 'Critical', 'High', 'Medium', or 'Low'\n"
                "- 'rag': 'red' (not implemented/critical gap), 'amber' (partial/needs work), or 'green' (good state)\n\n"
                "Also produce a 'notAssessed' array listing areas that CANNOT be determined from this scan data "
                "(e.g. patching compliance, Group Policy configuration, incident runbooks, application delivery, "
                "user experience, backup strategy, DR testing). Each item: {'area': '...', 'reason': '...'}.\n\n"
                "Also produce an 'executiveSummary' string (3-4 sentences for leadership).\n\n"
                "Format response as JSON ONLY:\n"
                "{\n"
                "  \"executiveSummary\": \"...\",\n"
                "  \"findings\": [{...}, {...}],\n"
                "  \"notAssessed\": [{\"area\": \"...\", \"reason\": \"...\"}]\n"
                "}\n\n"
                "EVIDENCE FROM AWS ACCOUNT SCAN:\n" + evidence_text[:28000]
            )

            try:
                response = bedrock.invoke_model(
                    modelId=MODEL_ID,
                    contentType='application/json',
                    accept='application/json',
                    body=json.dumps({
                        'anthropic_version': 'bedrock-2023-05-31',
                        'max_tokens': 8192,
                        'messages': [{'role': 'user', 'content': prompt}]
                    })
                )
                result = json.loads(response['body'].read())
                text = result['content'][0]['text'].strip()
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
                # Extract JSON
                brace_count = 0
                json_end = 0
                for ci, ch in enumerate(text):
                    if ch == '{': brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = ci + 1
                            break
                if json_end > 0:
                    text = text[:json_end]
                analysis = json.loads(text)
            except Exception as e:
                analysis = {'executiveSummary': f'Analysis error: {str(e)}', 'findings': [], 'notAssessed': []}

            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({
                    'analysis': analysis,
                    'evidence': evidence,
                    'summary': {
                        'workspaceCount': len(all_workspaces) if 'all_workspaces' in dir() else 0,
                        'protocols': protocols if 'protocols' in dir() else {},
                        'runningModes': running_modes if 'running_modes' in dir() else {},
                        'encryptedCount': encrypted_count if 'encrypted_count' in dir() else 0,
                        'directoryCount': len(directories) if 'directories' in dir() else 0
                    }
                })
            }

        if action == 'autoWafrAnalyse':
            # Auto WAFR Step 2: Send scan evidence to Bedrock for analysis
            evidence = body.get('evidence', {})
            summary_data = body.get('summary', {})
            evidence_text = "\n".join([f"=== {k.upper()} ===\n{v}" for k, v in evidence.items()])

            # Add summary context
            if summary_data:
                evidence_text = f"=== FLEET SUMMARY ===\nWorkSpaces: {summary_data.get('workspaceCount', 0)}, Protocols: {summary_data.get('protocols', {})}, Running modes: {summary_data.get('runningModes', {})}, Encrypted: {summary_data.get('encryptedCount', 0)}, Monthly cost: {summary_data.get('monthlyCost', 'N/A')}\n\n" + evidence_text

            prompt = (
                "You are a senior AWS Solutions Architect conducting a Well-Architected Review of an Amazon WorkSpaces environment. "
                "Below is evidence from an automated AWS account scan. Based ONLY on this evidence, produce a detailed assessment.\n\n"
                "For each finding, produce a JSON object with:\n"
                "- 'title': Short descriptive title\n"
                "- 'pillar': WAF pillar (Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimisation, Sustainability)\n"
                "- 'observation': Detailed professional summary of current state (3-5 sentences). Include specific numbers and configuration details from the evidence. Use third person.\n"
                "- 'recommendation': Start with a brief current-state acknowledgement, then 3-4 actionable bullet points where EACH bullet ends with a relevant AWS docs URL in parentheses (e.g. '... (https://docs.aws.amazon.com/workspaces/latest/adminguide/encrypt-workspaces.html)'). "
                "Every recommendation MUST contain at least 2 clickable https://docs.aws.amazon.com URLs embedded within the text.\n"
                "- 'targetState': What fully implemented looks like (2-3 sentences, concrete and measurable)\n"
                "- 'priority': Critical/High/Medium/Low\n"
                "- 'rag': red (critical gap), amber (partial), green (good)\n\n"
                "Also produce 'notAssessed' array: areas NOT determinable from scan. Each: {'area': '...', 'reason': '...', 'suggestedAction': '...'}.\n\n"
                "Produce 'executiveSummary' (3-4 sentences for leadership audience).\n\n"
                "JSON ONLY, no markdown:\n"
                "{\"executiveSummary\": \"...\", \"findings\": [{\"title\":\"\",\"pillar\":\"\",\"observation\":\"\",\"recommendation\":\"\",\"targetState\":\"\",\"priority\":\"\",\"rag\":\"\"}], "
                "\"notAssessed\": [{\"area\":\"\",\"reason\":\"\",\"suggestedAction\":\"\"}]}\n\n"
                "EVIDENCE:\n" + evidence_text[:20000]
            )

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
                brace_count = 0
                json_end = 0
                for ci, ch in enumerate(text):
                    if ch == '{': brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = ci + 1
                            break
                if json_end > 0:
                    text = text[:json_end]
                analysis = json.loads(text)
            except Exception as e:
                analysis = {'executiveSummary': f'Analysis error: {str(e)}', 'findings': [], 'notAssessed': []}

            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'},
                'body': json.dumps({'analysis': analysis})
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
