import asyncio
import time
import os
import threading
import multiprocessing
import vertexai
from dotenv import load_dotenv
from vertexai.generative_models import GenerativeModel

load_dotenv()

GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCP_LOCATION = os.environ["GCP_LOCATION"]

vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)

notes_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")
ppt_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")
video_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")
quiz_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")
blog_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")
tweet_agent = GenerativeModel("gemini-2.5-flash", system_instruction="...")

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
    print("Running all 6 agents simultaneously (Asyncio)...\n")
    script_start = time.time()
    
    results = await asyncio.gather(
        track_time("Notes", notes_agent, user_request),
        track_time("PPT", ppt_agent, user_request),
        track_time("Video", video_agent, user_request),
        track_time("Quiz", quiz_agent, user_request),
        track_time("Blog", blog_agent, user_request),
        track_time("Tweet", tweet_agent, user_request)
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
    elif agent_name == "Video":
        agent = video_agent
    elif agent_name == "Quiz":
        agent = quiz_agent
    elif agent_name == "Blog":
        agent = blog_agent
    else:
        agent = tweet_agent
        
    # Uses the synchronous generation method 
    response = agent.generate_content(prompt)
    
    elapsed = time.time() - start
    print(f"[{agent_name}] Finished in {elapsed:.2f} seconds (PID: {pid})")
    return {"type": agent_name, "content": response.text}

def true_parallel_coordinator(user_request: str):
    print("Running all 6 agents simultaneously (Multiprocessing)...\n")
    script_start = time.time()
    
    tasks = [
        ("Notes", user_request),
        ("PPT", user_request),
        ("Video", user_request),
        ("Quiz", user_request),
        ("Blog", user_request),
        ("Tweet", user_request)
    ]
    
    # Create a pool of 6 separate CPU processes
    with multiprocessing.Pool(processes=6) as pool:
        # pool.map distributes the tasks across the different cores
        results = pool.map(sync_worker, tasks)
        
    total_time = time.time() - script_start
    print(f"\nAll tasks completed. Total Script Time: {total_time:.2f} seconds\n")
    return results


if __name__ == "__main__":
    prompt = "The impact of quantum computing on modern cryptography."
    
    print("--- STARTING ASYNC TEST ---")
    asyncio.run(parallel_coordinator(prompt))
    
    print("\n--- STARTING MULTIPROCESSING TEST ---")
    true_parallel_coordinator(prompt)