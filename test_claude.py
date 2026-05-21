import anthropic

client = anthropic.Anthropic(api_key="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")

conversation = []

print("MPAL Lab Chatbot - type 'quit' to exit")
print("----------------------------------------")

while True:
    user_input = input("You: ")
    
    if user_input.lower() == "quit":
        print("Goodbye!")
        break
    
    conversation.append({
        "role": "user",
        "content": user_input
    })
    
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system="You are a helpful assistant for the Materials Property Assessment Lab (MPAL) at McMaster University. You help lab members and visitors with questions about the lab, its research, equipment, and workflows.",
        messages=conversation
    )
    
    assistant_message = response.content[0].text
    
    conversation.append({
        "role": "assistant",
        "content": assistant_message
    })
    
    print(f"\nMPAL Bot: {assistant_message}\n")