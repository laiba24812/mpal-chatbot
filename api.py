import os
import json
import base64
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import anthropic
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

    return f"""You are ETHOS, the intelligent assistant for the McMaster Manufacturing Research Institute (MMRI). Your job is to help industry partners find the right MMRI team for their manufacturing challenge and collect the information MMRI needs to get started.

MMRI SUB-TEAMS:
MSL: {TEAM_DESCRIPTIONS['MSL']}
CBM: {TEAM_DESCRIPTIONS['CBM']}
MPAL: {TEAM_DESCRIPTIONS['MPAL']}
Training: {TEAM_DESCRIPTIONS['Training']}

INTERNAL MMRI KNOWLEDGE BASE:
{knowledge if knowledge else "No internal documents uploaded yet."}

CONVERSATION FLOW:
1. Greet the partner warmly and ask for their name, company name, and email address.
2. Once you have those, ask: "Can you give me a quick overview of what your company does and who your customers are?"
3. Ask: "What's been giving you trouble lately in your production or manufacturing?" If they struggle, offer examples: "For example, is something breaking down too often? Are your parts not coming out right? Is a process taking too long?"
4. Ask: "Which of these best describes what you're looking for help with?" and offer these options in plain language:
   - Understanding or testing your materials
   - Developing or refining a product
   - Prototyping support
   - Improving a manufacturing process
   - Monitoring equipment health and performance
   - Something else
5. Ask 1 follow-up question max to clarify if needed.
6. Ask: "Roughly how many employees does your company have?" and "What timeline are you working with for this project?"
7. Match them to the best sub-team and explain in plain everyday language.

LANGUAGE RULES:
- Never say: CBM, MSL, MPAL, OEE, FMEA, KPI, predictive maintenance, condition monitoring
- Always say: "our equipment health team", "our materials team", "our manufacturing process team", "our training team"
- Use analogies: "think of it like a check engine light for your machines"
- Keep responses short — 2-4 sentences max per message
- Ask only ONE question at a time

TEAM ROUTING GUIDE:
- Material testing, characterization, property assessment → MSL
- Product development, refinement → MSL
- Prototyping → MSL or MPAL
- Process development, CNC, machining, manufacturing improvement → MPAL
- Equipment breaking down, performance monitoring, predictive health → CBM
- Workforce training, knowledge transfer → Training

At the end when you have enough info to match, include:
MATCH: [team name] | CONFIDENCE: [percentage]%
If multiple teams are relevant:
MATCH: [team name] | CONFIDENCE: [percentage]%
MATCH: [team name] | CONFIDENCE: [percentage]%

After the match, include 1-2 follow-up questions:
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

@app.route('/api/upload', methods=['POST'])
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
        project_type = extracted.get('project_type', '')
        company_size = extracted.get('company_size', '')
        timeline = extracted.get('timeline', '')
    except:
        partner_name = 'Unknown'
        company = 'Unknown'
        email = 'Not provided'
        phone = 'Not provided'
        overview = ''
        problem = ''
        project_type = ''
        company_size = ''
        timeline = ''

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
    maroon = HexColor('#7A003C')

    title_style = ParagraphStyle('Title', parent=styles['Title'],
                                  textColor=maroon, fontSize=24, spaceAfter=6)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
                                     textColor=HexColor('#666666'), fontSize=11, spaceAfter=20)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'],
                                    textColor=maroon, fontSize=13, spaceBefore=16, spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                 fontSize=11, spaceAfter=8, leading=16)

    story = []

    story.append(Paragraph("MMRI Project Scoping Document", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=maroon))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Partner Information", heading_style))
    story.append(Paragraph(f"<b>Name:</b> {partner_name}", body_style))
    story.append(Paragraph(f"<b>Company:</b> {company}", body_style))
    story.append(Paragraph(f"<b>Email:</b> {email}", body_style))
    story.append(Paragraph(f"<b>Phone:</b> {phone}", body_style))
    story.append(Paragraph(f"<b>Company Size:</b> {company_size}", body_style))

    if overview:
        story.append(Paragraph("Company Overview", heading_style))
        story.append(Paragraph(overview, body_style))

    story.append(Paragraph("Project Details", heading_style))
    story.append(Paragraph(f"<b>Project Type:</b> {project_type}", body_style))
    story.append(Paragraph(f"<b>Timeline:</b> {timeline}", body_style))

    story.append(Paragraph("Problem Description", heading_style))
    story.append(Paragraph(problem, body_style))

    story.append(Paragraph("Recommended MMRI Team", heading_style))
    story.append(Paragraph(f"<b>Team:</b> {matched_team}", body_style))
    story.append(Paragraph(f"<b>Match Confidence:</b> {confidence}%", body_style))
    story.append(Paragraph(f"<b>Why this team:</b> {TEAM_DESCRIPTIONS.get(matched_team, '')}", body_style))

    story.append(Paragraph("Conversation Summary", heading_style))
    clean_summary = conversation_summary.encode('ascii', 'replace').decode('ascii')
    story.append(Paragraph(clean_summary.replace('\n', '<br/>'), body_style))

    story.append(Paragraph("Next Steps", heading_style))
    story.append(Paragraph("1. Review this scoping document with the MMRI team lead", body_style))
    story.append(Paragraph("2. Schedule a kickoff meeting to discuss project details", body_style))
    story.append(Paragraph("3. Sign NDA and project agreement", body_style))
    story.append(Paragraph("4. Begin project scoping and timeline planning", body_style))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#cccccc')))
    story.append(Spacer(1, 8))
    story.append(Paragraph("McMaster Manufacturing Research Institute · 230 Longwood Rd S, Hamilton ON · mmri-ad@mcmaster.ca · 905-525-9140",
                            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=HexColor('#999999'))))

    doc.build(story)
    buffer.seek(0)

    from flask import send_file
    return send_file(buffer, mimetype='application/pdf',
                     as_attachment=True,
                     download_name=f'MMRI_Scoping_{company}_{datetime.now().strftime("%Y%m%d")}.pdf')

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

    bob_system = f"""You are BOB, an internal assistant for the McMaster Manufacturing Research Institute (MMRI) staff. You help MMRI team members quickly find information about partners, past projects, and internal knowledge.

You have access to:
1. Recent ETHOS partner conversations
2. Internal MMRI documents uploaded by managers

RECENT ETHOS CONVERSATIONS:
{conversations_text if conversations_text else "No conversations yet."}

INTERNAL MMRI KNOWLEDGE BASE:
{knowledge if knowledge else "No documents uploaded yet."}

MMRI SUB-TEAMS:
- MSL (Machining Systems Laboratory) — Brady
- CBM (Condition-Based Monitoring) — Kristin
- MPAL (Manufacturing Process Analysis Lab) — Darren
- Training — Sean

Be concise and helpful. When answering about a specific partner or project, cite which conversation or document you found the info in."""

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

@app.route('/bob')
def serve_bob():
    return send_from_directory('.', 'bob.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)