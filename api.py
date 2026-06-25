import os
import json
import base64
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import anthropic
import requests as http_requests

import psycopg2
import os

SUPABASE_DB_URL = os.environ.get('SUPABASE_DB_URL')

def get_db_connection():
    return psycopg2.connect(SUPABASE_DB_URL)

def create_project_record(fields):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        columns = ', '.join(f'"{k}"' for k in fields.keys())
        placeholders = ', '.join(['%s'] * len(fields))
        values = list(fields.values())
        
        query = f'INSERT INTO "MMRI Database" ({columns}) VALUES ({placeholders})'
        
        cur.execute(query, values)
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        print(f"Database write failed: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = 'appRLYp7Q2cfKgwru'
AIRTABLE_TABLE_NAME = 'Query (1) Table'

def create_airtable_record(fields):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"fields": fields}
    response = http_requests.post(url, headers=headers, json=payload)
    return response.json()

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, origins=["http://localhost:8080", "https://mpal-chatbot.onrender.com", "*"])

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

KNOWLEDGE_FILE = "knowledge_base.json"

def load_knowledge_base():
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, 'r') as f:
            return json.load(f)
    return {"docs": [], "knowledge": ""}

def save_knowledge_base(kb):
    with open(KNOWLEDGE_FILE, 'w') as f:
        json.dump(kb, f)

TEAM_DESCRIPTIONS = {
    "MSL": "The Machining Systems Laboratory (MSL) specializes in precision machining, milling, turning, grinding, EDM, water jet cutting, micro machining, CMM measurement, and material testing. Equipment includes 5-axis CNC mills, lathes, surface grinders, tool grinders, CMMs, and water jet systems. Led by Brady.",
    "CBM": "The Condition-Based Monitoring (CBM) team specializes in monitoring equipment health, predictive maintenance, vibration analysis, and performance assessment of industrial equipment. Led by Kristin.",
    "MPAL": "The Manufacturing Process Analysis Lab (MPAL) specializes in advanced manufacturing processes, machining, CNC operations, tooling, process optimization, and condition monitoring. Led by Darren.",
    "Training": "The Training team specializes in workforce development, training programs, and knowledge transfer for manufacturing processes. Led by Sean."
}

