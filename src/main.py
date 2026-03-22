from agents.specialist_agent import NotesAgent, FlashcardAgent, VideoAgent
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Error: GOOGLE_API_KEY not found. Check your .env file!")

def run_test_workflow():
    test_input = "The concept of Big O notation in algorithm analysis."
    
    # 1. Instantiate the team
    agents = [NotesAgent(), FlashcardAgent(), VideoAgent()]
    
    print("\n--- Starting Multimodal Workflow ---\n")
    
    # 2. Loop through agents and execute
    for agent in agents:
        try:
            agent.execute(test_input)
        except Exception as e:
            print(f"Error in {agent.mode_type} execution: {e}")

    print("\n--- Workflow Complete. Check the 'output/' folders! ---")

if __name__ == "__main__":
    run_test_workflow()