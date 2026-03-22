import uuid
from abc import ABC
from google import genai  # Import the native client instead of ADK runners
import os

class BaseAgent(ABC):
    def __init__(self, mode_type: str, output_folder: str):
        self.mode_type = mode_type
        self.output_folder = output_folder
        self.agent_id = str(uuid.uuid4())
        
        # Initialize the standard client. 
        # It automatically finds GOOGLE_API_KEY in your .env file!
        self.client = genai.Client()
        
    def _get_ai_response(self, prompt: str):
        """Directly calls Gemini without the messy ADK session boilerplate."""
        try:
            # A clean, single-shot request to the model
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )
            return response.text
            
        except Exception as e:
            return f"Execution Error: {str(e)}"

    def save_output(self, filename: str, content: str):
        # 1. Get the absolute path of the project root (D:\Term 4\UROP\parallel-ai-agents)
        # This prevents files from getting lost in the .venv or src folders
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_path = os.path.join(base_dir, "output", self.output_folder)

        # 2. Ensure the directory exists
        os.makedirs(output_path, exist_ok=True)

        # 3. Define the full file path
        file_path = os.path.join(output_path, filename)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ [SUCCESS] {self.mode_type} saved to: {file_path}")
        except Exception as e:
            print(f"❌ [SAVE ERROR] Could not save {filename}: {e}")