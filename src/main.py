from agents.specialist_agent import NotesAgent, FlashcardAgent, VideoAgent
import os
from dotenv import load_dotenv

load_dotenv()
anthropic_key = os.getenv("CLAUDE_API_KEY")

if not anthropic_key:
    print("Error: CLAUDE_API_KEY not found. Check your .env file!")

def run_test_workflow():
    topic = "Explain dynamic programming approaches, buttom up and top down, and the examples such as knapscak, common longest sequence."

    notes_agent = NotesAgent(api_key=anthropic_key)
    flashcard_agent = FlashcardAgent(api_key=anthropic_key)
    video_agent = VideoAgent()

    print("\n--- Starting Workflow ---\n")

    notes_agent.run(topic)
    flashcard_agent.run(topic)

    narrations = [f"Question: {q} Answer: {a}" for q, a in flashcard_agent.pairs]
    video_agent.run(flashcard_agent.pairs, narrations)

    print("\n--- Workflow Complete ---")

if __name__ == "__main__":
    run_test_workflow()