def get_system_prompt():
    kb = load_knowledge_base()
    knowledge = kb.get("knowledge", "")

    return f"""You are ETHOS, the intelligent intake assistant for the McMaster Manufacturing Research Institute (MMRI). You guide industry partners through MMRI's intake process in a warm, friendly, and non-technical way.

    GENERAL CONVERSATION HANDLING:
    If the partner sends a message that's off-topic, a greeting outside the flow (e.g. "hi" after the conversation has already started), or unrelated to the intake process, respond briefly and warmly, then gently steer back to the current step. For example: "Happy to chat! Just to keep us on track — [repeat the current question]." Never ignore the off-topic message, but always return to the intake flow afterward. 

    HANDLING INFORMATION PROVIDED EARLY:
    If a partner volunteers information before you've asked for it (e.g. they mention their budget, timeline, or problem description in their first message), acknowledge it naturally and do not ask for that same information again later. Skip directly to the next step that still needs information. For example, if they already gave their name, company, email, and problem description in one message, thank them and move straight to asking about business size.

    HANDLING REFUSAL TO ANSWER:
    If a partner declines to share a specific piece of information (e.g. "I'd rather not share that" or "I'm not comfortable saying"), respond respectfully — say something like "No problem at all, we can move forward without that for now." Continue to the next step rather than insisting or repeating the question. Note internally that the field is unknown rather than blocking the conversation.

    HANDLING REQUESTS TO SKIP AHEAD OR TALK TO A HUMAN:
    If a partner asks to skip the questions, speak to a person directly, or seems frustrated with the process, respond warmly: "Of course — I can have someone from our team reach out directly. Before I do, could I just grab your name, company, and email so they know who to contact?" If they've already provided that info, skip straight to: "Got it, someone from our team will be in touch with you directly. Thank you for reaching out to MMRI!" Do not output MATCH or FOLLOWUP tags in this case, since a full match wasn't completed.
    HANDLING UNCLEAR OR VERY SHORT RESPONSES:
    If a partner's response is unclear, very short (e.g. "ya", "idk", "sure"), or doesn't seem to answer the question asked, don't assume or guess what they meant. Gently ask for clarification: "Just to make sure I've got this right, could you tell me a bit more?" repeating the original question in simpler terms if needed. Never proceed to the next step on an ambiguous answer.

MMRI SUB-TEAMS:
MSL: {TEAM_DESCRIPTIONS['MSL']}
CBM: {TEAM_DESCRIPTIONS['CBM']}
MPAL: {TEAM_DESCRIPTIONS['MPAL']}
Training: {TEAM_DESCRIPTIONS['Training']}

INTERNAL MMRI KNOWLEDGE BASE:
{knowledge if knowledge else "No internal documents uploaded yet."}

CONVERSATION FLOW — follow these steps in order, one question at a time:

STEP 1 — GREETING
Introduce yourself warmly and explain you'll be helping them find the right MMRI team. Say: "This will work like a quick 15-minute consult — I'll ask you a few questions to understand your needs and connect you with the right team."

STEP 2 — PARTNER INFO
Ask for:
- Full name and job title
- Company name
- Contact email
- CRA business number
- Contact for accounts payable, if different from the main contact provided
- "How did you hear about us?"
Collect all of these before moving on. If they don't have their CRA number on hand, say "No problem — you can send that over later, we don't need it right now to get started" and continue without blocking the conversation.

STEP 3 — DESCRIPTION OF REQUEST
Ask: "In one sentence, what is the main challenge or project you're looking for help with?"
If the response is too vague to confidently identify a likely sub-team (e.g. "we need help with manufacturing" or "general improvements"), ask one clarifying follow-up before moving on, such as: "Could you tell me a bit more — is this more about a specific piece of equipment, a manufacturing process, the materials you're using, or something else?"
Internally use this to identify the likely sub-team match — do not reveal the team name yet.

STEP 4 — BUSINESS SIZE
Ask: "How many employees does your company have?"

STEP 5 — TIMELINE (CLIENT ONLY)
Ask: "Do you have a timeline in mind for when you'd like this completed?"
Note: this is confidential and only used internally.

STEP 6 — BUDGET (CLIENT ONLY)
Ask: "What budget range are you working with for this project? For example, under $5,000, $5,000–$15,000, $15,000–$50,000, or over $50,000."
Note: this is confidential and only used internally.

STEP 7 — PROCEED DECISION
Evaluate whether this project is a good fit for MMRI based on the information collected so far. Consider:
- Does the budget seem reasonable for the scope of work described? A very small budget for a large, complex project is a red flag.
- Is the timeline realistic given the complexity of the request? A very tight timeline for a complex project is a red flag.
- Does the request fall within MMRI's manufacturing-related expertise (materials, equipment monitoring, manufacturing processes, training)?
- Is the company size appropriate for MMRI's typical partners? MMRI primarily works with small and medium enterprises, though larger companies aren't automatically excluded — use judgment based on whether the scope of the request fits a collaborative research engagement.

There is no fixed minimum budget — use judgment based on what's reasonable for the type of work described.

- If the project seems like a reasonable fit → say "Great, based on what you've shared, it sounds like MMRI can help! Let me find the right team for you." Then move to Step 8.
- If the budget or timeline seems significantly misaligned with the scope, or the request is clearly outside MMRI's manufacturing-related expertise → say warmly: "Thanks so much for sharing all of this — I can tell there's a real need here. Before we go further, I want to make sure we set the right expectations together." Then ask: "Could you tell us a bit more about your budget and timeline expectations for this project?" Give them a genuine chance to clarify or adjust before deciding whether to proceed. If after clarifying it's still not a good fit, say warmly: "I really appreciate you walking through this with me. Based on what we've discussed, this particular project might be a better fit outside MMRI right now — but please don't hesitate to reach out again as things evolve, or if you have other manufacturing challenges down the line. We'd genuinely love to help when the timing is right." Do not output MATCH or FOLLOWUP tags in this case.

STEP 8 — PROJECT TYPE
Ask: "Is this project fee-for-service, or are you looking to apply for external funding (e.g. NSERC, CAMEDA, ORF, MITACS)?"
- If funded → ask: "Which funding mechanism are you applying through, or would you like a quick overview of the options?"
  - If they want an overview, briefly explain in plain language:
    - "NSERC — federal research funding for projects with an academic research and innovation component"
    - "ORF (Ontario Research Fund) — supports research infrastructure and equipment costs"
    - "MITACS — funds graduate student or postdoc research placements working on your project"
    - "CAMEDA — specifically for medical device companies needing manufacturing support"
    - "CAMINA — for advanced manufacturing projects related to the nuclear industry"
  - Help them identify which mechanism best fits based on their project description and industry.

STEP 9 — PROJECT DESCRIPTION
Ask: "Can you give me a more detailed description of the project? What are the goals and expected outcomes?"

STEP 10 — QUOTE
Inform the partner: "Based on your project details, MMRI will prepare a quote for you. Our team will follow up with a detailed breakdown."

STEP 11 — PROPOSAL / SCOPE OF WORK
If the partner provided a timeline in Step 5 → say: "Since you have a timeline in mind, MMRI will also prepare a Proposal and Scope of Work document for your review."
If no timeline → skip this step.

STEP 12 — CONFIRMATION SUMMARY
Before asking for approval, summarize everything collected so far in a clear, friendly recap. For example:
"Just to confirm everything — here's what I've got:
- Name: [name], [company]
- Contact: [email]
- Project: [one-line description]
- Type: [FFS or Funded]
- Timeline: [timeline or 'not specified']
- Budget: [budget or 'not specified']

Does this all look correct?"
If they want to correct anything, update it and re-confirm before moving on.

STEP 13 — CLIENT APPROVAL
Once confirmed, ask: "Great — are you ready to move forward?"
- If YES:
  - Determine the booking link based on the matched team:
    - If matched team is MSL → use link: https://calendly.com/PLACEHOLDER-MSL
    - If matched team is CBM → use link: https://calendly.com/PLACEHOLDER-CBM
    - If matched team is MPAL → use link: https://calendly.com/PLACEHOLDER-MPAL
  - If project type is "Funded" → say: "Wonderful! Since this is a funded project, the next step is putting together a funding proposal. Let's get a meeting scheduled with our team to start that process. You can pick a time that works for you here: [insert the correct link based on matched team]" Then say: "Once you've booked a time, our team will be ready to walk through the funding proposal process with you. You'll also receive a copy of this summary by email from our team shortly." Then output the MATCH and FOLLOWUP tags below.
  - If project type is "Fee-for-Service" → say: "Wonderful! Let's get a meeting scheduled with our team to kick off the project. You can pick a time that works for you here: [insert the correct link based on matched team]" Then say: "Once you've booked a time, our team will be ready to get started. You'll also receive a copy of this summary by email from our team shortly." Then output the MATCH and FOLLOWUP tags below.
- If NO → say: "No problem at all. Thank you for your time and we hope to work with you in the future." Do not output MATCH or FOLLOWUP tags in this case.

LANGUAGE RULES:
- Never say: CBM, MSL, MPAL, OEE, FMEA, KPI, predictive maintenance, condition monitoring
- Always say: "our equipment health team", "our materials team", "our manufacturing process team", "our training team"
- Use analogies: "think of it like a check engine light for your machines"
- Keep responses short — 2-4 sentences max per message
- Ask only ONE question at a time
- Be warm, friendly, and non-technical at all times

TEAM ROUTING GUIDE:
- Material testing, characterization, property assessment → MSL
- Product development, refinement → MSL
- Prototyping → MSL or MPAL
- Process development, CNC, machining, manufacturing improvement → MPAL
- Equipment breaking down, performance monitoring, predictive health → CBM
- Workforce training, knowledge transfer → Training

At the end when you have enough info, include:
MATCH: [team name] | CONFIDENCE: [percentage]%
If multiple teams are relevant:
MATCH: [team name] | CONFIDENCE: [percentage]%
MATCH: [team name] | CONFIDENCE: [percentage]%

Before the MATCH tags, briefly explain in plain language why each team is a good fit — for example: "This sounds like it touches both our equipment health side and our manufacturing process side, since the issue involves both the machine itself and how the process is run."

After the match include 1-2 follow-up questions:
FOLLOWUP: [question]

ABOUT MMRI:
- Located at 230 Longwood Road South, Hamilton, Ontario
- Phone: 905-525-9140, Email: mmri-ad@mcmaster.ca
- Hours: Monday-Friday 8:30am-4:30pm"""

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    messages = data.get('messages', [])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=get_system_prompt(),
        messages=messages
    )

    reply = response.content[0].text

    conversations = []
    if os.path.exists('conversations.json'):
        with open('conversations.json', 'r') as f:
            conversations = json.load(f)

    conversations.append({
        "id": str(len(conversations) + 1),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "messages": messages + [{"role": "assistant", "content": reply}]
    })

    with open('conversations.json', 'w') as f:
        json.dump(conversations, f)

    return jsonify({'response': reply})

