# C-Level Deck Generation Logic

## Overview

The C-Level Executive Briefing deck is generated using a two-stage AI pipeline:
1. **Tailored Recommendations** — per-question observations and recommendations (batched)
2. **AI Curation** — intelligent tiering and business-framing of findings into a boardroom-ready narrative

The result is a 13-slide fixed-structure PowerPoint with business-framed headlines, curated tiers, and visual design elements (coloured spines, RAG bars, effort badges).

## Generation Flow

```
User clicks "C-Level Deck" button
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  MODAL: Generate C-Level Deck                                │
│                                                              │
│  So What Report: [dropdown - optional grounding]             │
│  WAFR Report:    [dropdown - optional grounding]             │
│  Notification:   [email field - optional alert]              │
│                                                              │
│  [Cancel]  [Generate Deck]                                   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
STAGE 1: Fetch grounding context (optional)
    - Download selected S3 reports via Lambda getReport action
    - Strip HTML tags, truncate to 15,000 chars per report
    - Concatenate as reference context for Bedrock
    │
    ▼
STAGE 2: Generate tailored recommendations (existing flow)
    - Collect all questions with reviewer notes
    - Batch into groups of 5
    - Send each batch to Lambda `generate` action
    - Lambda calls Bedrock (Claude Haiku 4.5, 4096 tokens)
    - Returns {observation, recommendation} per question
    - Frontend merges all batch results
    │
    ▼
STAGE 3: AI Curation (new — curateDeck action)
    - Collect ALL findings: ID, pillar, question, RAG score, notes,
      observation (from Stage 2), recommendation (from Stage 2)
    - Collect pillar scores: name, percentage, RAG
    - Send to Lambda `curateDeck` action with reference context
    - Lambda sends single prompt to Bedrock (8192 tokens)
    - Returns structured JSON (see Curation Schema below)
    │
    ▼
STAGE 4: Build PowerPoint (buildCuratedCLevelPptx)
    - Consumes curated JSON structure
    - Builds 13 fixed slides using pptxgenjs
    - Saves to S3 via Lambda saveReport action
    - Sends email notification (if email provided)
    │
    ▼
FALLBACK: If Stage 3 fails
    - Uses mechanical buildCLevelPptx (old layout)
    - Maps RED→MUST, AMBER→SHOULD, GREEN→COULD
    - Shows alert explaining AI curation was unavailable
```

## Curation Prompt Logic

The `curateDeck` Lambda action sends the following prompt to Bedrock:

### Input
- Customer name
- Overall score + RAG
- Per-pillar scores (name, percentage, RAG)
- All findings (ID, pillar, question, RAG, notes, observation, recommendation)
- Reference context from saved reports (if selected)

### Curation Rules
The AI is instructed to:

1. **NOT map mechanically** — RAG is an input to tiering, not the tiering itself
2. **Select 4 Critical Findings** — board-level risks with business headlines and 2-3 sentence consequence explanations
3. **Curate MUST tier** (3-5 items) — genuine board-level risks + true quick wins that create a preventable crisis
4. **Curate SHOULD tier** (4-6 items) — highest-value items to resource this quarter
5. **Curate COULD tier** (4-6 items) — strategic, longer-term items
6. **Never present fully-implemented items as gaps**
7. **Cost savings** — only quantify where source data provides figures
8. **Assign roadmap** — Week 1-2 (urgent MUST), Week 3-6 (remaining MUST + top SHOULD), Week 7-12 (SHOULD + COULD)

### Output Schema

```json
{
  "criticalFindings": [
    {
      "id": "OPS-WS-11",
      "headline": "PCoIP to DCV Migration",
      "consequence": "Business consequence in 2-3 sentences",
      "rag": "red"
    }
  ],
  "must": [
    {
      "id": "OPS-WS-11",
      "headline": "Short business headline",
      "action": "One sentence action summary",
      "effort": "low|medium|high",
      "isQuickWin": true
    }
  ],
  "should": [
    {
      "id": "...",
      "headline": "...",
      "action": "...",
      "effort": "low|medium|high"
    }
  ],
  "could": [
    {
      "id": "...",
      "headline": "...",
      "action": "...",
      "effort": "medium|high"
    }
  ],
  "costInsights": {
    "hasData": false,
    "summary": "Overall cost assessment in 2-3 sentences",
    "items": [
      {
        "id": "COST-WS-01",
        "headline": "Short headline",
        "insight": "Insight text"
      }
    ]
  },
  "roadmap": {
    "week1_2": [{"id": "...", "headline": "..."}],
    "week3_6": [{"id": "...", "headline": "..."}],
    "week7_12": [{"id": "...", "headline": "..."}]
  },
  "executiveSummary": "3-4 sentence executive summary for board audience"
}
```

## Slide Structure (13 slides)

