import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
from dotenv import load_dotenv
import base64

load_dotenv()

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

TEAM_DESCRIPTIONS = {
    "MSL": "The Materials Science Lab (MSL) specializes in material characterization, property assessment, product development, and materials testing. Led by Brady, Kevin, and Steve.",
    "CBM": "The Condition-Based Monitoring (CBM) team specializes in monitoring equipment health, predictive maintenance, and performance assessment of industrial equipment. Led by Patrick and Kristin.",
    "MPAL": "The Manufacturing Process Analysis Lab (MPAL) specializes in advanced manufacturing processes, machining, CNC operations, tooling, process optimization, and condition monitoring. Led by Darren and Mahdi."
}

SYSTEM_PROMPT = f"""You are an expert assistant for the McMaster Manufacturing Research Institute (MMRI). 
Your job is to read uploaded documents from industry partners and:
1. Summarize what problem or need the partner has in plain language
2. Match them to the most relevant MMRI sub-team based on their problem
3. Explain why that team is the best fit
4. Suggest clear next steps

Here are the MMRI sub-teams and what they do:

MSL: {TEAM_DESCRIPTIONS['MSL']}
CBM: {TEAM_DESCRIPTIONS['CBM']}
MPAL: {TEAM_DESCRIPTIONS['MPAL']}

At the end of your response, always include team matches on their own lines in exactly this format:
MATCH: [team name] | CONFIDENCE: [percentage]%
If multiple teams are relevant, include one line per team, ordered by confidence. For example:
MATCH: MPAL | CONFIDENCE: 87%
MATCH: CBM | CONFIDENCE: 45%

After the team matches, always ask 1-2 follow-up questions to better understand the partner's needs. Format them like this:
FOLLOWUP: [your question here]
For example:
FOLLOWUP: How urgently do you need this resolved?
FOLLOWUP: Have you worked with a research institute before?"""

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    messages = data.get('messages', [])
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages
    )
    
    return jsonify({'response': response.content[0].text})

@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    pdf_data = base64.standard_b64encode(file.read()).decode('utf-8')
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
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

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    app.run(debug=True, port=5000)