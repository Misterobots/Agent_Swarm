from phi.agent import Agent, RunResponse
from architect_agent import get_architect_agent
from security_agent import get_security_agent

from metrics import AGENT_STATE, WORKFLOW_STEPS
import time
import sys
import subprocess
import sys
import subprocess
import re
import os
from dispatcher import Event, EventType
from logger_setup import setup_logger

logger = setup_logger("Router")

def handle_task_event(event: Event):
    """
    Callback for Dispatcher.
    Unwraps event and runs the swarm.
    """
    user_input = event.payload.get("task")
    if not user_input:
        return
        
    logger.info(f"--- [Router] Processing Async Event: {user_input} ---")
    
    # Run the swarm (using the non-streaming wrapper for now, or consuming the generator)
    # Since this is running in a background thread, we just consume the generator to ensure execution.
    # TODO: In the future, we should probably log these updates to a persistent store or a websocket.
    for update in chat_swarm(user_input):
        logger.info(f"[{update['type'].upper()}] {update['content']}")
    
    # Reset state after loop
    AGENT_STATE.labels(agent_name="Router").set(1)

# --- SPECIALIZED INTENT DETECTION ---
def detect_intent(input_text: str) -> str:
    """Classifies user intent: 3D, IMAGE, CODE, TRAIN, or RESEARCH."""
    text = input_text.lower()
    
    # Training Triggers
    if "remember that" in text or "start doing" in text or "correction:" in text or "learn:" in text:
        return "TRAIN"
        
    # Research Triggers (Explicit)
    if "research" in text or "find" in text or "search" in text or "who is" in text or "what is" in text or "explain" in text:
        return "RESEARCH"
        
    if "3d" in text or "forge" in text or "model" in text and "generate" in text:
        return "3D"
        
    if "image" in text or "picture" in text or "draw" in text or "photo" in text:
        return "IMAGE"
        
    # Code Triggers (Now explicit, not default)
    if "code" in text or "script" in text or "python" in text or "function" in text or "app" in text or "execute" in text or "debug" in text or "fix" in text:
        return "CODE"
        
    # Default Fallback -> General Chat/Research
    return "RESEARCH"

