import asyncio
import time
import os
import threading
import multiprocessing
import vertexai
from vertexai.generative_models import GenerativeModel

# Initialize
vertexai.init(project="project-6e5874e2-a053-4fd2-ba2", location="asia-southeast1")

# Use Flash for ALL agents during testing for maximum speed
notes_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")
ppt_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")
video_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")

# =====================================================================
# 1. FALSE PARALLELIZATION (CONCURRENCY VIA ASYNCIO - SINGLE CORE)
# =====================================================================

async def track_time(agent_name, agent, prompt):
    pid = os.getpid()
    thread_name = threading.current_thread().name
    
    start = time.time()
    print(f"[{agent_name}] Started on PID: {pid} | Thread: {thread_name}")
    
    response = await agent.generate_content_async(prompt)
    
    elapsed = time.time() - start
    print(f"[{agent_name}] Finished in {elapsed:.2f} seconds (PID: {pid})")
    return {"type": agent_name, "content": response.text}

async def parallel_coordinator(user_request: str):
    print("Running all agents simultaneously (Asyncio)...\n")
    script_start = time.time()
    
    results = await asyncio.gather(
        track_time("Notes", notes_agent, user_request),
        track_time("PPT", ppt_agent, user_request),
        track_time("Video", video_agent, user_request)
    )
    
    total_time = time.time() - script_start
    print(f"\nAll tasks completed. Total Script Time: {total_time:.2f} seconds\n")
    return results


# =====================================================================
# 2. TRUE PARALLELIZATION (MULTIPROCESSING - MULTIPLE CORES)
# =====================================================================

# This function must be a top-level function so Windows can pickle it across CPU cores
def sync_worker(args):
    agent_name, prompt = args
    pid = os.getpid()
    thread_name = threading.current_thread().name
    
    start = time.time()
    print(f"[{agent_name}] Started on PID: {pid} | Thread: {thread_name}")
    
    # Select the global agent
    if agent_name == "Notes":
        agent = notes_agent
    elif agent_name == "PPT":
        agent = ppt_agent
    else:
        agent = video_agent
        
    # Uses the synchronous generation method 
    response = agent.generate_content(prompt)
    
    elapsed = time.time() - start
    print(f"[{agent_name}] Finished in {elapsed:.2f} seconds (PID: {pid})")
    return {"type": agent_name, "content": response.text}

def true_parallel_coordinator(user_request: str):
    print("Running all agents simultaneously (Multiprocessing)...\n")
    script_start = time.time()
    
    tasks = [
        ("Notes", user_request),
        ("PPT", user_request),
        ("Video", user_request)
    ]
    
    # Create a pool of 3 separate CPU processes
    with multiprocessing.Pool(processes=3) as pool:
        # pool.map distributes the tasks across the different cores
        results = pool.map(sync_worker, tasks)
        
    total_time = time.time() - script_start
    print(f"\nAll tasks completed. Total Script Time: {total_time:.2f} seconds\n")
    return results



if __name__ == "__main__":
    prompt = "The impact of quantum computing on modern cryptography."
    
    # print("--- STARTING ASYNC TEST ---")
    asyncio.run(parallel_coordinator(prompt))
    
    # =====================================================================
    # OPTIONAL: Uncomment to test multiprocessing.
    # =====================================================================
    print("\n--- STARTING MULTIPROCESSING TEST ---")
    true_parallel_coordinator(prompt)