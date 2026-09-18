import os
import subprocess
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from .graph_state import AgentState

# CCR Endpoint Configuration
CCR_BASE_URL = "http://127.0.0.1:3456"
# Fake API key since CCR usually routes locally without checking it (or uses env vars)
CCR_API_KEY = os.getenv("CCR_API_KEY", "sk-ccr-local")

# Local Kimi-K3-in-C Configuration
K3_BIN_PATH = os.path.expanduser("~/kimi-k3-in-c/bin/k3")
K3_MODEL_DIR = os.path.expanduser("~/k3model")
K3_TRUNK_DIR = os.path.expanduser("~/k3trunk")
K3_PRESET = os.getenv("K3_PRESET", "laptop") # Default to laptop due to RAM constraint

# Helper function to get an LLM instance connected to CCR aliases
def get_ccr_llm(alias: str):
    return ChatOpenAI(
        model=alias,
        base_url=CCR_BASE_URL,
        api_key=CCR_API_KEY,
        # max_retries ensures we rely on CCR's built-in model-chain fallbacks
        max_retries=1 
    )

def call_local_kimi_k3(messages) -> str:
    """Executes the local kimi-k3-in-c binary via subprocess."""
    if not os.path.exists(K3_BIN_PATH):
        raise FileNotFoundError(f"Local Kimi K3 binary not found at {K3_BIN_PATH}")
    if not os.path.exists(K3_MODEL_DIR):
        raise FileNotFoundError(f"Model directory not found at {K3_MODEL_DIR}")
        
    # Format messages into a single prompt string
    prompt_text = ""
    for msg in messages:
        role = "System" if isinstance(msg, SystemMessage) else "User" if isinstance(msg, HumanMessage) else "Assistant"
        prompt_text += f"{role}: {msg.content}\n"
        
    # Build command according to kimi-k3-in-c README
    cmd = [
        K3_BIN_PATH, K3_MODEL_DIR,
        "--trunk", K3_TRUNK_DIR,
        "--preset", K3_PRESET,
        "--tok", K3_MODEL_DIR,
        "--prompt", prompt_text,
        "--gen", "512", # Max tokens to generate
        "--incremental"
    ]
    
    # Run subprocess
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    
    if result.returncode != 0:
        raise RuntimeError(f"Local Kimi K3 execution failed: {result.stderr}")
        
    # Extract the generated text from stdout
    stdout = result.stdout
    try:
        content = stdout.split("--- generated text ---")[1].split("----------------------")[0].strip()
        return content
    except IndexError:
        # Fallback if output format is unexpected
        return stdout

def supervisor_node(state: AgentState):
    """
    Supervisor Agent uses the 'fable' orchestrator model.
    Follows Fable Orchestrator methodology: plans, creates dependency-aware task graphs,
    and adjudicates only; never executes domain implementation directly.
    """
    messages = state.get("messages", [])
    
    # Uses CCR 'fable' alias (mapped to Fable Orchestrator profile)
    llm = get_ccr_llm("fable")
    
    system_prompt = SystemMessage(content="""
    You are Claude Fable 5.1, the Supervisor and Orchestrator Agent of Marzneshin OS.
    Core Rule: You plan, orchestrate, and adjudicate only; you NEVER write implementation code.
    Analyze the current state and route the task to the appropriate worker agent:
    - 'Coder': For deep engineering reasoning, algorithm design, and code implementation (powered by Kimi K3).
    - 'Memory': For retrieving prior context and architectural facts from agentmemory.
    - 'Reviewer': For fast quality gate verification and FSP protocol checking.
    - 'FINISH': If the task is fully completed, verified, and ready for integration.
    
    Reply ONLY with the exact name of the worker agent, or 'FINISH'.
    """)
    
    # Simple routing strategy for now
    response = llm.invoke([system_prompt] + messages)
    next_agent = response.content.strip().replace("'", "").replace('"', "")
    
    if next_agent not in ["Coder", "Memory", "Reviewer", "FINISH"]:
        next_agent = "FINISH" # Fail-closed approach if model hallucinates
        
    # Emit an FSP event for this decision
    event = {
        "actor": "supervisor",
        "action": "route_task",
        "target": next_agent,
        "ts": "now" # In real implementation, use marzneshin clock
    }
    
    return {"next_agent": next_agent, "fsp_events": [event]}

def coder_node(state: AgentState):
    """
    Coder Agent uses the 'reasoning' model (powered by Kimi K3 MoE inference).
    Applies deep step-by-step reasoning to write robust, verifiable code.
    First attempts local execution using the C engine, falls back to Cloud API (CCR).
    """
    messages = state.get("messages", [])
    sys_msg = SystemMessage(content="You are the Coder Agent powered by Kimi K3 deep reasoning. Write robust, surgical code adhering strictly to Marzneshin FSP specifications.")
    all_messages = [sys_msg] + messages
    
    try:
        # Step 1: Try Local Execution
        content = call_local_kimi_k3(all_messages)
        response = AIMessage(content=content)
        event = {"actor": "coder", "action": "generated_code", "backend": "local_c_engine"}
    except Exception as e:
        # Step 2: Fallback to Cloud (CCR/OpenRouter)
        print(f"[Coder] Local execution skipped/failed ({str(e)}). Falling back to CCR.")
        llm = get_ccr_llm("reasoning")
        response = llm.invoke(all_messages)
        event = {"actor": "coder", "action": "generated_code", "backend": "ccr_cloud"}
    
    return {"messages": [response], "fsp_events": [event]}

def reviewer_node(state: AgentState):
    """
    Reviewer Agent uses the 'fast' model (e.g., Gemini 3.5 Flash-Lite).
    """
    messages = state.get("messages", [])
    llm = get_ccr_llm("fast")
    
    sys_msg = SystemMessage(content="You are the Reviewer Agent. Check code for FSP protocol adherence.")
    
    response = llm.invoke([sys_msg] + messages)
    event = {"actor": "reviewer", "action": "reviewed_code"}
    
    return {"messages": [response], "fsp_events": [event]}

def memory_node(state: AgentState):
    """
    Memory Agent accesses agentmemory REST API for context retrieval.
    """
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
    from lib import agentmemory
    
    messages = state.get("messages", [])
    
    query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break
            
    if not query:
        query = "marzneshin"
        
    mem_resp = agentmemory.call_mcp_tool("memory_smart_search", {"query": query, "limit": 10})
    context = mem_resp if not mem_resp.startswith("AgentMemory error") else "No relevant memory found or error."
    
    event = {"actor": "memory", "action": "memory_search", "query": query}
    msg = AIMessage(content=f"I have searched the memory and updated the context.\nContext:\n{context}")
    
    return {"messages": [msg], "agent_memory": {"context": context}, "fsp_events": [event]}
