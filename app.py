import os
from dotenv import load_dotenv
load_dotenv()
import anthropic
import streamlit as st
import requests
from bs4 import BeautifulSoup

def scrape_mmri_page(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        text = soup.get_text(separator=' ', strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return ' '.join(lines)[:3000]
    except:
        return ""

@st.cache_data
def get_mmri_content():
    urls = [
        "https://www.eng.mcmaster.ca/mmri-home/",
        "https://www.eng.mcmaster.ca/mmri-home/our-focus/",
        "https://www.eng.mcmaster.ca/mmri-home/facilities/",
        "https://www.eng.mcmaster.ca/mmri-home/research/",
        "https://www.eng.mcmaster.ca/mmri-home/contact/",
    ]
    content = ""
    for url in urls:
        page_content = scrape_mmri_page(url)
        if page_content:
            content += f"\n\nFrom {url}:\n{page_content}"
    return content

mmri_content = get_mmri_content()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

st.set_page_config(
    page_title="MMRI Assistant",
    page_icon="🔬",
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
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .header h1 { color: #FDBF57; font-size: 24px; margin: 0; font-family: 'Georgia', serif; }
        .header p { color: #ffffff; margin: 0; font-size: 13px; opacity: 0.85; }
        .stChatMessage { background-color: #2a2a2a; border-radius: 10px; padding: 10px; margin-bottom: 8px; }
        .stChatInputContainer { border-top: 2px solid #7A003C; padding-top: 10px; }
        .stButton > button {
            background-color: #2a2a2a;
            color: #FDBF57;
            border: 1px solid #7A003C;
            border-radius: 20px;
            padding: 6px 16px;
            font-size: 13px;
            transition: all 0.2s;
        }
        .stButton > button:hover { background-color: #7A003C; color: white; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; }
        .handoff-box {
            background-color: #2a2a2a;
            border: 1px solid #7A003C;
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
        }
        .handoff-box h3 { color: #FDBF57; margin-top: 0; }
        .handoff-box p { color: #ffffff; margin: 5px 0; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="header">
        <div>
            <h1>🔬 MMRI Assistant</h1>
            <p>McMaster Manufacturing Research Institute · Ask me anything about MMRI</p>
        </div>
    </div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://www.eng.mcmaster.ca/wp-content/uploads/2022/09/MMRI-Logo.png", width=200)
    st.markdown("### 📞 Contact MMRI")
    st.markdown("""
    **Address:**  
    230 Longwood Rd S  
    Hamilton, ON L8P 0A6
    
    **Phone:** 905-525-9140  
    **Hours:** Mon-Fri 8:30am-4:30pm  
    **Email:** mmri-ad@mcmaster.ca
    """)
    st.markdown("---")
    st.markdown("### 💡 Suggested Questions")
    if st.button("What does MMRI do?"):
        st.session_state.starter = "What does MMRI do?"
    if st.button("What facilities are available?"):
        st.session_state.starter = "What facilities are available?"
    if st.button("How do I contact MMRI?"):
        st.session_state.starter = "How do I contact MMRI?"
    if st.button("What industries do you work with?"):
        st.session_state.starter = "What industries do you work with?"
    if st.button("What condition monitoring services do you offer?"):
        st.session_state.starter = "What condition monitoring services do you offer?"
    st.markdown("---")
    st.markdown("### 🏭 MPAL Team")
    st.markdown("""
    **Head:** Darren Feenstra
    
    **Team Members:**
    - Laiba Yousafzai
    - Mahdi
    """)
    st.markdown("---")
    if st.button("🗑️ Clear Chat"):
        st.session_state.conversation = []
        st.session_state.client_info = {}
        st.session_state.ready_for_scoping = False
        st.rerun()

SYSTEM_PROMPT = f"""You are a friendly assistant for the McMaster Manufacturing Research Institute (MMRI). Your job is to help people from industry who have manufacturing problems but may not know how to describe them technically.

Your goal is to:
1. Make the person feel welcome and understood
2. Ask simple, friendly questions to understand their problem
3. Explain in plain language how MMRI can help them
4. End by summarizing their problem and suggesting next steps

CONVERSATION FLOW:
- Start by warmly greeting them and asking what kind of manufacturing challenge they are facing
- Ask one question at a time in plain, friendly language
- Never use technical jargon like "FMEA", "data acquisition", "assets", "OEE" etc.
- If they use technical terms, that is fine — but always respond in simple language
- After 4-5 questions, summarize what you have learned and explain how MMRI can help

QUESTIONS TO ASK (in plain language, one at a time):
1. "What kind of equipment or process is giving you trouble?"
2. "What actually happens when things go wrong — does it break down, slow down, make bad parts?"
3. "How do you usually find out something is wrong — does someone notice, does an alarm go off, or do you only find out after the fact?"
4. "How often does this happen, and how much does it affect your production?"
5. "Have you tried anything to fix it so far?"

AFTER COLLECTING INFO:
- Summarize what they told you in simple terms
- Explain which MMRI capability can help in plain language
- Tell them the next step is to connect with the MMRI team and offer to help set that up

MMRI BACKGROUND INFO:
{mmri_content}

CONDITION MONITORING CAPABILITIES:
- MMRI can figure out which sensors to put on equipment to detect problems early
- MMRI can analyze data from machines to spot patterns before failures happen
- MMRI tests equipment in the lab first before deploying on the production floor
- MMRI can monitor robots, CNC machines, motors, gearboxes, and many other types of equipment
- MMRI builds dashboards and alerts so teams can see what is happening in real time

ABOUT MMRI:
- Located at 230 Longwood Road South, Hamilton, Ontario (McMaster Innovation Park)
- 21,000 sq ft facility with 7 research labs
- Phone: 905-525-9140, Email: mmri-ad@mcmaster.ca
- Hours: Monday-Friday 8:30am-4:30pm

CONVERSATION ENDINGS:
After the person has answered 4-5 questions, wrap up like this:
1. Say "Here's what I'll pass along to the MMRI team:" and summarize in 3-4 bullet points
2. Explain in 1-2 sentences which MMRI capability can help
3. Ask: "Would you like me to help set up a meeting with our team?"
4. If yes, ask for their name, company name, and email address
5. Once you have their name, company, and email — end your message with this exact tag on its own line: [READY_FOR_SCOPING]

If someone asks something you do not know, tell them you will connect them with the MMRI team and direct them to mmri-ad@mcmaster.ca."""

# Initialize session state
if "conversation" not in st.session_state:
    st.session_state.conversation = []
    st.session_state.client_info = {}
    st.session_state.ready_for_scoping = False
    opening_message = "Hi there! 👋 I'm the MMRI Assistant at McMaster Manufacturing Research Institute. I'm here to help figure out how our team can help with your manufacturing challenges.\n\nTo get started — what kind of manufacturing problem are you dealing with?"
    st.session_state.conversation.append({
        "role": "assistant",
        "content": opening_message
    })

for message in st.session_state.conversation:
    with st.chat_message(message["role"]):
        st.write(message["content"].replace("[READY_FOR_SCOPING]", ""))

user_input = st.chat_input("Ask a question about MMRI...")

if "starter" in st.session_state and st.session_state.starter:
    user_input = st.session_state.starter
    st.session_state.starter = None
    st.rerun()

if user_input:
    st.session_state.conversation.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_placeholder.write("MMRI Assistant is thinking... 🔬")
        full_response = ""

        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=st.session_state.conversation
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                response_placeholder.write(full_response.replace("[READY_FOR_SCOPING]", "") + "▌")
            response_placeholder.write(full_response.replace("[READY_FOR_SCOPING]", ""))

    st.session_state.conversation.append({
        "role": "assistant",
        "content": full_response
    })

    # Check if ready for scoping
    if "[READY_FOR_SCOPING]" in full_response:
        st.session_state.ready_for_scoping = True
        # Save full conversation summary for scoping agent
        st.session_state.client_info["conversation_summary"] = "\n".join([
            f"{m['role'].upper()}: {m['content']}"
            for m in st.session_state.conversation
        ])

# Show handoff button when ready
if st.session_state.get("ready_for_scoping"):
    st.markdown("""
        <div class="handoff-box">
            <h3>✅ Ready for Next Step!</h3>
            <p>Your information has been collected. Click below to move to the Scoping Agent who will draft a project document for the MMRI team.</p>
        </div>
    """, unsafe_allow_html=True)
    if st.button("➡️ Continue to Scoping Agent"):
        st.switch_page("pages/2_Scoping_Agent.py")

st.markdown("""
    <div class="footer">
        McMaster Manufacturing Research Institute · 230 Longwood Rd S, Hamilton ON · 905-525-9140
    </div>
""", unsafe_allow_html=True)