@app.route ('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    pdf_data = base64.standard_b64encode(file.read()).decode('utf-8')

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=get_system_prompt(),
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_data
                    }
                },
                {
                    "type": "text",
                    "text": "Please analyze this document and match it to the right MMRI team."
                }
            ]
        }]
    )

    return jsonify({'response': response.content[0].text})


@app.route('/api/train', methods=['POST'])
def train():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    file_content = file.read()
    pdf_data = base64.standard_b64encode(file_content).decode('utf-8')

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_data
                    }
                },
                {
                    "type": "text",
                    "text": "Extract the key information from this MMRI document. Summarize what services, capabilities, success stories, or knowledge it contains that would help match industry partners to the right MMRI team. Be concise and factual."
                }
            ]
        }]
    )

    extracted = response.content[0].text

    kb = load_knowledge_base()
    doc_id = str(len(kb["docs"]) + 1)
    kb["docs"].append({
        "id": doc_id,
        "name": file.filename,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "extracted": extracted
    })

    kb["knowledge"] = "\n\n".join([f"From {d['name']}:\n{d['extracted']}" for d in kb["docs"]])
    save_knowledge_base(kb)

    return jsonify({'success': True, 'extracted': extracted})

@app.route('/api/docs', methods=['GET'])
def get_docs():
    kb = load_knowledge_base()
    return jsonify({'docs': kb["docs"]})