| # | Slide | Content Source | Visual Elements |
|---|-------|--------------|-----------------|
| 1 | Cover | Review metadata (customer, date) | Dark background, orange stripe |
| 2 | How to Read | Static content | 3 tier cards with coloured left spines (red/amber/green) |
| 3 | Executive Summary | `overallScore` + `curated.executiveSummary` | Large score, RAG colour, narrative paragraph |
| 4 | Six-Pillar Scorecard | `pillarScores[]` | Horizontal RAG bars (filled rectangles) |
| 5 | Critical Findings | `curated.criticalFindings[0-3]` | 4 cards with coloured spine + consequence text |
| 6 | Prioritisation Framework | `curated.must/should/could` (headlines) | 3 columns with coloured spines, bullet lists |
| 7 | MUST — Quick Wins | `curated.must` where `isQuickWin=true` | Red spine cards + effort badges |
| 8 | MUST — Avoidable Crises | `curated.must` where `isQuickWin=false` | Red spine cards + red background tint |
| 9 | SHOULD | `curated.should[0-5]` | Amber spine cards + effort badges |
| 10 | COULD | `curated.could[0-5]` | Green spine cards + effort badges |
| 11 | Cost Optimisation | `curated.costInsights` | Bullet items + dashed "needs more research" callout |
| 12 | 90-Day Roadmap | `curated.roadmap` | Table (Timeframe / Actions / Tier) |
| 13 | Discussion & Next Steps | Static + review metadata | 4 numbered action items + follow-up date |

## Visual Design System

### Theme Colours
| Name | Hex | Usage |
|------|-----|-------|
| Squid Ink | `232F3E` | Dark backgrounds, body text |
| Orange | `FF9900` | Accent, highlights, score text |
| Red | `D13212` | MUST tier, critical findings |
| Amber | `FF9900` | SHOULD tier |
| Green | `1D8102` | COULD tier, fully implemented |
| Grey | `5F6B7A` | Secondary text, footnotes |
| Blue | `0073BB` | Links, info callouts |

### Visual Elements
- **Coloured left spine** — 0.08-0.12 inch rectangle on left edge of cards, colour matches tier
- **RAG bars** — filled rectangle over grey background, width proportional to score
- **Effort badges** — text labels: "⚡ Low effort", "⚙️ Medium effort", "🏗️ High effort"
- **Callout box** — rounded rectangle with dashed amber border, yellow fill, italic text
- **Tier cards** — grey background rectangle with spine, headline in tier colour, body in dark text

## Fallback Behaviour

If the `curateDeck` Lambda call fails (timeout, Bedrock error, JSON parse failure):
1. Frontend logs the error to console
2. Falls back to `buildCLevelPptx` (mechanical layout)
3. Shows alert: "AI curation was unavailable — deck was generated using the standard layout"
4. The mechanical layout maps RED→MUST, AMBER→SHOULD, GREEN→COULD and uses raw question titles

## Lambda Actions Summary

| Action | Purpose | Max Tokens | Input |
|--------|---------|-----------|-------|
| `generate` | Per-question observations + recommendations | 4096 | Batch of 5 questions |
| `curateDeck` | Full-deck AI curation | 8192 | All findings + scores + context |
| `saveReport` | Save report to S3 | N/A | Content + metadata |
| `listReports` | List saved reports for a review | N/A | reviewId |
| `getReport` | Retrieve saved report from S3 | N/A | S3 key |
| `deleteReport` | Delete saved report from S3 | N/A | S3 key |
| `email` | Send report as email attachment | N/A | HTML + recipient |
| `notify` | Send simple notification email | N/A | Subject + body + recipient |
| `chat` | AI chat — answer questions grounded in review data | 1024 | Question + context + history |

## Performance

| Stage | Typical Duration | Notes |
|-------|-----------------|-------|
| Grounding fetch | 1-3s | Only if reports selected |
| Tailored recommendations | 30-90s | Depends on question count (batches of 5, sequential) |
| AI Curation | 5-15s | Single Bedrock call, 8192 tokens |
| PPTX build + S3 save | 2-5s | Client-side pptxgenjs + S3 upload |
| **Total** | **40-120s** | Dominated by tailored recommendation batching |

## Cost Per Generation

| Component | Est. Cost |
|-----------|-----------|
| Tailored recommendations (10 batches × ~2000 tokens) | ~$0.01 |
| Curation call (1 × ~5000 tokens in + ~3000 out) | ~$0.005 |
| S3 storage (1 PPTX ~300KB) | <$0.001 |
| SES notification | Free tier |
| **Total per deck** | **~$0.02** |

## Template-Aware AI Guidance (ORR Integration)

The AI pipeline is template-aware. When a review uses the `orr-default` template, all AI stages adapt their prompts to reference AWS Operational Readiness Review best practices instead of generic WorkSpaces Well-Architected guidance.

### How It Works

The frontend passes `templateId` (from the review object) to both the `generate` and `curateDeck` Lambda actions. The Lambda checks this field and switches prompt strategy accordingly.