def chat_swarm(user_input: str):
    """
    Generator that yields status updates and final response for UI.
    """
    AGENT_STATE.labels(agent_name="Router").set(2)
    WORKFLOW_STEPS.labels(status="started", agent_type="Router").inc()
    
    # 1. Load Context (Memory Bridge)
    from context_manager import get_pending_context, clear_context, save_pending_image_clarification
    pending_ctx = get_pending_context()
    
    # Check if this is a reply to a clarification
    if pending_ctx and pending_ctx.get("type") == "image_clarification":
        original_prompt = pending_ctx.get("prompt")
        logger.info(f"--- [Router] Merging Context. Original: '{original_prompt}' + New: '{user_input}' ---")
        user_input = f"{original_prompt} {user_input}"
        yield {"type": "log", "content": f"[Context Manager] Context Merged: '{user_input}'"}
        clear_context()

    try:
        # 2. Security Check (on the Merged Input)
        yield {"type": "status", "content": "🔒 Security Agent: Scanning input..."}
        security = get_security_agent()
        AGENT_STATE.labels(agent_name="Security").set(2)
        
        security_check: RunResponse = security.run(f"Validate this user command for safety: {user_input}")
        yield {"type": "log", "content": f"[Security Analysis] Algo: Llama-Guard | Output: {security_check.content}"}
        
        AGENT_STATE.labels(agent_name="Security").set(1)
        
        if "UNSAFE" in security_check.content.upper():
            yield {"type": "error", "content": f"🚫 BLOCKED: {security_check.content}"}
            WORKFLOW_STEPS.labels(status="blocked", agent_type="Security").inc()
            return # HITL Block

        yield {"type": "status", "content": "✅ Security Agent: Input Cleared."}
        WORKFLOW_STEPS.labels(status="success", agent_type="Security").inc()

        # 3. Intent Routing (Neural Upgrade)
        from semantic_router import semantic_router
        
        yield {"type": "status", "content": "🧠 Neural Cortex: Analyzing intent..."}
        
        routing_decision = semantic_router.route(user_input)
        intent = routing_decision.get("intent", "RESEARCH") # Fail safe default
        confidence = routing_decision.get("confidence", 0.0)
        reasoning = routing_decision.get("reasoning", "No reasoning provided.")
        
        yield {"type": "log", "content": f"[Router] Intent: {intent} ({confidence * 100:.1f}%) | Reason: {reasoning}"}
        logger.info(f"--- [Router] Neural Decision: {intent} (Conf: {confidence}) ---")
        
        # --- AMBIGUITY CHECK ---
        if intent == "AMBIGUOUS":
             question = routing_decision.get("disambiguation_question", "Could you clarify your request?")
             yield {"type": "response", "content": f"🤔 **Ambiguous Request:** {question}"}
             AGENT_STATE.labels(agent_name="Router").set(1)
             return
        
        # --- CONSULTATIVE LAYER: ART DIRECTOR ---
        if intent == "IMAGE":
             # The user rejected fast-path: We ALWAYS consult the Art Director.
             yield {"type": "status", "content": "🎨 Art Director: Reviewing your vision..."}
             AGENT_STATE.labels(agent_name="ArtDirector").set(2)
             
             from phi.model.ollama import Ollama
             # Config
             MODEL_NAME = "qwen2.5-coder:14b"
             OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
             
             art_director = Agent(
                 name="Art Director",
                 model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST),
                 instructions="""You are the AI Art Director. Your goal is to ensure image prompts are vividly detailed.
                 
                 CRITICAL RULES:
                 1. **Check for Style**: Does the prompt specify "Photo", "Painting", "3D Render", or "Sketch"? If not, ask!
                 2. **Check for Setting**: Does the prompt specify a location? If not, ask!
                 3. **Check for Subject Detail**: "A dog" is bad. "A Golden Retriever" is okay. "A black labrador puppy" is good.
                 
                 RESPONSE FORMAT:
                 - If ANY of the above are missing/vague, return: 'CLARIFY: [Direct question asking for the missing detail]'
                 - If the prompt is fully detailed (Subject + Style + Setting), return: 'EXECUTE'
                 """,
                 show_tool_calls=False
             )
             
             try:
                 # 0. LEARNED MEMORY INJECTION
                 from memory_system import memory
                 learned_rules = memory.get_relevant_rules(user_input, "visual_rules")
                 
                 memory_context = ""
                 if learned_rules:
                     memory_context = f"\n\n[🧠 MEMORY]: The user has previously taught you:\n" + "\n".join([f"- {r}" for r in learned_rules])
                 
                 # Check specificity
                 review_prompt = f"Review this prompt: '{user_input}'{memory_context}"
                 review: RunResponse = art_director.run(review_prompt)
                 
                 if "CLARIFY:" in review.content:
                     # HITL STOP: Return the clarifying question and EXIT the generator.
                     # SAVE CONTEXT so we remember next time.
                     save_pending_image_clarification(user_input)
                     
                     question = review.content.replace("CLARIFY:", "").strip()
                     yield {"type": "response", "content": f"🎨 **Art Director:** {question}"}
                     AGENT_STATE.labels(agent_name="ArtDirector").set(1)
                     return
                 
                 yield {"type": "log", "content": "[Art Director] Prompt approved for Execution."}
                 
             except Exception as e:
                 # Fallback: If AD fails, just execute.
                 logger.error(f"Art Director Failed: {e}")
                 yield {"type": "log", "content": "[Art Director] Offline. Skipping review."}
                 
             AGENT_STATE.labels(agent_name="ArtDirector").set(1)

        # --- ROUTE: RESEARCH / CHAT ---
        if intent == "RESEARCH":
            yield {"type": "status", "content": "💬 Chat Agent: Researching..."}
            AGENT_STATE.labels(agent_name="ChatAgent").set(2)
            
            from phi.model.ollama import Ollama
            MODEL_NAME = "qwen2.5-coder:14b"
            OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            
            researcher = Agent(
                name="Chat Agent",
                model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST),
                instructions="""You are a Researcher/Chat Agent.
                Your goal is to answer user questions comprehensively, provide facts, and summaries.
                If the user asks for code, decline and suggest they ask the Architect.
                If the user asks for images, decline and suggest they ask the Art Director.
                Focus on: Definitions, Explanations, Logical Reasoning, and General Knowledge.
                """,
                show_tool_calls=False
            )
            
            try:
                response: RunResponse = researcher.run(user_input)
                yield {"type": "response", "content": response.content}
                yield {"type": "log", "content": f"[Research] Completed query: {user_input}"}
                
            except Exception as e:
                yield {"type": "error", "content": f"Research Failed: {e}"}
                
            AGENT_STATE.labels(agent_name="ChatAgent").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="ChatAgent").inc()
            return

        # --- ROUTE: 3D GENERATION ---
        if intent == "3D":
            yield {"type": "status", "content": "🔮 Router: Detected 3D Generation Request."}
            
            # Step A: Concept Art
            yield {"type": "status", "content": "🎨 Creative Studio: Generating Concept Art..."}
            AGENT_STATE.labels(agent_name="CreativeStudio").set(2)
            
            from specialized.image_gen import generate_image
            
            concept_prompt = f"Concept art for 3d modeling, neutral background: {user_input}"
            yield {"type": "log", "content": f"[CreativeStudio] Prompt Optimized: '{concept_prompt}'"}
            
            try:
                img_result = generate_image(concept_prompt) 
                yield {"type": "status", "content": f"🖼️ {img_result}"}
                yield {"type": "log", "content": f"[CreativeStudio] Output: {img_result}"}
                AGENT_STATE.labels(agent_name="CreativeStudio").set(1)
                
                import re
                match = re.search(r"Generated Image: ([\w\.-]+)", img_result)
                
                if match:
                    filename = match.group(1)
                    full_image_path = f"/app/comfy_io/output/{filename}" 
                    
                    # Step B: 3D Forge
                    yield {"type": "status", "content": "⚒️ Creature Forge: Hammering Geometry..."}
                    AGENT_STATE.labels(agent_name="Forge").set(2)
                    
                    from specialized.forge_agent import generate_3d_model
                    
                    yield {"type": "log", "content": f"[Forge] Processing: {full_image_path} (High-Res Mode)"}
                    forge_result = generate_3d_model(full_image_path)
                    AGENT_STATE.labels(agent_name="Forge").set(1)
                    
                    # Yield 3D Artifact
                    yield {
                        "type": "artifact", 
                        "content": {
                            "type": "3d_model", 
                            "path": f"{filename}.glb", # Approximation, forge returns string result
                            "name": f"Creature_{filename}"
                        }
                    }
                    
                    yield {"type": "response", "content": forge_result}
                    WORKFLOW_STEPS.labels(status="success", agent_type="Forge").inc()
                    return
                else:
                    yield {"type": "error", "content": f"Failed to parse image filename from: {img_result}"}
                    WORKFLOW_STEPS.labels(status="error", agent_type="CreativeStudio").inc()
                    return
            except Exception as e:
                yield {"type": "error", "content": f"Concept Generation Failed: {e}"}
                yield {"type": "log", "content": f"[Exception] {str(e)}"}
                return

        # --- ROUTE: IMAGE GENERATION ---
        elif intent == "IMAGE":
            yield {"type": "status", "content": "🎨 Creative Studio: Spinning up..."}
            AGENT_STATE.labels(agent_name="CreativeStudio").set(2)
            
            from specialized.image_gen import generate_image
            yield {"type": "log", "content": f"[CreativeStudio] Generating with flux-schnell: '{user_input}'"}
            response = generate_image(user_input)
            
            # Try to extract image path for artifact preview
            import re
            image_match = re.search(r"Generated Image: ([\w\.-]+)", response)
            if image_match:
                filename = image_match.group(1)
                # Assuming standard ComfyUI output location mapping
                # In Docker: /app/comfy_io/output/
                # On Host: mapped via volume. 
                # For UI display, we might need the absolute path or a served URL.
                # Since UI matches the host, strict paths might be tricky if paths differ.
                # However, we'll pass the filename and a robust path for now.
                
                # --- ROBUST DELIVERY: HTTP DOWNLOAD ---
                # Since we are in Docker, we cannot access host C:\ paths directly unless mounted.
                # Reliable info: We have COMFYUI_HOST from environment.
                
                delivery_dir = os.path.join(os.getcwd(), "delivered_artifacts")
                if not os.path.exists(delivery_dir):
                    os.makedirs(delivery_dir, exist_ok=True)
                    
                delivery_path = os.path.join(delivery_dir, filename)
                COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://host.docker.internal:8188")
                
                logger.info(f"Attempting download from {COMFYUI_HOST} for {filename}...")
                
                try:
                    # Download from ComfyUI API
                    # Endpoint: /view?filename=...&subfolder=&type=output
                    import requests
                    url = f"{COMFYUI_HOST}/view"
                    params = {"filename": filename, "subfolder": "", "type": "output"}
                    
                    # Retry loop for download (in case Comfy is slow to serve)
                    for i in range(10):
                        r = requests.get(url, params=params, timeout=10)
                        if r.status_code == 200:
                            with open(delivery_path, 'wb') as f:
                                f.write(r.content)
                            logger.info(f"Downloaded and delivered artifact: {delivery_path}")
                            
                            yield {
                                "type": "artifact",
                                "content": {
                                    "type": "image",
                                    "name": filename,
                                    "path": delivery_path, 
                                    "docker_path": f"/app/comfy_io/output/{filename}" 
                                }
                            }
                            break
                        else:
                            logger.warning(f"Download attempt {i+1} failed: {r.status_code}. Retrying...")
                            import time
                            time.sleep(1)
                    else:
                         logger.error(f"Failed to download image after retries. Status: {r.status_code}")
                         yield {"type": "error", "content": f"Could not retrieve image from engine. (Status {r.status_code})"}
                         
                except Exception as e:
                    logger.error(f"Download error: {e}")
                    yield {"type": "error", "content": f"Failed to download artifact: {e}"}
            
            AGENT_STATE.labels(agent_name="CreativeStudio").set(1)
            
            AGENT_STATE.labels(agent_name="CreativeStudio").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="CreativeStudio").inc()
            yield {"type": "response", "content": response}
            return

        # --- ROUTE: TRAINER (FEEDBACK LOOP) ---
        if intent == "TRAIN":
            yield {"type": "status", "content": "🧠 Memory Controller: Learning new skill..."}
            from memory_system import memory
            
            # Simple Heuristic Parser
            # "Remember that [KEYWORD] means [RULE]"
            # "Correction: [KEYWORD] should be [RULE]"
            
            domain = "general_rules" 
            keyword = "general"
            rule = user_input
            
            # Attempt to extract structure
            if "code" in user_input or "python" in user_input or "script" in user_input:
                domain = "coding_rules"
            elif "image" in user_input or "style" in user_input or "look" in user_input:
                domain = "visual_rules"
                
            # Extract Keyword (Naive) -> "Remember that CYBERPUNK means..."
            import re
            match = re.search(r"(?:remember that|correction:|learn:) (.+?) (?:means|is|should be) (.+)", user_input, re.IGNORECASE)
            
            if match:
                keyword = match.group(1).strip()
                rule = match.group(2).strip()
                
            result = memory.add_rule(domain, keyword, rule)
            yield {"type": "response", "content": f"🧠 **Learned**: {result}"}
            return

        # --- ROUTE: STANDARD ARCHITECT (DEFAULT) ---
        else:
            yield {"type": "status", "content": "🏗️ Architect Agent: Planning & Executing..."}
            architect = get_architect_agent()
            AGENT_STATE.labels(agent_name="Architect").set(2)
            
            try:
                # 0. LEARNED MEMORY INJECTION
                from memory_system import memory
                code_rules = memory.get_relevant_rules(user_input, "coding_rules")
                
                final_input = user_input
                if code_rules:
                    rule_block = "\n".join([f"- {r}" for r in code_rules])
                    final_input = f"{user_input}\n\n[🧠 MEMORY] Apply these user-taught coding rules:\n{rule_block}"
                    yield {"type": "log", "content": f"[Memory] Injected {len(code_rules)} coding rules."}
                
                # Primary Execution Attempt
                yield {"type": "log", "content": f"[Architect] Sending prompt to Qwen2.5-Coder: '{user_input}'"}
                response: RunResponse = architect.run(final_input)
                yield {"type": "log", "content": f"[Architect] Raw Response Length: {len(response.content)} chars"}
            except Exception as e:
                # --- SELF-HEALING PROTOCOL ---
                error_str = str(e)
                yield {"type": "log", "content": f"[Exception] Architect Crash: {error_str}"}
                
                package_match = re.search(r"No module named '(\w+)'", error_str) or \
                                re.search(r"custom_nodes\\(\w+)", error_str) 
                
                if package_match:
                    missing_pkg = package_match.group(1)
                    yield {"type": "status", "content": f"🚨 Dependency Gatekeeper: Missing '{missing_pkg}'"}
                    
                    # 1. Consult Security Agent
                    yield {"type": "status", "content": f"🛡️ Security Agent: Reviewing '{missing_pkg}'..."}
                    security = get_security_agent()
                    review = security.review_dependency(missing_pkg)
                    yield {"type": "log", "content": f"[Gatekeeper] Security Review Verdict: {review.content}"}
                    
                    if review.content == "SAFE":
                        yield {"type": "status", "content": "✅ Security Agent: APPROVED. Installing..."}
                        try:
                            # 2. Ephemeral Installation
                            yield {"type": "log", "content": f"[Gatekeeper] Executing: pip install {missing_pkg}"}
                            subprocess.check_call([sys.executable, "-m", "pip", "install", missing_pkg])
                            yield {"type": "status", "content": f"💾 System: '{missing_pkg}' Installed. Retrying Task..."}
                            
                            # 3. Retry Execution
                            yield {"type": "log", "content": "[Gatekeeper] Retrying Agent Execution..."}
                            response = architect.run(user_input)
                        except Exception as install_error:
                            yield {"type": "error", "content": f"🔥 Self-Healing Failed: {install_error}"}
                            return
                    else:
                        yield {"type": "error", "content": f"🚫 Security Agent: Blocked installation of '{missing_pkg}'"}
                        return
                else:
                    raise e

            
            # Parse and execute tools
            yield {"type": "status", "content": "⚙️ Architect Agent: Executing Tools..."}
            
            # Capture and yield tool logs
            tool_results = parse_and_execute_tools(response.content)
            
            # Capture and yield tool logs
            tool_results = parse_and_execute_tools(response.content)
            
            # Note: parse_and_execute_tools logs to file logger but doesn't return detailed structure yet.
            # We will just log the results for now.
            for res_obj in tool_results:
                 res = res_obj["output"]
                 yield {"type": "status", "content": f"🛠️ Tool: {res}"}
                 yield {"type": "log", "content": f"[Tool Output] {res}"}
                 
                 # Yield Artifact if present
                 if res_obj["artifact"]:
                     yield {"type": "artifact", "content": res_obj["artifact"]}
            
            WORKFLOW_STEPS.labels(status="success", agent_type="Architect").inc()
            AGENT_STATE.labels(agent_name="Architect").set(1)
            
            yield {"type": "response", "content": response.content}
            yield {"type": "log", "content": "[Router] Workflow Complete."}

    except Exception as e:
        yield {"type": "error", "content": f"🔥 Error: {e}"}
        WORKFLOW_STEPS.labels(status="error", agent_type="Router").inc()
    finally:
        AGENT_STATE.labels(agent_name="Router").set(1)