@app.route('/api/docs/<doc_id>', methods=['DELETE'])
def delete_doc(doc_id):
    kb = load_knowledge_base()
    kb["docs"] = [d for d in kb["docs"] if d["id"] != doc_id]
    kb["knowledge"] = "\n\n".join([f"From {d['name']}:\n{d['extracted']}" for d in kb["docs"]])
    save_knowledge_base(kb)
    return jsonify({'success': True})

@app.route('/api/knowledge', methods=['GET'])
def get_knowledge():
    kb = load_knowledge_base()
    return jsonify({'knowledge': kb.get("knowledge", "")})

@app.route('/api/scoping', methods=['POST'])
def generate_scoping():
    data = request.json
    matched_team = data.get('matched_team', '')
    confidence = data.get('confidence', '')
    conversation_summary = data.get('conversation_summary', '')

    extract_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"From this conversation extract: partner name, company name, email, phone, company overview, problem description, project type, company size, and timeline. Return ONLY a JSON object with no markdown, no backticks, just raw JSON like this: {{\"name\": \"...\", \"company\": \"...\", \"email\": \"...\", \"phone\": \"...\", \"overview\": \"...\", \"problem\": \"...\", \"project_type\": \"...\", \"company_size\": \"...\", \"timeline\": \"...\"}}\n\nConversation:\n{conversation_summary}"
        }]
    )

    try:
        raw = extract_response.content[0].text.strip()
        extracted = json.loads(raw)
        partner_name = extracted.get('name', 'Unknown')
        company = extracted.get('company', 'Unknown')
        email = extracted.get('email', 'Not provided')
        phone = extracted.get('phone', 'Not provided')
        overview = extracted.get('overview', '')
        problem = extracted.get('problem', '')
        project_type = extracted.get('project_type', 'Not specified')
        company_size = extracted.get('company_size', 'Not specified')
        timeline = extracted.get('timeline', 'Not specified')
    except:
        partner_name = 'Unknown'
        company = 'Unknown'
        email = 'Not provided'
        phone = 'Not provided'
        overview = ''
        problem = ''
        project_type = 'Not specified'
        company_size = 'Not specified'
        timeline = 'Not specified'

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
    import io

    maroon = HexColor('#7A003C')
    maroon_dark = HexColor('#5c002d')
    gold = HexColor('#D4A24C')
    gold_bright = HexColor('#FDBF57')
    ink = HexColor('#2B2420')
    ink_soft = HexColor('#6B6258')
    line_col = HexColor('#E3DACB')

    team_full_name = TEAM_DESCRIPTIONS.get(matched_team, matched_team).split('.')[0] if matched_team in TEAM_DESCRIPTIONS else matched_team
    project_code = f"PENDING-{datetime.now().strftime('%Y%m%d%H%M')}"
    today_str = datetime.now().strftime('%d %B %Y')

    buffer = io.BytesIO()
    is_funded = project_type and 'fund' in project_type.lower()

    styles = getSampleStyleSheet()

    if not is_funded:
        # ───────────────────────── SIMPLE FFS VERSION ─────────────────────────
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            rightMargin=0.85*inch, leftMargin=0.85*inch,
            topMargin=0.7*inch, bottomMargin=0.75*inch
        )

        eyebrow_style = ParagraphStyle('Eyebrow', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=9, textColor=gold, spaceAfter=2)
        title_style = ParagraphStyle('Title', parent=styles['Title'], fontName='Helvetica-Bold',
            textColor=maroon_dark, fontSize=22, spaceAfter=4, leading=26)
        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontName='Helvetica',
            textColor=ink_soft, fontSize=10, spaceAfter=2)
        section_label_style = ParagraphStyle('SectionLabel', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=10, textColor=maroon, spaceBefore=16, spaceAfter=6)
        field_label_style = ParagraphStyle('FieldLabel', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=8.5, textColor=ink_soft, spaceAfter=1)
        field_value_style = ParagraphStyle('FieldValue', parent=styles['Normal'], fontName='Helvetica',
            fontSize=10.5, textColor=ink, spaceAfter=9, leading=14)
        body_style = ParagraphStyle('Body', parent=styles['Normal'], fontName='Helvetica',
            fontSize=10.5, textColor=ink, spaceAfter=8, leading=15)
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontName='Helvetica',
            fontSize=8, textColor=ink_soft)
        numbered_style = ParagraphStyle('Numbered', parent=styles['Normal'], fontName='Helvetica',
            fontSize=10, textColor=ink, spaceAfter=5, leading=14, leftIndent=4)

        def field_block(label, value):
            return [Paragraph(label.upper(), field_label_style), Paragraph(str(value), field_value_style)]

        story = []
        story.append(Paragraph("MCMASTER MANUFACTURING RESEARCH INSTITUTE", eyebrow_style))
        story.append(Paragraph("Quick-Start Project Summary", title_style))
        story.append(Paragraph(f"Fee-for-Service Engagement &nbsp;&middot;&nbsp; {today_str} &nbsp;&middot;&nbsp; Generated by ETHOS", subtitle_style))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=2, color=maroon))
        story.append(Spacer(1, 14))

        left_col = field_block("Contact", f"{partner_name} &middot; {company}")
        right_col = field_block("Email / Phone", f"{email} &middot; {phone}")
        info_table = Table([[left_col, right_col]], colWidths=[3.1*inch, 3.1*inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(info_table)

        left_col2 = field_block("Company Size", company_size)
        right_col2 = field_block("Target Timeline", timeline)
        info_table2 = Table([[left_col2, right_col2]], colWidths=[3.1*inch, 3.1*inch])
        info_table2.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(info_table2)

        story.append(Paragraph("WHAT THEY NEED", section_label_style))
        story.append(Paragraph(problem, body_style))

        story.append(Spacer(1, 4))
        team_card_inner = Table(
            [[Paragraph("RECOMMENDED MMRI TEAM", ParagraphStyle('w', parent=field_label_style, textColor=HexColor('#FFFFFF'), fontSize=8.5)),
              Paragraph(f"{confidence}% match confidence", ParagraphStyle('c', parent=field_label_style, textColor=gold_bright, fontSize=8.5))],
             [Paragraph(matched_team, ParagraphStyle('tn', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, textColor=gold_bright)), '']],
            colWidths=[4.2*inch, 2*inch]
        )
        team_card_inner.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), maroon_dark),
            ('LEFTPADDING', (0,0), (-1,-1), 16),
            ('TOPPADDING', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,1), (-1,1), 12),
            ('TOPPADDING', (0,1), (-1,1), 2),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(team_card_inner)
        story.append(Spacer(1, 12))

        story.append(Paragraph("NEXT STEPS", section_label_style))
        steps = [
            "MMRI team reaches out to confirm scope and quote",
            "Quick kickoff and work begins",
        ]
        for i, step in enumerate(steps, 1):
            row = Table(
                [[Paragraph(str(i), ParagraphStyle(f'num{i}', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=HexColor('#FFFFFF'), alignment=TA_CENTER)),
                  Paragraph(step, numbered_style)]],
                colWidths=[0.3*inch, 5.9*inch]
            )
            row.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,0), maroon),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (0,0), 0),
                ('TOPPADDING', (0,0), (0,0), 4),
                ('BOTTOMPADDING', (0,0), (0,0), 4),
                ('LEFTPADDING', (1,0), (1,0), 10),
            ]))
            story.append(row)
            story.append(Spacer(1, 4))

        story.append(Spacer(1, 14))
        story.append(HRFlowable(width="100%", thickness=0.75, color=line_col))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "McMaster Manufacturing Research Institute &nbsp;&middot;&nbsp; 230 Longwood Road South, Hamilton, ON &nbsp;&middot;&nbsp; mmri-ad@mcmaster.ca &nbsp;&middot;&nbsp; 905-525-9140",
            footer_style
        ))

        doc.build(story)

    else:
        # ───────────────────────── ELABORATE FUNDED VERSION ─────────────────────────
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            rightMargin=0.85*inch, leftMargin=0.85*inch,
            topMargin=0.65*inch, bottomMargin=0.7*inch
        )

        table_header_bg = maroon
        table_alt_bg = HexColor('#F4F0EE')
        ink2 = HexColor('#231F20')

        doc_title_style = ParagraphStyle('DocTitle', parent=styles['Title'], fontName='Helvetica-Bold',
            fontSize=15, textColor=ink2, alignment=TA_CENTER, spaceAfter=14)
        section_header_style = ParagraphStyle('SectionHeader', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=11.5, textColor=HexColor('#FFFFFF'), spaceBefore=0, spaceAfter=0, alignment=TA_CENTER)
        subsection_style = ParagraphStyle('Subsection', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=10.5, textColor=ink2, spaceBefore=14, spaceAfter=6)
        body_style2 = ParagraphStyle('Body2', parent=styles['Normal'], fontName='Helvetica',
            fontSize=10, textColor=ink2, spaceAfter=8, leading=15)
        placeholder_style = ParagraphStyle('Placeholder', parent=styles['Normal'], fontName='Helvetica-Oblique',
            fontSize=10, textColor=ink_soft, spaceAfter=8, leading=14, leftIndent=14)
        header_field_label = ParagraphStyle('HFL', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=ink2)
        header_field_value = ParagraphStyle('HFV', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=ink2)
        footer_style2 = ParagraphStyle('Footer2', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=ink_soft)

        def section_band(text):
            t = Table([[Paragraph(text, section_header_style)]], colWidths=[6.3*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), table_header_bg),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            return t

        story = []

        header_data = [
            [Paragraph("Date:", header_field_label), Paragraph(today_str, header_field_value)],
            [Paragraph("Company Name:", header_field_label), Paragraph(company, header_field_value)],
            [Paragraph("Report Title:", header_field_label), Paragraph(f"{company} Intake Summary", header_field_value)],
            [Paragraph("Project Code:", header_field_label), Paragraph(project_code + " (pending assignment)", header_field_value)],
        ]
        header_table = Table(header_data, colWidths=[1.5*inch, 4.8*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
        ]))

        story.append(Paragraph("Project Intake Summary", doc_title_style))
        story.append(header_table)
        story.append(Spacer(1, 10))

        rev_data = [
            [Paragraph("Revision", ParagraphStyle('rh', parent=header_field_label, alignment=TA_CENTER)),
             Paragraph("Description", ParagraphStyle('rh2', parent=header_field_label, alignment=TA_CENTER)),
             Paragraph("Author", ParagraphStyle('rh3', parent=header_field_label, alignment=TA_CENTER)),
             Paragraph("Revision Date", ParagraphStyle('rh4', parent=header_field_label, alignment=TA_CENTER))],
            [Paragraph("V1", body_style2), Paragraph("Generated from ETHOS intake conversation.", body_style2),
             Paragraph("ETHOS", body_style2), Paragraph(today_str, body_style2)],
        ]
        rev_table = Table(rev_data, colWidths=[0.85*inch, 3.15*inch, 1*inch, 1.3*inch])
        rev_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, HexColor('#999999')),
            ('BACKGROUND', (0,0), (-1,0), table_alt_bg),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(rev_table)
        story.append(Spacer(1, 12))

        story.append(section_band("Summary of Report"))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"This document summarizes the intake conversation between <b>{partner_name}</b> of <b>{company}</b> "
            f"and ETHOS, the MMRI partner intake assistant. Based on the information gathered, the project has been "
            f"matched to the <b>{team_full_name}</b> with {confidence}% confidence. This document is intended to "
            f"support the MMRI team lead in preparing a full Scope of Work and should not be treated as a "
            f"final project agreement.", body_style2
        ))
        story.append(Spacer(1, 8))

        story.append(section_band("1. Background"))
        story.append(Spacer(1, 6))
        story.append(Paragraph("1.1 &nbsp;Partner Information", subsection_style))

        info_data = [
            [Paragraph("Contact Name", header_field_label), Paragraph(partner_name, body_style2),
             Paragraph("Email", header_field_label), Paragraph(email, body_style2)],
            [Paragraph("Company", header_field_label), Paragraph(company, body_style2),
             Paragraph("Phone", header_field_label), Paragraph(phone, body_style2)],
            [Paragraph("Company Size", header_field_label), Paragraph(company_size, body_style2),
             Paragraph("Project Type", header_field_label), Paragraph(project_type, body_style2)],
        ]
        info_table = Table(info_data, colWidths=[1.2*inch, 1.95*inch, 1.0*inch, 2.15*inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(info_table)

        story.append(Paragraph("1.2 &nbsp;Company Overview", subsection_style))
        story.append(Paragraph(overview if overview else "<i>Not provided during intake.</i>", body_style2))

        story.append(Paragraph("1.3 &nbsp;Purpose", subsection_style))
        story.append(Paragraph(
            f"The purpose of this engagement is to support {company} in addressing the following challenge, "
            f"as described during intake:", body_style2
        ))
        story.append(Paragraph(problem, body_style2))

        story.append(Paragraph("1.4 &nbsp;Timeline &amp; Budget Considerations", subsection_style))
        story.append(Paragraph(f"<b>Indicated timeline:</b> {timeline if timeline else 'Not specified'}", body_style2))
        story.append(Paragraph("<i>Note: budget information was collected during intake but is withheld from this document for confidentiality. It is available internally to the MMRI team lead.</i>", placeholder_style))

        story.append(section_band("2. Recommended MMRI Team"))
        story.append(Spacer(1, 6))
        team_data = [[
            Paragraph(team_full_name, ParagraphStyle('tn2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, textColor=maroon)),
            Paragraph(f"{confidence}% match confidence", ParagraphStyle('tc2', parent=body_style2, alignment=TA_LEFT))
        ]]
        team_table = Table(team_data, colWidths=[4*inch, 2.3*inch])
        team_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), table_alt_bg),
            ('BOX', (0,0), (-1,-1), 0.75, maroon),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(team_table)

        story.append(section_band("3. Project Requirements"))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "In this document, the term <b>SHALL</b> indicates a requirement that must be satisfied. The term "
            "<b>SHOULD</b> indicates a recommendation that is advised but not required. The specific technical "
            "requirements for this engagement have not yet been defined and will be developed collaboratively "
            "by the assigned MMRI team lead in consultation with the partner.", body_style2
        ))
        story.append(Paragraph("3.1 &nbsp;Scope of MMRI Involvement", subsection_style))
        story.append(Paragraph("<i>To be defined by MMRI team lead following kickoff meeting.</i>", placeholder_style))
        story.append(Paragraph("3.2 &nbsp;Items Outside of Project Scope", subsection_style))
        story.append(Paragraph("<i>To be defined by MMRI team lead following kickoff meeting.</i>", placeholder_style))

        story.append(section_band("4. Next Steps"))
        story.append(Spacer(1, 6))

        steps_data = [
            ["No.", "Activity", "Description", "Status"],
            ["1", "Intake conversation", "Partner needs and project details gathered via ETHOS.", "Complete"],
            ["2", "Team match", f"Project matched to {matched_team}.", "Complete"],
            ["3", "Kickoff meeting", "MMRI team to schedule and confirm meeting time with partner.", "Pending"],
            ["4", "Funding proposal", "MMRI team lead develops funding proposal documentation.", "Pending"],
            ["5", "Client approval", "Partner reviews and approves proposal.", "Pending"],
            ["6", "Project code assignment", "Sean to assign official MMRI project code.", "Pending"],
        ]
        steps_table_data = []
        for idx, row in enumerate(steps_data):
            if idx == 0:
                steps_table_data.append([
                    Paragraph(row[0], ParagraphStyle('sh0', parent=header_field_label, alignment=TA_CENTER)),
                    Paragraph(row[1], header_field_label),
                    Paragraph(row[2], header_field_label),
                    Paragraph(row[3], ParagraphStyle('sh3', parent=header_field_label, alignment=TA_CENTER)),
                ])
            else:
                status_color = HexColor('#2E7D32') if row[3]=="Complete" else HexColor('#B8860B')
                steps_table_data.append([
                    Paragraph(row[0], ParagraphStyle(f'sc_{idx}', parent=body_style2, alignment=TA_CENTER)),
                    Paragraph(row[1], body_style2),
                    Paragraph(row[2], body_style2),
                    Paragraph(row[3], ParagraphStyle(f'sc2_{idx}', parent=body_style2, alignment=TA_CENTER,
                        textColor=status_color))
                ])

        steps_table = Table(steps_table_data, colWidths=[0.4*inch, 1.5*inch, 3.1*inch, 0.9*inch])
        steps_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, HexColor('#999999')),
            ('BACKGROUND', (0,0), (-1,0), table_alt_bg),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(steps_table)

        story.append(Spacer(1, 16))
        story.append(HRFlowable(width="100%", thickness=1, color=maroon))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "McMaster Manufacturing Research Institute &nbsp;&middot;&nbsp; 230 Longwood Road South, Hamilton, ON L8P 0A6 "
            "&nbsp;&middot;&nbsp; mmri-ad@mcmaster.ca &nbsp;&middot;&nbsp; 905-525-9140 &nbsp;&middot;&nbsp; Generated by ETHOS",
            footer_style2
        ))

        doc.build(story)

    buffer.seek(0)

    from flask import send_file
    doc_label = "FundingIntake" if is_funded else "QuickSummary"
    return send_file(buffer, mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f'MMRI_{doc_label}_{company}_{datetime.now().strftime("%Y%m%d")}.pdf')


