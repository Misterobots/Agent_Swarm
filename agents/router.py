from phi.agent import Agent, RunResponse
from architect_agent import get_architect_agent
from security_agent import get_security_agent

# MarsRL Loop — Solver → Verifier → Corrector
from mars_loop import MarsRLLoop, mars_loop_stream
from verifier_agent import get_verifier
from corrector_agent import get_corrector

from metrics import AGENT_STATE, WORKFLOW_STEPS
import time
import sys
import subprocess
import re
import os
from dispatcher import Event, EventType
from logger_setup import setup_logger
from utils.gpu_queue import request_lock

logger = setup_logger("Router")

# --- Langfuse Tracing ---
try:
    from langfuse import Langfuse, observe
    import os
    
    langfuse = Langfuse(
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-dev"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-dev"),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3001")
    )
    USE_LANGFUSE = True
    langfuse_context = None # Stubbed for v3 compatibility until open-telemetry logic is integrated
    logger.info("[Router] Langfuse tracing enabled")
except ImportError:
    USE_LANGFUSE = False
    observe = lambda *args, **kwargs: lambda f: f  # No-op decorator
    langfuse_context = None
    logger.warning("[Router] Langfuse not available, tracing disabled")

@observe(name="handle_task_event")  # Langfuse traces this function
def handle_task_event(event: Event):
    """
    Callback for Dispatcher.
    Unwraps event and runs the swarm.
    Traced by Langfuse for observability.
    """
    print(f"DEBUG ROUTER: handle_task_event called with payload keys: {event.payload.keys()}")
    user_input = event.payload.get("task")
    intent = event.payload.get("intent", "DEFAULT") # From Dispatcher
    target_device = event.payload.get("target_device", "auto")
    session_id = event.payload.get("session_id", "default_session")

    if not user_input:
        return
    
    # Add context to Langfuse trace
    if USE_LANGFUSE and langfuse:
        try:
            langfuse.trace(
                name="handle_task_event",
                session_id=session_id,
                metadata={
                    "intent": intent,
                    "target_device": target_device
                }
            )
        except Exception as e:
            logger.warning(f"[Router] Trace update failed: {e}")
        
    logger.info(f"--- [Router] Processing Async Event: {user_input} (Intent: {intent}) ---")

    try:
        if intent == "IMAGE":
            # Direct Route to Creative Team / Image Gen
            from specialized.image_gen import generate_image
            logger.info(f"[Router] Routing to Image Gen (Device: {target_device})")
            
            # Execute
            with request_lock(context="image"):
                response = generate_image(user_input, target_device=target_device)
            logger.info(f"[ImageGen] Result: {response}")
            
        elif intent == "3D":
             # Direct Route to 3D Pipeline
             from specialized.image_gen import generate_image
             # ... (Add 3D logic if needed, or just use image gen for concept art first)
             logger.info("[Router] Routing to 3D Pipeline (starting with concept art)...")
             with request_lock(context="image"):
                 response = generate_image(f"Concept art for 3d modeling: {user_input}", target_device=target_device)
             logger.info(f"[3D] Concept Art Result: {response}")
             # trigger forge here if implemented
             
        else:
            # Default: Orchestrator with session persistence
            from teams import get_orchestrator
            orchestrator = get_orchestrator()
            # Run the orchestrator (it handles delegation to teams)
            response = orchestrator.run(user_input)
            logger.info(f"[Orchestrator] Final Response: {response.content}")
        
    except Exception as e:
        logger.error(f"Task Execution Failed: {e}")

    # Reset state after loop
    AGENT_STATE.labels(agent_name="Router").set(1)

