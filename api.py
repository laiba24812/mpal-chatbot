import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are a friendly assistant for the McMaster Manufacturing Research Institute (MMRI). Your job is to help people from industry who have manufacturing problems but may not know how to describe them technically.

Your goal is to:
1. Make the person feel welcome and understood
2. Ask simple, friendly questions to understand their problem
3. Explain in plain language how MMRI can help them
4. End by summarizing their problem and suggesting next steps

CONVERSATION FLOW:
- Start by warmly greeting them and asking what kind of manufacturing challenge they are facing
- Ask one question at a time in plain, friendly language
- Never use technical jargon
- After 4-5 questions, summarize what you have learned and explain how MMRI can help

ABOUT MMRI:
- Located at 230 Longwood Road South, Hamilton, Ontario (McMaster Innovation Park)
- 21,000 sq ft facility with 7 research labs
- Phone: 905-525-9140, Email: mmri-ad@mcmaster.ca
- Hours: Monday-Friday 8:30am-4:30pm
- Expertise: advanced manufacturing, condition monitoring, materials testing, prototyping, process optimization"""

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
    
    return jsonify({
        'response': response.content[0].text
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)