@app.route('/api/create-project', methods=['POST'])
def create_project():
    data = request.json
    conversation_summary = data.get('conversation_summary', '')
    matched_team = data.get('matched_team', '')

    extract_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"From this conversation extract: partner name, company name, email, phone, project description, project type, company size, address if mentioned. Return ONLY raw JSON: {{\"name\": \"...\", \"company\": \"...\", \"email\": \"...\", \"phone\": \"...\", \"description\": \"...\", \"project_type\": \"...\", \"company_size\": \"...\", \"address\": \"...\"}}\n\nConversation:\n{conversation_summary}"
        }]
    )

    try:
        raw = extract_response.content[0].text.strip()
        raw = raw.replace('```json', '').replace('```', '').strip()
        extracted = json.loads(raw)
    except Exception as e:
        print(f"Extraction parsing failed: {e}")
        extracted = {}

    project_code = f"PENDING-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    fields = {
    "Title": f"{extracted.get('company', 'Unknown')} - {matched_team}",
    "Project Code": project_code,
    "Partner": extracted.get('company', 'Unknown'),
    "Project Description": extracted.get('description', ''),
    "Start Date": datetime.now().strftime('%Y-%m-%d'),
    "Program Type": extracted.get('project_type', ''),
    "Sub-Group": matched_team,
    "Project Status": "Pending Agreement",
    "Partner Contact Name": extracted.get('name', ''),
    "Partner Contact Email": extracted.get('email', ''),
    "Partner Address": extracted.get('address', ''),
    "Company Size": extracted.get('company_size', ''),
}

    db_success = create_project_record(fields)
    return jsonify({"success": db_success, "project_code": project_code})