def run_swarm(user_input: str):
    """CLI Wrapper for chat_swarm"""
    print(f"--- [Swarm] Receiving Task: {user_input} ---") # Keep print for CLI
    for update in chat_swarm(user_input):
        print(f"[{update['type'].upper()}] {update['content']}") # Keep print for CLI



import json
import re
from tools.file_ops import write_file, read_file
from tools.terminal import run_command

def parse_and_execute_tools(response_text: str) -> list:
    """
    Parses JSON tool calls from markdown blocks and executes them.
    Returns a list of result strings to display in UI.
    """
    results = []
    
    # Regex to find json blocks
    json_blocks = re.findall(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    
    if not json_blocks:
        # Try finding raw json objects if not in markdown
        json_blocks = re.findall(r"(\{.*?\})", response_text, re.DOTALL)

    for block in json_blocks:
        try:
            tool_call = json.loads(block)
            tool_name = tool_call.get("name")
            args = tool_call.get("arguments", {})
            
            logger.info(f"--- [Tool Parser] Detected Tool: {tool_name} ---")
            
            outcome = ""
            artifact = None
            
            if tool_name == "write_file":
                path = args.get("path")
                content = args.get("content")
                result = write_file(path, content)
                outcome = f"Write File: {result}"
                
                # Create Artifact Metadata
                artifact = {
                    "type": "file",
                    "path": path,
                    "content": content,
                    "name": os.path.basename(path)
                }
                
            elif tool_name == "run_command":
                result = run_command(args.get("command"))
                outcome = f"Run Command: {result}"
            elif tool_name == "read_file":
                result = read_file(args.get("path"))
                outcome = f"Read File: {result[:50]}..." # Truncate read
            
            logger.info(f"[Result] {outcome}")
            results.append({"output": outcome, "artifact": artifact})
                
        except json.JSONDecodeError:
            continue
        except Exception as e:
            err_msg = f"Tool Execution Failed: {e}"
            logger.error(err_msg)
            results.append({"output": err_msg, "artifact": None})
            
    return results

if __name__ == "__main__":
    # Example dry run
    run_swarm("Write a Python script to calculate the Fibonacci sequence.")
