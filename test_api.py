import os
from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import system, user

load_dotenv()

api_key = os.getenv("XAI_API_KEY")
if not api_key:
    print("❌ ERROR: XAI_API_KEY not found in .env file!")
    exit()

print("🔍 Testing xAI Grok API connection...")

client = Client(api_key=api_key)

chat = client.chat.create(model="grok-4-1-fast-reasoning")
chat.append(system("You are a helpful assistant."))
chat.append(user("Hi! Please just reply with 'Hello from Grok API! I'm working perfectly.'"))

response = chat.sample()   # ← This is the correct method

print("\n✅ SUCCESS! API is working.")
print("Response from Grok:")
print(response.content)