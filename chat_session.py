import os

import vertexai
from dotenv import load_dotenv
from vertexai.generative_models import GenerativeModel

load_dotenv()

GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCP_LOCATION = os.environ["GCP_LOCATION"]

vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)

model = GenerativeModel("gemini-2.5-flash")

#  Google's Default
print("--- Stateful ChatSession ---")
chat = model.start_chat() # Creates a ChatSession object

resp1 = chat.send_message("Hi, my name is Cliffton.")
print(resp1.text)

resp2 = chat.send_message("What is my name?")
print(resp2.text) # object holds self.history

# For Rust Migration, we use Stateless Execution
print("\n--- Stateless Execution ---")
# Instead of an object holding memory, we pass the memory manually.
history_db = [
    {"role": "user", "parts": [{"text": "Hi, my name is Cliffton."}]},
    {"role": "model", "parts": [{"text": "Hello Cliffton!"}]}
]

# We use generate_content instead of start_chat
resp3 = model.generate_content(
    contents=history_db + [{"role": "user", "parts": [{"text": "What is my name?"}]}]
)
print(resp3.text) 