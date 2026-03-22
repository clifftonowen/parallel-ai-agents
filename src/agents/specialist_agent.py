from google.adk.agents import LlmAgent as Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
import os
from .base_agent import BaseAgent

# --- Notes Specialist ---
class NotesAgent(BaseAgent):
    def __init__(self):
        super().__init__(mode_type="Notes", output_folder="notes")
        self.ai = Agent(model='gemini-2.0-flash', name="Notes_Specialist")

    def execute(self, input_data: str):
        print(f"[{self.mode_type}] Generating structured notes...")
        prompt = f"Convert the following content into detailed academic study notes: {input_data}"
        
        content = self._get_ai_response(prompt)
        self.save_output(f"notes_{self.agent_id[:5]}.md", content)

# --- Flashcard Specialist ---
class FlashcardAgent(BaseAgent):
    def __init__(self):
        super().__init__(mode_type="Flashcard", output_folder="flashcards")
        self.ai = Agent(model='gemini-2.0-flash', name="Flashcard_Specialist")

    def execute(self, input_data: str):
        print(f"[{self.mode_type}] Creating Q&A pairs...")
        prompt = f"Create a list of active recall flashcards (Question and Answer) based on: {input_data}"
        
        content = self._get_ai_response(prompt)
        self.save_output(f"flashcards_{self.agent_id[:5]}.txt", content)


# --- Video Specialist ---
class VideoAgent(BaseAgent):
    def __init__(self):
        super().__init__(mode_type="Video", output_folder="videos")
        self.ai = Agent(model='gemini-2.0-flash', name="Video_Specialist")

    def execute(self, input_data: str):
        print(f"[{self.mode_type}] Scripting video content...")
        prompt = f"Create a 60-second video script and visual prompts for the topic: {input_data}"
        
        content = self._get_ai_response(prompt)
        self.save_output(f"video_script_{self.agent_id[:5]}.md", content)