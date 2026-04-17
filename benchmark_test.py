import asyncio
import time
import multiprocessing

# =====================================================================
# CONFIGURATION
# =====================================================================
NUM_AGENTS = 20
SIMULATED_API_DELAY = 2.0  # Simulate waiting 2 seconds for Vertex AI

# =====================================================================
# 1. ASYNCIO (FALSE PARALLELIZATION)
# =====================================================================
async def async_worker(agent_id):
    # Simulate I/O network wait without blocking the CPU
    await asyncio.sleep(SIMULATED_API_DELAY)
    return f"Agent {agent_id} done"

async def run_async_test():
    print(f"--- Starting ASYNCIO Test ({NUM_AGENTS} simulated agents) ---")
    start_time = time.time()
    
    tasks = [async_worker(i) for i in range(NUM_AGENTS)]
    await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    print(f"Asyncio Total Time: {total_time:.4f} seconds\n")


# =====================================================================
# 2. MULTIPROCESSING (TRUE PARALLELIZATION)
# =====================================================================
def sync_worker(agent_id):
    # Simulate a blocking network call 
    time.sleep(SIMULATED_API_DELAY)
    return f"Agent {agent_id} done"

def run_multiprocessing_test():
    print(f"--- Starting MULTIPROCESSING Test ({NUM_AGENTS} simulated agents) ---")
    start_time = time.time()
    
    # We will let the Pool decide how to distribute the 20 tasks across available cores
    with multiprocessing.Pool() as pool:
        pool.map(sync_worker, range(NUM_AGENTS))
        
    total_time = time.time() - start_time
    print(f"Multiprocessing Total Time: {total_time:.4f} seconds\n")


# =====================================================================
# EXECUTION
# =====================================================================
if __name__ == "__main__":
    # Run Asyncio
     asyncio.run(run_async_test())
    # Run Multiprocessing
     run_multiprocessing_test()
    