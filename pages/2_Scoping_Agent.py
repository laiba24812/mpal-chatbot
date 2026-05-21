import os
from dotenv import load_dotenv
load_dotenv()
import anthropic
import streamlit as st

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def generate_pdf(scoping_text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=72)

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#7A003C'),
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#7A003C'),
        spaceAfter=6,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        leading=16,
        fontName='Helvetica'
    )

    divider_style = ParagraphStyle(
        'Divider',
        parent=styles['Normal'],
        fontSize=1,
        spaceAfter=10,
        spaceBefore=10,
    )

    story = []
    story.append(Paragraph("MMRI Project Scoping Document", title_style))
    story.append(Spacer(1, 12))

    # Clean and process lines
    lines = scoping_text.split('\n')
    for line in lines:
        line = line.strip()

        # Skip empty lines, dividers, and the header/footer text
        if not line or line == '---' or line == '**MMRI PROJECT SCOPING DOCUMENT**' or line == 'MMRI PROJECT SCOPING DOCUMENT':
            continue

        # Skip the "does this look correct" question
        if 'Does this look correct' in line:
            continue

        # Clean markdown bold markers
        line = line.replace('**', '')

        # Detect section headings (all caps lines or lines ending with :)
        if line.isupper() or (line.endswith(':') and len(line) < 40):
            story.append(Paragraph(line, heading_style))
        elif line.startswith(('1.', '2.', '3.', '4.')):
            story.append(Paragraph(line, body_style))
        else:
            story.append(Paragraph(line, body_style))

        story.append(Spacer(1, 4))

    doc.build(story)
    buffer.seek(0)
    return buffer

st.set_page_config(
    page_title="MMRI Scoping Agent",
    page_icon="📋",
    layout="centered"
)

st.markdown("""
    <style>
        .stApp { background-color: #1a1a1a; }
        .header {
            background-color: #7A003C;
            padding: 20px 30px;
            border-radius: 12px;
            margin-bottom: 20px;
        }
        .header h1 { color: #FDBF57; font-size: 24px; margin: 0; }
        .header p { color: #ffffff; margin: 0; font-size: 13px; opacity: 0.85; }
        .stButton > button {
            background-color: #2a2a2a;
            color: #FDBF57;
            border: 1px solid #7A003C;
            border-radius: 20px;
            padding: 6px 16px;
            font-size: 13px;
        }
        .stButton > button:hover { background-color: #7A003C; color: white; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="header">
        <div>
            <h1>📋 MMRI Scoping Agent</h1>
            <p>McMaster Manufacturing Research Institute · Let's scope your project</p>
        </div>
    </div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://www.eng.mcmaster.ca/wp-content/uploads/2022/09/MMRI-Logo.png", width=200)
    st.markdown("### 🏭 MPAL Team")
    st.markdown("""
    **Team Lead:** Darren Feenstra  
    **Email:** mmri-ad@mcmaster.ca  
    **Phone:** 905-525-9140
    """)
    st.markdown("---")
    if st.button("🗑️ Clear Chat"):
        st.session_state.scoping_conversation = []
        st.session_state.scoping_initialized = False
        st.rerun()

SCOPING_SYSTEM_PROMPT = """You are a scoping agent for the McMaster Manufacturing Research Institute (MMRI).

Your job is to take information collected from a potential client and immediately draft a clear scoping document in this exact format:

---
MMRI PROJECT SCOPING DOCUMENT

Client Name: [name from conversation]
Company: [company from conversation]
Email: [email from conversation]
Date: [today's date]

PROBLEM SUMMARY:
[2-3 sentences describing the manufacturing problem in plain language]

RECOMMENDED MMRI SERVICE:
[Which MMRI capability fits best and why, in plain language]

PROPOSED NEXT STEPS:
1. Initial meeting with MPAL team lead Darren Feenstra
2. Site visit to understand the equipment and environment
3. Proposal development and project scoping
4. Project kickoff

MPAL TEAM LEAD: Darren Feenstra
CONTACT: mmri-ad@mcmaster.ca | 905-525-9140
---

After drafting the document, ask: "Does this look correct? Would you like me to confirm this with the MMRI team?"

If they say yes, say: "Perfect! This has been flagged for the MMRI team. Darren Feenstra will be in touch within 1-2 business days at the email you provided. You can also reach us at mmri-ad@mcmaster.ca or 905-525-9140."

Keep your tone friendly and professional. Use plain language throughout."""

# Reset scoping conversation when coming fresh from intake chatbot
if st.session_state.get("ready_for_scoping") and "scoping_initialized" not in st.session_state:
    st.session_state.scoping_conversation = []
    st.session_state.scoping_initialized = True

if "scoping_conversation" not in st.session_state:
    st.session_state.scoping_conversation = []

if len(st.session_state.scoping_conversation) == 0:
    conversation_summary = st.session_state.get("client_info", {}).get("conversation_summary", "")

    if conversation_summary:
        opening_message = "Hi again! 👋 I've received your information from the intake chat. Let me draft a scoping document for the MMRI team right away..."
        st.session_state.scoping_conversation.append({
            "role": "assistant",
            "content": opening_message
        })
        st.session_state.scoping_conversation.append({
            "role": "user",
            "content": f"Here is the intake conversation summary:\n\n{conversation_summary}\n\nPlease draft a scoping document based on this."
        })
    else:
        opening_message = "Hi! 👋 I'm the MMRI Scoping Agent. I'll help turn your manufacturing challenge into a project scoping document.\n\nCan you give me a quick summary of your problem, and your name, company, and email?"
        st.session_state.scoping_conversation.append({
            "role": "assistant",
            "content": opening_message
        })

# Display conversation — skip the hidden user summary message
for message in st.session_state.scoping_conversation:
    if message["role"] == "user" and "intake conversation summary" in message["content"]:
        continue
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Auto-generate scoping document if coming from intake
if (len(st.session_state.scoping_conversation) == 2 and
        st.session_state.scoping_conversation[-1]["role"] == "user"):

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_placeholder.write("Drafting your scoping document... 📋")
        full_response = ""

        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SCOPING_SYSTEM_PROMPT,
            messages=st.session_state.scoping_conversation
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                response_placeholder.write(full_response + "▌")
            response_placeholder.write(full_response)

    st.session_state.scoping_conversation.append({
        "role": "assistant",
        "content": full_response
    })

user_input = st.chat_input("Type your response here...")

if user_input:
    st.session_state.scoping_conversation.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_placeholder.write("MMRI Scoping Agent is thinking... 📋")
        full_response = ""

        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SCOPING_SYSTEM_PROMPT,
            messages=st.session_state.scoping_conversation
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                response_placeholder.write(full_response + "▌")
            response_placeholder.write(full_response)

    st.session_state.scoping_conversation.append({
        "role": "assistant",
        "content": full_response
    })

# Show download button if scoping document has been generated
if len(st.session_state.scoping_conversation) >= 3:
    for message in st.session_state.scoping_conversation:
        if message["role"] == "assistant" and "MMRI PROJECT SCOPING DOCUMENT" in message["content"]:
            pdf_buffer = generate_pdf(message["content"])
            st.download_button(
                label="📄 Download Scoping Document as PDF",
                data=pdf_buffer,
                file_name="MMRI_Scoping_Document.pdf",
                mime="application/pdf"
            )
            break

st.markdown("""
    <div class="footer">
        McMaster Manufacturing Research Institute · 230 Longwood Rd S, Hamilton ON · 905-525-9140
    </div>
""", unsafe_allow_html=True)