```
Frontend (review.templateId)
    │
    ├── templateId == 'orr-default'
    │       → ORR-specific prompts + ORR_BEST_PRACTICES grounding
    │
    └── templateId == 'workspaces-default' (or any other)
            → Standard WorkSpaces Well-Architected prompts
```

### ORR Best Practices Grounding

A static `ORR_BEST_PRACTICES` constant is embedded in the Lambda (`wafr-email-report.py`). It covers seven categories drawn from the AWS ORR whitepaper:

| Category | Key Requirements |
|----------|-----------------|
| Failure Modeling & Blast Radius | Documented failure model, single points of failure, static stability, bulkhead patterns |
| Operational Processes | Runbooks, on-call rotation, incident management, change management, capacity planning |
| Event Management | Alarms tied to customer impact, actionable dashboards, canary monitoring, correlation IDs |
| Release Quality & Safe Deployment | CI/CD pipeline, progressive rollout, tested rollback, feature flags, backward-compatible migrations |
| Resilience & Recovery | RTO/RPO defined and tested, DR exercises, backup validation, circuit breakers, graceful degradation |
| Security & Compliance | Least-privilege IAM, secrets rotation, network segmentation, vulnerability scanning, audit logging |
| ORR Lifecycle | Design phase ORR, mid-cycle check-in, pre-launch completion, annual re-runs, COE feedback loop |

This reference is injected into prompts as grounding context so Bedrock can assess findings against established ORR standards.

### ORR-Specific Tailored Recommendations (`generate` action)

When `templateId == 'orr-default'`:
- System prompt frames the AI as assessing operational readiness for production
- ORR best practices are injected as grounding (in addition to any S3 report context)
- Recommendations focus on closing operational readiness gaps
- Further Reading URLs point to operational readiness documentation
- Tone uses "the team" / "the workload" rather than "the customer" / "the fleet"

### ORR-Specific Curation (`curateDeck` action)

When `templateId == 'orr-default'`:

| Aspect | WorkSpaces Default | ORR Default |
|--------|-------------------|-------------|
| Framing | "WorkSpaces Well-Architected Review" | "Operational Readiness Review" |
| Critical Findings | Board-level business risks | Items causing production incidents, outages, compliance failures |
| MUST Tier | Preventable crises + quick wins | Pre-launch blockers: missing failure models, no rollback, absent monitoring |
| SHOULD Tier | Highest-value items this quarter | Operational foundation: capacity planning, runbooks, canary deployments |
| COULD Tier | Strategic, longer-term | Operational maturity: chaos engineering, game days, automated remediation |
| Roadmap Week 1-2 | Urgent MUST | Pre-launch blockers |
| Roadmap Week 3-6 | Remaining MUST + top SHOULD | Monitoring, runbooks, incident process |
| Roadmap Week 7-12 | SHOULD + COULD | Chaos engineering, game days, automation |
| Cost Insights | Fleet/billing quantification | "Cost impacts secondary to operational readiness gaps" (unless data exists) |
| Entity Language | "the estate", "the fleet" | "the team", "the workload", "the application" |

### Data Flow with ORR Template

```
Frontend: review.templateId = 'orr-default'
    │
    ▼
STAGE 2 (generate): POST /email-report
    Body includes: { action: 'generate', questions: [...], templateId: 'orr-default' }
    Lambda injects ORR_BEST_PRACTICES into prompt + switches to ORR framing
    │
    ▼
STAGE 3 (curateDeck): POST /email-report
    Body includes: { action: 'curateDeck', ..., templateId: 'orr-default' }
    Lambda uses ORR curation prompt + injects ORR_BEST_PRACTICES as grounding
    │
    ▼
STAGE 4 (PPTX build): Same slide structure, content driven by ORR-curated JSON
```

### Adding New Templates

To add a new template-specific AI behaviour:

1. Add a system prompt entry in `wafr-explain.py` → `TEMPLATE_PROMPTS['your-template-id']`
2. Add a best practices constant in `wafr-email-report.py` (e.g., `YOUR_TEMPLATE_BEST_PRACTICES`)
3. Add an `elif template_id == 'your-template-id'` branch in `generate_tailored_recommendations()`
4. Add an `elif template_id == 'your-template-id'` branch in the `curateDeck` handler
5. The frontend automatically passes `templateId` from the review object - no frontend changes needed

### AWS ORR Documentation References

| Resource | URL |
|----------|-----|
| ORR Main Guide | https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/wa-operational-readiness-reviews.html |
| The ORR Mechanism | https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/the-orr-mechanism.html |
| The ORR Tool | https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/the-orr-tool.html |
| Gaining Adoption | https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/gaining-adoption.html |
| Example ORR Questions | https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/appendix-b-example-orr-questions.html |
| Well-Architected OPS07-BP02 | https://docs.aws.amazon.com/wellarchitected/2025-02-25/framework/ops_ready_to_support_const_orr.html |