@app.route('/api/bob', methods=['POST'])
def bob():
    data = request.json
    messages = data.get('messages', [])

    kb = load_knowledge_base()
    knowledge = kb.get("knowledge", "")

    conversations = []
    if os.path.exists('conversations.json'):
        with open('conversations.json', 'r') as f:
            conversations = json.load(f)

    conversations_text = "\n\n".join([
        f"Conversation {c['id']} ({c['date']}):\n" +
        "\n".join([f"{m['role'].upper()}: {m['content']}" for m in c['messages']])
        for c in conversations[-20:]
    ])

    bob_system = f"""You are BOB, an internal assistant for the McMaster Manufacturing Research Institute (MMRI) staff. You help MMRI team members quickly find information about partners, past projects, internal processes, and internal knowledge.

You have access to:
1. Recent ETHOS partner conversations
2. Internal MMRI documents uploaded by managers
3. MMRI's internal project workflows (below)

RECENT ETHOS CONVERSATIONS:
{conversations_text if conversations_text else "No conversations yet."}

INTERNAL MMRI KNOWLEDGE BASE:
{knowledge if knowledge else "No documents uploaded yet."}

MMRI SUB-TEAMS:
- MSL (Machining Systems Laboratory) — Brady
- CBM (Condition-Based Monitoring) — Kristin
- MPAL (Manufacturing Process Analysis Lab) — Darren
- Training — Sean

KRISTIN'S PROJECT WORKFLOW (Initiation → Planning → Execution → Closure):
1. INITIATION: Create project folder (OCI or ORF Team) + Request project code (Sean) + Project kickoff w/ client → Develop proposal (DRF) or SOW (OCI) + quote (using Proposal/SOW template, quoting tool, project codes sheet) → Client approval (if no, revise proposal; if yes, proceed)
2. PLANNING: Request Infinity X form (MMRI Admin) + Create SOW (ORF) + Complete MMRI promotion form (if applicable) → Assign MS Planner buckets and tasks
3. EXECUTION: Execute project as per SOW → Client receives deliverables
4. CLOSURE: Transfer OCI files to MMRI archive and delete channel + Update and close MS Planner tasks + Update IX form to next stage + Update project status in project codes list → Project closed

DARREN'S PROJECT WORKFLOW (RFQ → Quote → Execution → Billing):
1. Incoming request via Diss/Chat/Email → RFQ → Tech/Design → Milestone/OBS. RFQ also connects to Funding, OCI, and Steve.
2. Quote → Excel SPLIT (outputs: FAB with LES/Kevin, Machine time, Report/Analysis, Sub-contract — these can iterate) and Quote tool
3. Submit Q to customer (iterates with Q Accept until agreed) → Scope doc finalized
4. Q Accept → Code request (outputs: KS, Hour allocation, PMP doc) and P.O
5. Mail received → Kick-off → Assign tasks / Update timeline (outputs: Teams, PMP doc, email)
6. Work → Clockify + Infinity X Form/Rock (outputs feed into MPAL-PMP Drive) → Submit report
7. Billing (outputs: Infinity X, Ellen/Sam) → Budget vs Actual → Rate review
8. Outcomes/Success → Follow-up

When staff ask about "what happens after X" or "what's the next step in the process," reference these workflows directly. Be concise and helpful. When answering about a specific partner or project, cite which conversation or document you found the info in."""
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=bob_system,
        messages=messages
    )

    return jsonify({'response': response.content[0].text})

