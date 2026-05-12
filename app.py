import os
import anthropic
import streamlit as st

import requests
from bs4 import BeautifulSoup

def scrape_mmri_page(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        # Remove scripts and styles
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        text = soup.get_text(separator=' ', strip=True)
        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return ' '.join(lines)[:3000]  # Limit to 3000 chars per page
    except:
        return ""

# Scrape MMRI pages on startup
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

client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

# Page config
st.set_page_config(
    page_title="MPAL Lab Assistant",
    page_icon="🔬",
    layout="centered"
)

# McMaster branding CSS
st.markdown("""
    <style>
        /* Background */
        .stApp {
            background-color: #1a1a1a;
        }
        
        /* Header bar */
        .header {
            background-color: #7A003C;
            padding: 20px 30px;
            border-radius: 12px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .header h1 {
            color: #FDBF57;
            font-size: 24px;
            margin: 0;
            font-family: 'Georgia', serif;
        }
        .header p {
            color: #ffffff;
            margin: 0;
            font-size: 13px;
            opacity: 0.85;
        }

        /* Chat messages */
        .stChatMessage {
            background-color: #2a2a2a;
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 8px;
        }

        /* Input box */
        .stChatInputContainer {
            border-top: 2px solid #7A003C;
            padding-top: 10px;
        }

        /* Suggestion buttons */
        .stButton > button {
            background-color: #2a2a2a;
            color: #FDBF57;
            border: 1px solid #7A003C;
            border-radius: 20px;
            padding: 6px 16px;
            font-size: 13px;
            transition: all 0.2s;
        }
        .stButton > button:hover {
            background-color: #7A003C;
            color: white;
        }

        /* Footer */
        .footer {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="header">
        <div>
            <h1>🔬 MPAL Lab Assistant</h1>
            <p>McMaster Manufacturing Research Institute · Ask me anything about the lab</p>
        </div>
    </div>
""", unsafe_allow_html=True)

# System prompt
SYSTEM_PROMPT = f"""You are a helpful assistant for the Materials Property Assessment Lab (MPAL) 
at the McMaster Manufacturing Research Institute (MMRI). Answer questions accurately based on the following information:

{mmri_content}

If asked something not covered here, say you'll check with the lab team and direct them to contact MMRI directly.
ABOUT THE MMRI:
- Full name: McMaster Manufacturing Research Institute (MMRI)
- Located at: 230 Longwood Road South, Hamilton, Ontario, Canada, L8P 0A6 (McMaster Innovation Park)
- New facility opened in 2023 at McMaster Innovation Park
- 21,000 sq. ft. facility with 7 research labs
- 20+ years of experience in teaching, research and industrial activities
- Part of the Ontario Advanced Manufacturing Consortium (OAMC) with University of Waterloo and Western University
- Phone: 905-525-9140, Hours: Monday-Friday 8:30am-4:30pm

MMRI'S FOCUS:
- Develop intelligent solutions to issues faced by Canada's manufacturers in all steps of machining processes
- Partners with industry to solve complex mechanical engineering and manufacturing challenges
- Expertise spans: additive manufacturing, advanced manufacturing processes, and materials testing
- Team includes: professional engineers, machinists, researchers, and students
- Services range from rapid prototyping to process optimization and long-term technology development

TECHNOLOGY TRANSFER SERVICES:
- Tooling selection: helps choose correct tools using material, process and tooling information
- Tool path development: uses MACHpro software for 5-axis process simulation and NC program optimization
- Process parameters: uses CUTPRO software to optimize feeds and speeds
- Process monitoring: uses MMRI-Monitoring software to track production in real time
- Technology transfer: translates research outcomes into implementable industry solutions

INDUSTRY SECTORS SERVED:
- Automotive and aerospace
- Energy and infrastructure
- Advanced manufacturing
- Metals, alloys, and advanced materials development
- Healthcare

STUDY & TRAINING:
- Graduate-level degrees in manufacturing engineering
- MMRI Industrial Training Program for career advancement
- Students work directly on real industry problems

If asked something not covered here, say you'll check with the lab team and direct them to contact MMRI directly."""

# Initialize conversation
if "conversation" not in st.session_state:
    st.session_state.conversation = []

# Suggestion buttons (only show if no conversation yet)
if not st.session_state.conversation:
    st.markdown("**💡 Try asking:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("What does MPAL do?"):
            st.session_state.starter = "What does MPAL do?"
    with col2:
        if st.button("Where is MMRI located?"):
            st.session_state.starter = "Where is MMRI located?"
    with col3:
        if st.button("What industries do you work with?"):
            st.session_state.starter = "What industries do you work with?"

# Display conversation
for message in st.session_state.conversation:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Always show chat input
user_input = st.chat_input("Ask a question about MPAL or MMRI...")

# Handle starter button clicks
if not user_input and "starter" in st.session_state and st.session_state.starter:
    user_input = st.session_state.starter
    st.session_state.starter = None

# Process input
# Process input
if user_input:
    st.session_state.conversation.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=st.session_state.conversation
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                response_placeholder.write(full_response + "▌")
            response_placeholder.write(full_response)

    st.session_state.conversation.append({
        "role": "assistant",
        "content": full_response
    })

# Footer
st.markdown("""
    <div class="footer">
        McMaster Manufacturing Research Institute · 230 Longwood Rd S, Hamilton ON · 905-525-9140
    </div>
""", unsafe_allow_html=True)
