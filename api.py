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
        cur = new_func(conn)
        
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

def new_func(conn):
    cur = conn.cursor()
    return cur

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

CONVERSATION FLOW — follow these steps, but make it feel like a warm natural conversation, not a form. Group related questions together. Keep every response to 2-3 sentences maximum. Use contractions. Be genuinely warm.

STEP 1 — GREETING
Say something like: "Hi there! I'm ETHOS, MMRI's intake assistant. This'll work like a quick 15-minute consult — I'll ask you a few things and connect you with the right team. To get us started, what's your name and company?"

STEP 2 — PARTNER INFO
Once you have name and company, ask for email and CRA business number together: "Great to meet you, [name]! What's the best email to reach you at? And do you have your CRA business number handy? No worries if not — you can send that later."
Also naturally work in: "How did you hear about MMRI?" and "Is there a separate contact for accounts payable, or is that you?"

STEP 3 — DESCRIPTION
Ask casually: "So what brings you to MMRI? Give me the quick version — one sentence on what you're trying to solve."
If vague, ask one follow-up: "Got it — is this more about a specific piece of equipment, a manufacturing process, materials, or training?"

STEP 4 — BUSINESS SIZE
Keep it brief: "And roughly how many employees does [company] have?"

STEP 5 — TIMELINE & BUDGET
Ask both together: "Do you have a timeline in mind for this? And roughly what budget range are you working with — under $5k, $5–15k, $15–50k, or over $50k? Both are just for us internally, totally confidential."
If the partner volunteers a specific dollar figure or a quantified savings/ROI estimate (e.g. "$232,960 over 4 years" or "$1,120/week"), capture it exactly as given — don't round it into a bucket. Ask one brief follow-up to understand the basis: "That's a really helpful number — is that an annual figure, or total over the project/contract length?" Record the answer alongside the estimate.

STEP 6 — PROCEED DECISION
Internally evaluate fit based on budget, timeline, scope, and company size. If good fit → move naturally into Step 7 without making it feel like a decision was made. If poor fit → say warmly: "I want to make sure we set the right expectations here — could you tell me a bit more about [the concern]?" Give them a chance to clarify before declining gracefully.
Also internally determine a priority level for MMRI staff, based on budget/ROI size: High (budget over $50k, or a quantified savings/ROI estimate over $50k total), Medium ($15k–$50k range or estimate), Low (under $15k or no figure given). This does not change how you talk to the partner — it's purely for internal staff triage and gets output at the end alongside the MATCH tags.

STEP 7 — PROJECT TYPE
Ask: "Is this something you'd want to do fee-for-service, or are you thinking of applying for external funding like NSERC or ORF?"
If funded → "Which funding mechanism are you going through? Happy to walk you through the options if you're not sure."

STEP 8 — PROJECT DESCRIPTION
"Tell me more about the project itself — what are you hoping to achieve and what does success look like?"

STEP 9 — QUOTE & PROPOSAL
Say: "Based on what you've shared, MMRI will put together a quote for you." If they gave a timeline → add: "And since you have a timeline in mind, we'll also prepare a Scope of Work for your review."

STEP 10 — CONFIRMATION SUMMARY
Recap everything warmly and concisely: "Just to make sure I've got everything right — [name] from [company], [email], [project type], [one-line description], timeline [X], budget [range]. Does that all look good?"
If the partner gave a specific dollar figure or ROI estimate in Step 5, include it explicitly instead of just the bucket range: "...timeline [X], and you're estimating around [$ figure] in savings [annual/total, per the basis they gave]. Does that all look good?"
If they want to correct anything, update and re-confirm.

STEP 11 — APPROVAL & NEXT STEPS
Once confirmed: "Wonderful — let's get you connected with our team!"
- If Fee-for-Service → "You can book a kickoff call right here: [CALENDLY_LINK] — pick whatever time works best for you. Someone will be in touch shortly to confirm everything."
- If Funded → "Since this is a funded project, the next step is a funding proposal. You can book a call to kick that off here: [CALENDLY_LINK]"
Then output MATCH and FOLLOWUP tags.
- If NO → "No worries at all — thanks so much for reaching out. Feel free to come back anytime if things change!"