@app.route('/api/report', methods=['POST'])
def generate_report():
    data = request.json
    conversation_summary = data.get('conversation_summary', '')
    bob_response = data.get('bob_response', '')

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.units import inch
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)

    styles = getSampleStyleSheet()
    blue = HexColor('#2a2a7a')

    title_style = ParagraphStyle('Title', parent=styles['Title'],
                                  textColor=blue, fontSize=24, spaceAfter=6)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
                                     textColor=HexColor('#666666'), fontSize=11, spaceAfter=20)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'],
                                    textColor=blue, fontSize=13, spaceBefore=16, spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                 fontSize=11, spaceAfter=8, leading=16)

    story = []

    story.append(Paragraph("MMRI Internal Project Report", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=blue))
    story.append(Spacer(1, 16))

    story.append(Paragraph("BOB Summary", heading_style))
    clean_bob = bob_response.encode('ascii', 'replace').decode('ascii')
    story.append(Paragraph(clean_bob.replace('\n', '<br/>'), body_style))

    story.append(Paragraph("Full Conversation Log", heading_style))
    clean_summary = conversation_summary.encode('ascii', 'replace').decode('ascii')
    story.append(Paragraph(clean_summary.replace('\n', '<br/>'), body_style))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#cccccc')))
    story.append(Spacer(1, 8))
    story.append(Paragraph("McMaster Manufacturing Research Institute · Internal Use Only · mmri-ad@mcmaster.ca",
                            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=HexColor('#999999'))))

    doc.build(story)
    buffer.seek(0)

    from flask import send_file
    return send_file(buffer, mimetype='application/pdf',
                     as_attachment=True,
                     download_name=f'MMRI_Report_{datetime.now().strftime("%Y%m%d")}.pdf')

@app.route('/training')
def serve_training():
    return send_from_directory('.', 'training.html')

@app.route('/widget.html')
def serve_widget():
    return send_from_directory('.', 'widget.html')

@app.route('/bob')
def serve_bob():
    return send_from_directory('.', 'bob.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)