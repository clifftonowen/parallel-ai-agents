import asyncio
import time
import vertexai
from vertexai.generative_models import GenerativeModel

# Initialize
vertexai.init(project="project-6e5874e2-a053-4fd2-ba2", location="us-central1")

# Use Flash for ALL agents during testing for maximum speed
notes_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")
ppt_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")
video_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")

async def track_time(agent_name, agent, prompt):
    start = time.time()
    print(f"[{agent_name}] Started...")
    
    response = await agent.generate_content_async(prompt)
    
    elapsed = time.time() - start
    print(f"[{agent_name}] Finished in {elapsed:.2f} seconds!")
    return {"type": agent_name, "content": response.text}

async def parallel_coordinator(user_request: str):
    print("Running all agents simultaneously...\n")
    script_start = time.time()
    
    results = await asyncio.gather(
        track_time("Notes", notes_agent, user_request),
        track_time("PPT", ppt_agent, user_request),
        track_time("Video", video_agent, user_request)
    )
    
    total_time = time.time() - script_start
    print(f"\nAll tasks completed. Total Script Time: {total_time:.2f} seconds\n")
    return results

if __name__ == "__main__":
    asyncio.run(parallel_coordinator("The impact of quantum computing on modern cryptography."))