# --- SPECIALIZED INTENT DETECTION ---
# (Keyword-based detect_intent() was removed in favor of neural semantic_router)
def chat_swarm(user_input: str, session_id: str = "default_session", history: list = None):
    """
    Generator that yields status updates and final response for UI.
    - history: Optional list of OpenAI-formatted messages [{"role": "user", "content": "..."}]
    """
    AGENT_STATE.labels(agent_name="Router").set(2)
    WORKFLOW_STEPS.labels(status="started", agent_type="Router").inc()
    
    # --- HISTORY CONVERSION ---
    # PHI Agents use their own storage/history, but we can seed it or pass it.
    # For now, we'll use history to enhance the prompt if provided.
    history_context = ""
    if history:
        history_context = "\n\n[Previous Conversation History]:\n"
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_context += f"- {role.upper()}: {content}\n"
    
    # --- RAG CONTEXT INTERCEPTION ---
    import re
    extracted_context = ""
    context_match = re.search(r'<context>.*?</context>', user_input, re.DOTALL)
    if context_match:
        extracted_context = context_match.group(0)
        # Strip Open-WebUI's boilerplate injection
        user_input = re.sub(r'### Task:.*?<context>.*?</context>\s*', '', user_input, flags=re.DOTALL).strip()
        yield {"type": "log", "content": f"[Router] Intercepted RAG Context ({len(extracted_context)} chars)."}
    
    # 1. Load Context (Memory Bridge)
    from context_manager import get_pending_context, clear_context, save_pending_image_clarification
    pending_ctx = get_pending_context()
    
    # Check if this is a reply to a clarification
    if pending_ctx:
        if pending_ctx.get("type") == "image_clarification":
            original_prompt = pending_ctx.get("prompt")
            logger.info(f"--- [Router] Merging Context. Original: '{original_prompt}' + New: '{user_input}' ---")
            user_input = f"{original_prompt} {user_input}"
            yield {"type": "log", "content": f"[Context Manager] Context Merged: '{user_input}'"}
            clear_context()
            
        elif pending_ctx.get("type") == "ambiguity_resolution":
            original = pending_ctx.get("prompt")
            question = pending_ctx.get("question")
            logger.info(f"--- [Router] Resolving Ambiguity. Original: '{original}' + Answer: '{user_input}' ---")
            
            # Composite prompt for the Semantic Router
            user_input = f"Original Request: '{original}'\nSystem Question: '{question}'\nUser Answer: '{user_input}'"
            
            yield {"type": "log", "content": f"[Context Manager] Ambiguity Resolved. Analying composite input..."}
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
        from semantic_router import get_semantic_router
        
        yield {"type": "status", "content": "🧠 Neural Cortex: Analyzing intent..."}
        
        router_inst = get_semantic_router()
        routing_decision = router_inst.route(user_input)
        intent = routing_decision.get("intent", "RESEARCH") # Fail safe default
        confidence = routing_decision.get("confidence", 0.0)
        reasoning = routing_decision.get("reasoning", "No reasoning provided.")
        
        yield {"type": "log", "content": f"[Router] Intent: {intent} ({confidence * 100:.1f}%) | Reason: {reasoning}"}
        logger.info(f"--- [Router] Neural Decision: {intent} (Conf: {confidence}) ---")
        
        if USE_LANGFUSE and langfuse_context:
            langfuse_context.update_current_observation(
                name="intent_routing",
                metadata={"model": router_inst.model_name, "host": router_inst.host},
                output=routing_decision,
                scores=[{"name": "routing_confidence", "value": confidence}]
            )
        
        # --- AMBIGUITY CHECK ---
        if intent == "AMBIGUOUS":
             question = routing_decision.get("disambiguation_question", "Could you clarify your request?")
             
             # SAVE CONTEXT so we remember what was ambiguous
             from context_manager import save_pending_context
             save_pending_context({
                 "type": "ambiguity_resolution",
                 "prompt": user_input,
                 "question": question
             })
             
             yield {"type": "response", "content": f"🤔 **Ambiguous Request:** {question}"}
             AGENT_STATE.labels(agent_name="Router").set(1)
             return
        
        # --- CONSULTATIVE LAYER: ART DIRECTOR ---
        if intent == "IMAGE":
             # The user rejected fast-path: We ALWAYS consult the Art Director.
             yield {"type": "status", "content": "🎨 Art Director: Reviewing your vision..."}
             AGENT_STATE.labels(agent_name="ArtDirector").set(2)
             
             from phi.model.ollama import Ollama
             from utils.gpu_queue import get_ollama_host
             # Config
             MODEL_NAME = "qwen2.5-coder:14b"
             OLLAMA_HOST = get_ollama_host(MODEL_NAME)
             
             art_director = Agent(
                 name="Art Director",
                 model=Ollama(id=MODEL_NAME, host=OLLAMA_HOST, client_kwargs={"timeout": 300.0}),
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

        # --- ROUTE: DOCUMENTATION / TECHNICAL WRITING ---
        if intent == "DOCUMENTATION":
            yield {"type": "status", "content": "📝 Technical Writer: Reviewing document structure..."}
            AGENT_STATE.labels(agent_name="TechnicalWriter").set(2)
            
            from utils.gpu_queue import get_ollama_host
            # Use qwen3.5:9b for efficient 256k context coding
            TECH_MODEL = os.getenv("ARCHITECT_MODEL", "qwen3.5:9b")
            OLLAMA_HOST = get_ollama_host(TECH_MODEL)
            
            tech_writer = Agent(
                name="Technical Writer",
                model=Ollama(id=TECH_MODEL, host=OLLAMA_HOST, client_kwargs={"timeout": 300.0}),
                instructions="""You are a Staff-Level Technical Writer.
                Your goal is to rewrite, format, and organize documentation into professional, polished markdown.
                If provided with large context files, synthesize the information accurately.
                Focus on clarity, tone, accurate citations, and structured formatting (headings, lists, bolding).
                """,
                show_tool_calls=False
            )
            
            try:
                final_input = user_input
                
                # Context integration
                from memory_system import memory
                doc_rules = memory.get_relevant_rules(user_input, "general_rules")
                if doc_rules:
                    rule_block = "\n".join([f"- {r}" for r in doc_rules])
                    final_input = f"{final_input}\n\n[🧠 MEMORY] Apply these rules:\n{rule_block}"
                    yield {"type": "log", "content": f"[Memory] Injected {len(doc_rules)} stylistic rules."}
                    
                if extracted_context:
                    yield {"type": "log", "content": f"[TechnicalWriter] Reading Attached RAG Context ({len(extracted_context)} chars)..."}
                    final_input = f"{final_input}\n\n[Attached Document Context]:\n{extracted_context}"
                    
                with request_lock(context="text"):
                    response_stream = tech_writer.run(final_input, stream=True)
                    yield {"type": "status", "content": "📝 Technical Writer: Generating document..."}
                    full_content = ""
                    for chunk in response_stream:
                        if chunk.content:
                            full_content += chunk.content
                            yield {"type": "message", "content": chunk.content}
                
                yield {"type": "log", "content": "[TechnicalWriter] Document Transformation Complete."}
                yield {"type": "response", "content": full_content}
                
            except Exception as e:
                yield {"type": "error", "content": f"Technical Writing Failed: {e}"}
                
            AGENT_STATE.labels(agent_name="TechnicalWriter").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="TechnicalWriter").inc()
            return

        # --- ROUTE: RESEARCH / CHAT ---
        if intent == "RESEARCH":
            yield {"type": "status", "content": "📚 Librarian Agent: Accessing Archives..."}
            AGENT_STATE.labels(agent_name="Librarian").set(2)
            
            from phi.model.ollama import Ollama
            from agents.config import LIBRARIAN_MODEL, OLLAMA_HOST
            
            researcher = Agent(
                name="Librarian",
                model=Ollama(id=LIBRARIAN_MODEL, host=OLLAMA_HOST),
                instructions="""You are the Hive Librarian and Scholar.
                Your goal is to provide deep historical context, literary analysis, and general knowledge.
                You are the guardian of facts and culture. Focus on: History, Literature, Philosophy, Science, and Factual Explanations.
                If the user asks for code, decline and suggest they ask the Architect.
                If the user asks for images, decline and suggest they ask the Art Director.
                """,
                show_tool_calls=False
            )
            
            try:
                final_input = user_input
                if extracted_context:
                    yield {"type": "log", "content": "[Librarian] Reading Attached RAG Context..."}
                    final_input = f"{user_input}\n\n[Attached Document Context]:\n{extracted_context}"
                    
                with request_lock(context="text"):
                    response_stream = researcher.run(final_input, stream=True)
                    yield {"type": "status", "content": "📚 Librarian Agent: Drafting response..."}
                    full_content = ""
                    for chunk in response_stream:
                        if chunk.content:
                            full_content += chunk.content
                            yield {"type": "message", "content": chunk.content}
                
                yield {"type": "log", "content": f"[Research] Completed query: {user_input}"}
                yield {"type": "response", "content": full_content}
                
            except Exception as e:
                yield {"type": "error", "content": f"Research Failed: {e}"}
                
            AGENT_STATE.labels(agent_name="Librarian").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="Librarian").inc()
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
                with request_lock(context="image"):
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
                    with request_lock(context="image"):
                        forge_result = generate_3d_model(full_image_path)
                    AGENT_STATE.labels(agent_name="Forge").set(1)
                    
                    # Yield 3D Artifact
                    yield {
                        "type": "artifact", 
                        "content": {
                            "type": "3d_model", 
                            "path": f"{filename}.glb", 
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
            with request_lock(context="image"):
                response = generate_image(user_input)
            
            # Extraction logic for artifact delivery
            import re
            image_match = re.search(r"Generated Image: ([\w\.-]+)", response)
            if image_match:
                filename = image_match.group(1)
                delivery_dir = os.path.join(os.getcwd(), "delivered_artifacts")
                if not os.path.exists(delivery_dir):
                    os.makedirs(delivery_dir, exist_ok=True)
                    
                delivery_path = os.path.join(delivery_dir, filename)
                COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://host.docker.internal:8188")
                
                try:
                    import requests
                    url = f"{COMFYUI_HOST}/view"
                    params = {"filename": filename, "subfolder": "", "type": "output"}
                    for i in range(10):
                        r = requests.get(url, params=params, timeout=10)
                        if r.status_code == 200:
                            with open(delivery_path, 'wb') as f:
                                f.write(r.content)
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
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"Download error: {e}")
            
            AGENT_STATE.labels(agent_name="CreativeStudio").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="CreativeStudio").inc()
            yield {"type": "response", "content": response}
            return

        # --- ROUTE: TRAINER (FEEDBACK LOOP) ---
        if intent == "TRAIN":
            yield {"type": "status", "content": "🧠 Memory Controller: Learning new skill..."}
            from memory_system import memory
            
            domain = "general_rules" 
            keyword = "general"
            rule = user_input
            
            if "code" in user_input or "python" in user_input or "script" in user_input:
                domain = "coding_rules"
            elif "image" in user_input or "style" in user_input or "look" in user_input:
                domain = "visual_rules"
                
            import re
            match = re.search(r"(?:remember that|correction:|learn:) (.+?) (?:means|is|should be) (.+)", user_input, re.IGNORECASE)
            
            if match:
                keyword = match.group(1).strip()
                rule = match.group(2).strip()
                
            result = memory.add_rule(domain, keyword, rule)
            yield {"type": "response", "content": f"🧠 **Learned**: {result}"}
            return

        # --- ROUTE: IOT CONTROLLER (HOME ASSISTANT) ---
        if intent == "IOT_CONTROL":
            yield {"type": "status", "content": "🏠 IoT Controller: Connecting to Home..."}
            AGENT_STATE.labels(agent_name="IoTController").set(2)
            
            from specialized.iot_agent import get_iot_agent
            iot_agent = get_iot_agent()
            
            try:
                yield {"type": "log", "content": f"[IoT] Dispatching: '{user_input}'"}
                response: RunResponse = iot_agent.run(user_input)
                yield {"type": "response", "content": response.content}
            except Exception as e:
                yield {"type": "error", "content": f"IoT Error: {e}"}
                
            AGENT_STATE.labels(agent_name="IoTController").set(1)
            WORKFLOW_STEPS.labels(status="success", agent_type="IoTController").inc()
            return

        # --- ROUTE: STANDARD ARCHITECT / CODE (MarsRL Loop) ---
        else:
            yield {"type": "status", "content": "🏗️ MarsRL: Solver → Verifier → Corrector..."}
            AGENT_STATE.labels(agent_name="Architect").set(2)

            try:
                from memory_system import memory
                code_rules = memory.get_relevant_rules(user_input, "coding_rules")
                
                final_input = user_input
                if code_rules:
                    rule_block = "\n".join([f"- {r}" for r in code_rules])
                    final_input = f"{user_input}\n\n[🧠 MEMORY] Apply these user-taught coding rules:\n{rule_block}"
                    yield {"type": "log", "content": f"[Memory] Injected {len(code_rules)} coding rules."}

                if extracted_context:
                    final_input = f"{final_input}\n\n[Attached Document Context]:\n{extracted_context}"

                solver = get_architect_agent(session_id=session_id)
                verifier = get_verifier()
                corrector = get_corrector(session_id=session_id)

                mars = MarsRLLoop(
                    solver=solver,
                    verifier=verifier,
                    corrector=corrector,
                    max_iter=2,
                    intent=intent,
                    session_id=session_id,
                )

                yield {"type": "log", "content": f"[MarsRL] Intent: {intent} | Loop initialized."}

                with request_lock(context="text"):
                    for update in mars_loop_stream(final_input, mars):
                        yield update

            except Exception as e:
                error_str = str(e)
                yield {"type": "log", "content": f"[Exception] MarsRL Crash: {error_str}"}

                package_match = re.search(r"No module named '(\w+)'", error_str) or \
                                re.search(r"custom_nodes\\(\w+)", error_str)

                if package_match:
                    missing_pkg = package_match.group(1)
                    yield {"type": "status", "content": f"🚨 Gatekeeper: Missing '{missing_pkg}'"}
                    security = get_security_agent()
                    review = security.review_dependency(missing_pkg)
                    if review.content == "SAFE":
                        subprocess.check_call([sys.executable, "-m", "pip", "install", missing_pkg])
                        yield {"type": "status", "content": f"💾 Fixed: Installed '{missing_pkg}'."}
                    else:
                        yield {"type": "error", "content": f"🚫 Security: Blocked '{missing_pkg}'"}
                        return
                else:
                    raise e

            WORKFLOW_STEPS.labels(status="success", agent_type="Architect").inc()
            AGENT_STATE.labels(agent_name="Architect").set(1)

    except Exception as e:
        yield {"type": "error", "content": f"🔥 Error: {e}"}
        WORKFLOW_STEPS.labels(status="error", agent_type="Router").inc()
    finally:
        AGENT_STATE.labels(agent_name="Router").set(1)

def run_swarm(user_input: str):
    """CLI Wrapper for chat_swarm"""
    print(f"--- [Swarm] Receiving Task: {user_input} ---")
    for update in chat_swarm(user_input, session_id="cli_session"):
        print(f"[{update['type'].upper()}] {update['content']}")

if __name__ == "__main__":
    run_swarm("Write a Python script to calculate the Fibonacci sequence.")