LANGUAGE RULES:
- Never say: CBM, MSL, MPAL, OEE, FMEA, KPI, predictive maintenance, condition monitoring
- Always say: "our equipment health team", "our materials team", "our manufacturing process team", "our training team"
- Use analogies: "think of it like a check engine light for your machines"
- Keep responses short — 2-4 sentences max per message
- Ask only ONE question at a time
- Be warm, friendly, and non-technical at all times
- Maximum 2-3 sentences per message — be concise
- Use contractions (you're, we'll, that's, I'll)
- Never say "Certainly!", "Of course!", "Absolutely!" — just respond naturally
- Never explain what you're about to do, just do it
- Sound like a friendly, knowledgeable person, not a form

PROJECT CATEGORY GUIDE:
Based on the partner's description, identify which category of work this falls under. Use ONLY these four categories:
- Materials & Testing: material testing, characterization, property assessment, product development, prototyping, refinement
- Equipment Health & Monitoring: equipment breaking down, performance monitoring, predictive health, condition monitoring
- Manufacturing Process: CNC, machining, process development, manufacturing improvement, automation, fabrication
- Training & Knowledge Transfer: workforce training, upskilling, knowledge transfer, professional development

IMPORTANT LANGUAGE RULES FOR CATEGORIES:
- Never say MSL, CBM, MPAL, or any specific sub-team names
- Always describe the category in plain language: "our materials and testing team", "our equipment health team", "our manufacturing process team", "our training team"
- Sub-team assignment will be done internally by MMRI staff after intake — ETHOS does not assign sub-teams

At the end when you have enough info, output:
MATCH: [category name] | CONFIDENCE: [percentage]%

For example:
MATCH: Equipment Health & Monitoring | CONFIDENCE: 88%

If the project spans multiple categories:
MATCH: [primary category] | CONFIDENCE: [percentage]%
MATCH: [secondary category] | CONFIDENCE: [percentage]%

Before the MATCH tags, briefly explain in plain language why this category fits — for example: "Based on what you've described, this sounds like it falls into our equipment health and monitoring space, since you're dealing with machine performance issues."

After the match, output the internal priority level determined in Step 6:
PRIORITY: [High/Medium/Low]

