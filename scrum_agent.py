import streamlit as st
import anthropic
import json
import xlwings as xw
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

@st.cache_resource
def get_client():
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

client = get_client()

EMPLOYEE_FILES = {
    "brady semple": "C:/Users/laiba/Downloads/MpalChatbot/Project Tracker - Brady Semple.xlsm",
    "kristin bennett": "C:/Users/laiba/Downloads/MpalChatbot/Project Tracker - Kristin BennettV3testing.xlsm",
}

VALID_PROJECT_CODES = [
    "MCS1","INCORPAI1","TYCOS12","HONDA30", "HONDA58", "ORF0", "vAMC1", "HONDA79", "ENEDYM1", "HONDA75", "HONDA76",
    "HONDA86", "HONDA53", "HONDA89", "vRSC11", "vRSC12", "vRSC13", "HONDA98",
    "HONDA78", "LONGAN2", "HONDA103", "ALCHEMY5", "HONDACBM1", "QUICKMILL2",
    "COLLINS1", "HONDA130", "AXYZ3", "MEVOTECH5", "GASTRO2", "HONDACBM6",
    "HONDA119", "RACER2", "TUPY1", "SMARTCN1", "OLIGO3", "MHI1", "HONDA122",
    "HONDA123", "ABERGER3"
]

st.set_page_config(page_title="MMRI Scrum Agent", page_icon="🤖", layout="wide")

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
        .stButton > button:hover {
            background-color: #7A003C;
            color: white;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="header">
        <h1>🤖 MMRI Daily Scrum Agent</h1>
        <p>McMaster Manufacturing Research Institute · Your 2-minute daily project update assistant</p>
    </div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 👥 Employees")
    st.markdown("""
    - Brady Semple
    - Kristin Bennett
    - Darren Feenstra
    - Kevin
    - Patrick Chin
    - Mahdi
    - Steve
    """)
    st.markdown("---")
    st.markdown("### 📋 Instructions")
    st.markdown("""
    1. Click **Start Daily Scrum**
    2. Answer the agent's questions
    3. Click **Export to Excel** when done
    """)
    st.markdown("---")
    st.markdown("### ⏱️ Takes about 2 minutes")
    st.markdown("---")
    if st.button("🗑️ Clear Chat"):
        st.session_state.conversation = []
        st.session_state.started = False
        st.session_state.updates_ready = False
        st.rerun()

if "conversation" not in st.session_state:
    st.session_state.conversation = []
    st.session_state.updates = {}
    st.session_state.started = False
    st.session_state.updates_ready = False

SCRUM_STEPS = ["Name", "Project Type", "Project Details", "Blockers", "Complete"]

def get_progress(conversation):
    if not conversation:
        return 0
    msg_count = len([m for m in conversation if m["role"] == "user"])
    return min(msg_count / 5, 1.0)

progress = get_progress(st.session_state.conversation)
step_index = min(int(progress * len(SCRUM_STEPS)), len(SCRUM_STEPS) - 1)
st.markdown(f"**Scrum Progress:** {SCRUM_STEPS[step_index]}")
st.progress(progress)

SYSTEM_PROMPT = f"""You are a friendly scrum agent for the MMRI lab at McMaster University. 
Your job is to conduct a quick 2-minute daily standup with each employee.

Ask these questions one at a time in a friendly conversational way:
1. What is your name?
2. Are you updating an existing project or adding a new project?

If UPDATING an existing project, ask:
- Which project code? (refer to the valid project codes list below)
- What is your current % complete?
- How many hours did you spend on it today?
- What is the status? Give them these exact options to choose from:
  Complete, In Progress, Delay, Future Work
- Any blockers or risks?

If adding a NEW project, ask:
- Project code? (refer to the valid project codes list below)
- Task name?
- Start date?
- End date?
- Estimated hours?
- Current status? Give them these exact options:
  Complete, In Progress, Delay, Future Work
- Current % complete?
- Hours complete so far?
- Priority? Give them these exact options:
  High, Medium, Low
- Any blockers or risks?

After each project ask "Any other projects to update or add?"
Once done with all projects say UPDATES_COMPLETE.

VALID PROJECT CODES (match employee input to one of these):
{", ".join(VALID_PROJECT_CODES)}

If an employee mentions a project that doesn't match a code, ask them to confirm which code it corresponds to.

Be friendly, concise and professional. Keep responses short.

Once you know the employee's name, use it naturally throughout the conversation to make it feel personal. For example "Great, thanks Brady!" or "Got it Kristin, what's the status?".

Be friendly, concise and professional. Keep responses short.

If an employee says they worked more than 12 hours on a project in one day, flag it and ask them to confirm. For example "Just to confirm, you worked 15 hours on that today? That seems like a lot — can you double check that number?".

Be friendly, concise and professional. Keep responses short."""

for message in st.session_state.conversation:
    with st.chat_message(message["role"]):
        st.write(message["content"])

if not st.session_state.started:
    employee = st.selectbox("Select your name:", [
        "", "Brady Semple", "Kristin Bennett", "Darren Feenstra",
        "Kevin", "Patrick Chin", "Mahdi", "Steve"
    ])
    if st.button("▶️ Start Daily Scrum", key="start_button"):
        if employee:
            st.session_state.started = True
            st.session_state.employee_name = employee
            opening = f"Hi {employee}! 👋 I'm your MMRI Scrum Agent. I'll help you log your daily project updates in about 2 minutes. Let's get started!\n\nAre you updating an existing project or adding a new one?"
            st.session_state.conversation.append({"role": "assistant", "content": opening})
            st.rerun()
        else:
            st.warning("Please select your name before starting!")
            
if st.session_state.started:
    user_input = st.chat_input("Type your response here...")
else:
    user_input = None

if user_input and st.session_state.started:
    st.session_state.conversation.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_placeholder.write("Agent is processing... 🤖")
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=st.session_state.conversation
        )
        assistant_message = response.content[0].text
        response_placeholder.write(assistant_message)

    st.session_state.conversation.append({"role": "assistant", "content": assistant_message})

    if "UPDATES_COMPLETE" in assistant_message:
        st.session_state.updates_ready = True

if st.session_state.get("updates_ready"):
    st.success("✅ Updates collected! Ready to export to Excel.")

    st.markdown("### 📋 Session Summary")
    for msg in st.session_state.conversation:
        if msg["role"] == "user":
            st.markdown(f"**You:** {msg['content']}")
        else:
            if "UPDATES_COMPLETE" not in msg["content"]:
                st.markdown(f"**Agent:** {msg['content']}")

    if st.button("📤 Export to Excel"):
        with st.spinner("Extracting and exporting..."):
            extraction_response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": f"""Based on this scrum conversation, extract the project updates in JSON format:
                    
{str(st.session_state.conversation)}

Return ONLY a JSON object like this, no other text:
{{
    "employee_name": "name here",
    "updates": [
        {{
            "type": "update",
            "project_code": "code",
            "status": "In Progress",
            "percent_complete": 50,
            "hours_today": 2,
            "blockers": "any blockers or none"
        }}
    ],
    "new_projects": [
        {{
            "type": "new",
            "project_code": "code",
            "task": "task name",
            "start_date": "DD/MM/YYYY",
            "end_date": "DD/MM/YYYY",
            "estimated_hours": 100,
            "status": "In Progress",
            "percent_complete": 0,
            "hours_complete": 0,
            "priority": "High",
            "blockers": "any blockers or none"
        }}
    ]
}}

STRICT RULES:
- status must be EXACTLY one of: Complete, In Progress, Delay, Future Work
- priority must be EXACTLY one of: High, Medium, Low
- project_code must match one of the valid codes from the conversation
- Do not use any other values for these fields
- Do not include any markdown or extra text, just the JSON"""
                }]
            )

            try:
                raw_text = extraction_response.content[0].text
                clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_text)
                st.success("✅ Updates extracted!")
                st.json(data)

                employee_name = data["employee_name"].lower()
                file_path = EMPLOYEE_FILES.get(employee_name)

                if not file_path:
                    st.error(f"No Excel file found for {data['employee_name']}. Make sure the name matches exactly.")
                else:
                    wb = xw.Book(file_path)
                    ws = wb.sheets["ProjectTracker"]

                    exported = []
                    failed = []

                    for update in data.get("updates", []):
                        found = False
                        for row in range(14, 200):
                            if ws.cells(row, 3).value == update["project_code"]:
                                ws.cells(row, 9).api.Validation.Delete()
                                ws.cells(row, 9).value = update["status"]
                                ws.cells(row, 10).value = update["percent_complete"] / 100
                                current_hours = ws.cells(row, 11).value or 0
                                ws.cells(row, 11).value = current_hours + update["hours_today"]
                                if update["blockers"] and update["blockers"].lower() != "none":
                                    ws.cells(row, 14).value = update["blockers"]
                                ws.cells(row, 15).value = datetime.today().strftime('%Y-%m-%d')
                                exported.append(update["project_code"])
                                found = True
                                break
                        if not found:
                            failed.append(update["project_code"])

                    for new_proj in data.get("new_projects", []):
                        for row in range(14, 200):
                            if ws.cells(row, 3).value is None:
                                ws.cells(row, 3).value = new_proj["project_code"]
                                ws.cells(row, 4).value = new_proj["task"]
                                ws.cells(row, 6).value = new_proj["start_date"]
                                ws.cells(row, 7).value = new_proj["end_date"]
                                ws.cells(row, 8).value = new_proj["estimated_hours"]
                                ws.cells(row, 9).api.Validation.Delete()
                                ws.cells(row, 9).value = new_proj["status"]
                                ws.cells(row, 10).value = new_proj["percent_complete"] / 100
                                ws.cells(row, 11).value = new_proj["hours_complete"]
                                ws.cells(row, 13).api.Validation.Delete()
                                ws.cells(row, 13).value = new_proj["priority"]
                                ws.cells(row, 14).value = new_proj["blockers"] if new_proj["blockers"].lower() != "none" else ""
                                ws.cells(row, 15).value = "'" + datetime.today().strftime('%d/%m/%Y')
                                exported.append(new_proj["project_code"])
                                break

                    wb.save()

                    if exported:
                        st.success(f"✅ Successfully exported: {', '.join(exported)}")
                    if failed:
                        st.error(f"❌ Could not find these project codes in Excel: {', '.join(failed)}")

                    st.balloons()
                    import time
                    time.sleep(3)
                    st.session_state.conversation = []
                    st.session_state.started = False
                    st.session_state.updates_ready = False
                    st.rerun()

            except json.JSONDecodeError:
                st.error("Could not parse the extracted data. Please try exporting again.")
            except Exception as e:
                st.error(f"Could not update Excel file: {e}")