For example:
PRIORITY: High

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
            "content": f"From this conversation extract: partner name, company name, email, phone, company overview, problem description, project type, company size, timeline, and budget_estimate (any specific dollar figure or quantified savings/ROI estimate the partner gave, plus whether annual or total — leave blank if only a bucket range was given). Return ONLY a JSON object with no markdown, no backticks, just raw JSON like this: {{\"name\": \"...\", \"company\": \"...\", \"email\": \"...\", \"phone\": \"...\", \"overview\": \"...\", \"problem\": \"...\", \"project_type\": \"...\", \"company_size\": \"...\", \"timeline\": \"...\", \"budget_estimate\": \"...\"}}\n\nConversation:\n{conversation_summary}"
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
        budget_estimate = extracted.get('budget_estimate', '')
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
        budget_estimate = ''

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
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
        # ───────────────────────── LETTERHEAD-STYLE FFS VERSION ─────────────────────────
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            rightMargin=0.75*inch, leftMargin=0.75*inch,
            topMargin=0.6*inch, bottomMargin=0.7*inch
        )

        ink_soft2 = HexColor('#4A4540')
        border_col = HexColor('#231F20')

        uni_style = ParagraphStyle('Uni', parent=styles['Normal'], fontName='Times-Bold', fontSize=15, textColor=ink, leading=17)
        eng_style = ParagraphStyle('Eng', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=ink, leading=13, spaceBefore=1)
        mmri_style = ParagraphStyle('Mmri', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, textColor=ink_soft2, leading=11)
        contact_style = ParagraphStyle('Contact', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8.5,
            textColor=ink_soft2, alignment=TA_RIGHT, leading=11)
        table_header_style = ParagraphStyle('TH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=ink)
        table_value_style = ParagraphStyle('TV', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=ink, leading=13)
        q_style = ParagraphStyle('Q', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=ink, spaceAfter=4, leading=13)
        a_style = ParagraphStyle('A', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=ink, leading=14)
        footer_brand_style = ParagraphStyle('FooterBrand', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13, textColor=maroon)

        def qa_box(question, answer):
            answer_flowables = [Paragraph(answer, a_style)] if isinstance(answer, str) else answer
            cell_content = [Paragraph(question, q_style)] + answer_flowables
            t = Table([[cell_content]], colWidths=[6.75*inch])
            t.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 0.75, border_col),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ]))
            return t

        story = []

        left_header = [
            Paragraph("McMaster<br/>University", uni_style),
            Spacer(1, 2),
            Paragraph("ENGINEERING", eng_style),
            Paragraph("McMaster Manufacturing<br/>Research Institute (MMRI)", mmri_style),
        ]
        right_header = [
            Paragraph("<i>McMaster Manufacturing Research Institute</i>", contact_style),
            Paragraph("230 Longwood Rd. S.", contact_style),
            Paragraph("Hamilton, ON L8P 0A6", contact_style),
            Spacer(1, 4),
            Paragraph("(365) 366-6638", contact_style),
            Paragraph("mmri-ad@mcmaster.ca", contact_style),
            Paragraph("eng.mcmaster.ca/manufacturing-research-institute-mmri", contact_style),
        ]
        header_table = Table([[left_header, right_header]], colWidths=[3.2*inch, 3.55*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 14))

        info_header = [Paragraph("Name", table_header_style), Paragraph("Company", table_header_style), Paragraph("Date", table_header_style)]
        info_values = [Paragraph(partner_name, table_value_style), Paragraph(company, table_value_style), Paragraph(today_str, table_value_style)]
        info_table = Table([info_header, info_values], colWidths=[2.25*inch, 2.75*inch, 1.75*inch])
        info_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.75, border_col),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(info_table)

        story.append(qa_box("Describe the problem or challenge the partner wants to address.", problem))
        story.append(qa_box("Project type and estimated timeline.", f"{project_type} &nbsp;&middot;&nbsp; {timeline if timeline else 'Not specified'}"))
        story.append(qa_box("Company size.", company_size))
        budget_line = budget_estimate if budget_estimate else "Not specified by partner (bucket range only, see internal notes)."
        story.append(qa_box("Estimated budget / ROI, as shared by the partner.", budget_line))

        recommended_row = Table(
            [[Paragraph("Recommended MMRI Category", ParagraphStyle('rc', parent=q_style, textColor=HexColor('#FFFFFF'))),
              Paragraph(f"{confidence}% confidence", ParagraphStyle('cc', parent=a_style, textColor=gold_bright, alignment=TA_RIGHT))],
             [Paragraph(matched_team, ParagraphStyle('mt', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13, textColor=HexColor('#FFFFFF'))), '']],
            colWidths=[5*inch, 1.75*inch]
        )
        recommended_row.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), maroon),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,0), 8),
            ('BOTTOMPADDING', (0,1), (-1,1), 10),
            ('TOPPADDING', (0,1), (-1,1), 2),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(recommended_row)
        story.append(Spacer(1, 4))

        story.append(qa_box("Contact information.", f"{email} &nbsp;&middot;&nbsp; {phone}"))
        story.append(qa_box("Next steps.", "MMRI team reaches out to confirm scope and quote. Kickoff and work begin shortly after."))

        story.append(Spacer(1, 18))
        story.append(HRFlowable(width="100%", thickness=2, color=maroon))
        story.append(Spacer(1, 6))
        story.append(Paragraph("BRIGHTER WORLD", footer_brand_style))

        doc.build(story)
        
    else:
        # ───────────────────────── LETTERHEAD-STYLE FUNDED VERSION ─────────────────────────
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            rightMargin=0.75*inch, leftMargin=0.75*inch,
            topMargin=0.6*inch, bottomMargin=0.7*inch
        )

        table_header_bg = maroon
        table_alt_bg = HexColor('#F4F0EE')
        ink2 = HexColor('#231F20')
        border_col = HexColor('#231F20')

        uni_style = ParagraphStyle('Uni2', parent=styles['Normal'], fontName='Times-Bold', fontSize=15, textColor=ink2, leading=17)
        eng_style = ParagraphStyle('Eng2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=ink2, leading=13, spaceBefore=1)
        mmri_style = ParagraphStyle('Mmri2', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, textColor=ink_soft, leading=11)
        contact_style = ParagraphStyle('Contact2', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8.5,
            textColor=ink_soft, alignment=TA_RIGHT, leading=11)
        table_header_style = ParagraphStyle('TH2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=ink2)
        table_value_style = ParagraphStyle('TV2', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=ink2, leading=13)
        q_style = ParagraphStyle('Q2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=ink2, spaceAfter=4, leading=13)
        a_style = ParagraphStyle('A2', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=ink2, leading=14)
        footer_brand_style = ParagraphStyle('FooterBrand2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13, textColor=maroon)

        doc_title_style = ParagraphStyle('DocTitle', parent=styles['Title'], fontName='Helvetica-Bold',
            fontSize=15, textColor=ink2, alignment=TA_CENTER, spaceAfter=6)
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

        def qa_box(question, answer):
            answer_flowables = [Paragraph(answer, a_style)] if isinstance(answer, str) else answer
            cell_content = [Paragraph(question, q_style)] + answer_flowables
            t = Table([[cell_content]], colWidths=[6.75*inch])
            t.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 0.75, border_col),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ]))
            return t

        def section_band(text):
            t = Table([[Paragraph(text, section_header_style)]], colWidths=[6.75*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), table_header_bg),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            return t

        story = []

        left_header = [
            Paragraph("McMaster<br/>University", uni_style),
            Spacer(1, 2),
            Paragraph("ENGINEERING", eng_style),
            Paragraph("McMaster Manufacturing<br/>Research Institute (MMRI)", mmri_style),
        ]
        right_header = [
            Paragraph("<i>McMaster Manufacturing Research Institute</i>", contact_style),
            Paragraph("230 Longwood Rd. S.", contact_style),
            Paragraph("Hamilton, ON L8P 0A6", contact_style),
            Spacer(1, 4),
            Paragraph("(365) 366-6638", contact_style),
            Paragraph("mmri-ad@mcmaster.ca", contact_style),
            Paragraph("eng.mcmaster.ca/manufacturing-research-institute-mmri", contact_style),
        ]
        header_table_top = Table([[left_header, right_header]], colWidths=[3.2*inch, 3.55*inch])
        header_table_top.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(header_table_top)
        story.append(Spacer(1, 12))

        story.append(Paragraph("Project Intake Summary", doc_title_style))

        info_header = [Paragraph("Name", table_header_style), Paragraph("Company", table_header_style), Paragraph("Date", table_header_style)]
        info_values = [Paragraph(partner_name, table_value_style), Paragraph(company, table_value_style), Paragraph(today_str, table_value_style)]
        info_table = Table([info_header, info_values], colWidths=[2.25*inch, 2.75*inch, 1.75*inch])
        info_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.75, border_col),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(info_table)
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
            ('GRID', (0,0), (-1,-1), 0.5, border_col),
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
        story.append(qa_box("1.1 &nbsp;Contact Information", f"{email} &nbsp;&middot;&nbsp; {phone} &nbsp;&middot;&nbsp; Company size: {company_size} &nbsp;&middot;&nbsp; Project type: {project_type}"))
        story.append(qa_box("1.2 &nbsp;Company Overview", overview if overview else "Not provided during intake."))
        story.append(qa_box("1.3 &nbsp;Purpose", problem))
        budget_line = budget_estimate if budget_estimate else "Not specified by partner (bucket range only, see internal notes)."
        story.append(qa_box("1.4 &nbsp;Timeline &amp; Budget/ROI Considerations", f"<b>Indicated timeline:</b> {timeline if timeline else 'Not specified'}<br/><b>Budget/ROI estimate:</b> {budget_line}"))

        story.append(section_band("2. Recommended MMRI Team"))
        story.append(Spacer(1, 6))
        recommended_row = Table(
            [[Paragraph("Recommended MMRI Category", ParagraphStyle('rc2', parent=q_style, textColor=HexColor('#FFFFFF'))),
              Paragraph(f"{confidence}% confidence", ParagraphStyle('cc2', parent=a_style, textColor=gold_bright, alignment=TA_RIGHT))],
             [Paragraph(team_full_name, ParagraphStyle('mt2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13, textColor=HexColor('#FFFFFF'))), '']],
            colWidths=[5*inch, 1.75*inch]
        )
        recommended_row.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), maroon),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,0), 8),
            ('BOTTOMPADDING', (0,1), (-1,1), 10),
            ('TOPPADDING', (0,1), (-1,1), 2),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(recommended_row)

        story.append(section_band("3. Project Requirements"))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "In this document, the term <b>SHALL</b> indicates a requirement that must be satisfied. The term "
            "<b>SHOULD</b> indicates a recommendation that is advised but not required. The specific technical "
            "requirements for this engagement have not yet been defined and will be developed collaboratively "
            "by the assigned MMRI team lead in consultation with the partner.", body_style2
        ))
        story.append(qa_box("3.1 &nbsp;Scope of MMRI Involvement", "To be defined by MMRI team lead following kickoff meeting."))
        story.append(qa_box("3.2 &nbsp;Items Outside of Project Scope", "To be defined by MMRI team lead following kickoff meeting."))

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
            ('GRID', (0,0), (-1,-1), 0.5, border_col),
            ('BACKGROUND', (0,0), (-1,0), table_alt_bg),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(steps_table)

        story.append(Spacer(1, 16))
        story.append(HRFlowable(width="100%", thickness=2, color=maroon))
        story.append(Spacer(1, 6))
        story.append(Paragraph("BRIGHTER WORLD", footer_brand_style))

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
    priority = data.get('priority', '')

    extract_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"From this conversation extract: partner name, company name, email, phone, project description, project type, company size, address if mentioned, and budget_estimate (any specific dollar figure or quantified savings/ROI estimate the partner gave, plus whether they said it's annual or total — leave blank if they only gave a bucket range like 'under $5k'). Return ONLY raw JSON: {{\"name\": \"...\", \"company\": \"...\", \"email\": \"...\", \"phone\": \"...\", \"description\": \"...\", \"project_type\": \"...\", \"company_size\": \"...\", \"address\": \"...\", \"budget_estimate\": \"...\"}}\n\nConversation:\n{conversation_summary}"
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

    description_extras = f"\n\nETHOS Category Match: {matched_team}"
    if priority:
        description_extras += f"\nETHOS Priority: {priority}"
    budget_estimate = extracted.get('budget_estimate', '')
    if budget_estimate:
        description_extras += f"\nBudget/ROI Estimate: {budget_estimate}"

    fields = {
    "Title": f"{extracted.get('company', 'Unknown')} - Intake",
    "Project Code": project_code,
    "Partner": extracted.get('company', 'Unknown'),
    "Project Description": extracted.get('description', '') + description_extras,
    "Start Date": datetime.now().strftime('%Y-%m-%d'),
    "Program Type": extracted.get('project_type', ''),
    "Sub-Group": "",
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

    # Pull live Supabase project data
    supabase_summary = ""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT "Title", "Project Code", "Partner", "Project Status", 
                   "Sub-Group", "Program Type", "Start Date", "MMRI Lead"
            FROM "MMRI Database" 
            ORDER BY id DESC 
            LIMIT 50
        ''')
        rows = cur.fetchall()
        cur.execute('SELECT COUNT(*) FROM "MMRI Database"')
        total = cur.fetchone()[0]
        cur.execute('''SELECT "Project Status", COUNT(*) as count 
                      FROM "MMRI Database" 
                      GROUP BY "Project Status"''')
        status_counts = cur.fetchall()
        cur.execute('''SELECT "Sub-Group", COUNT(*) as count 
                      FROM "MMRI Database" 
                      WHERE "Sub-Group" IS NOT NULL AND "Sub-Group" != \'\'
                      GROUP BY "Sub-Group"''')
        team_counts = cur.fetchall()
        cur.close()
        conn.close()

        supabase_summary = f"TOTAL PROJECTS IN DATABASE: {total}\n\n"
        supabase_summary += "PROJECT STATUS BREAKDOWN:\n"
        for s in status_counts:
            if s[0]:
                supabase_summary += f"  - {s[0]}: {s[1]}\n"
        supabase_summary += "\nPROJECTS BY TEAM:\n"
        for t in team_counts:
            if t[0]:
                supabase_summary += f"  - {t[0]}: {t[1]}\n"
        supabase_summary += "\nRECENT 50 PROJECTS:\n"
        for r in rows:
            supabase_summary += f"  [{r[1] or 'No code'}] {r[0] or 'Untitled'} | Partner: {r[2] or 'Unknown'} | Status: {r[3] or 'Unknown'} | Team: {r[4] or 'N/A'} | Lead: {r[7] or 'N/A'}\n"
    except Exception as e:
        supabase_summary = f"Database currently unavailable: {str(e)}"

    bob_system = f"""You are BOB, the internal AI assistant for the McMaster Manufacturing Research Institute (MMRI). You serve MMRI staff — helping them find partner information, track project status, understand internal workflows, and access the knowledge base.

You have access to:
1. Live MMRI project database (172+ real projects from Supabase)
2. Recent ETHOS partner intake conversations (last 20)
3. Internal documents uploaded via the Training Agent
4. Full details of Kristin's and Darren's internal workflows

RESPONSE STYLE:
- Be concise and direct — staff are busy, get to the point fast
- Use bullet points and structure for multi-part answers
- When citing a project, always include the project code if known
- When citing a conversation, mention the date
- If you don't have the information, say so clearly rather than guessing
- For workflow questions, cite the specific step number

LIVE PROJECT DATABASE:
{supabase_summary}

RECENT ETHOS INTAKE CONVERSATIONS:
{conversations_text if conversations_text else "No conversations yet."}

INTERNAL KNOWLEDGE BASE:
{knowledge if knowledge else "No documents uploaded yet."}

MMRI SUB-TEAMS:
- MSL (Machining Systems Laboratory) — Lead: Brady Semple
- CBM (Condition-Based Monitoring) — Lead: Kristin Bennett
- MPAL (Manufacturing Process Analysis Lab) — Lead: Darren Feenstra
- Training — Lead: Sean
- MCC (McMaster Centre for Computational Engineering)
- Internal projects

KEY STAFF:
- Darren Feenstra: MPAL lead/director
- Kristin Bennett: PM/CBM lead
- Brady Semple: MSL lead
- Kevin Lytwyn: MPAL
- Sean: Training/project codes/IT
- Steve Remilli: MMRI Database
- Ellen/Sam: Billing

KRISTIN'S PROJECT WORKFLOW:
STEP 1 — INITIATION:
  - Create project folder (OCI or ORF Team)
  - Request project code from Sean
  - Project kickoff with client
  - Develop proposal (DRF) or SOW (OCI) + quote
  - Tools: Proposal/SOW template, quoting tool, project codes sheet
  - Client approval → if No: revise proposal; if Yes: proceed to Planning

STEP 2 — PLANNING:
  - Request Infinity X / LIMS form (MMRI Admin)
  - Create SOW (ORF)
  - Complete MMRI promotion form (if applicable)
  - Assign MS Planner buckets and tasks

STEP 3 — EXECUTION:
  - Execute project as per SOW
  - Client receives deliverables

STEP 4 — CLOSURE:
  - Transfer OCI files to MMRI archive, delete channel
  - Update and close MS Planner tasks
  - Update LIMS/Infinity X form to next stage
  - Update project status in project codes list
  → Project closed

DARREN'S PROJECT WORKFLOW:
STEP 1 — INTAKE: Incoming via Diss/Chat/Email → RFQ → Tech/Design review → Milestone/OBS. RFQ connects to Funding, OCI, Steve.
STEP 2 — QUOTING: Quote → Excel SPLIT → Quote tool + outputs (FAB/LES/Kevin, Machine time, Report/Analysis, Sub-contract). Iterate until agreed.
STEP 3 — SCOPE: Submit Q to customer ↔ Iterate → Q Accept → Scope doc finalized
STEP 4 — CODE REQUEST: Q Accept → Code request → KS, Hour allocation, PMP doc. Also → P.O → Billing
STEP 5 — KICKOFF: Mail received → Kick-off → Assign tasks / Update timeline (Teams, PMP doc, email)
STEP 6 — EXECUTION: Work → Clockify + LIMS/Infinity X Form/Rock → MPAL-PMP Drive → Submit report
STEP 7 — BILLING: Billing → Infinity X / Ellen / Sam → Budget vs Actual → Rate review
STEP 8 — CLOSE: Outcomes/Success → Follow-up

WHAT BOB CAN ANSWER:
- "What projects are active for [team]?" → query the database summary above
- "What's the status of project [code]?" → look in the database
- "What happens after Q Accept?" → reference Darren's workflow Step 4
- "Who is the lead on MSL?" → Brady Semple
- "What did the last partner intake say?" → check recent ETHOS conversations
- "How many projects are committed-active?" → check status breakdown above
- "What's in the knowledge base about [topic]?" → check internal documents

Always be helpful, specific, and cite your source (database, conversation, workflow, or knowledge base)."""

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