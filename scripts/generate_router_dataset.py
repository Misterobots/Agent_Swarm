"""
Generate a focused intent-classification training dataset for the
Nemotron-8B router model.

Produces JSONL in the GRPO conversations format:
  {"conversations": [{"role":"user","content":"..."}, {"role":"assistant","content":"{...}"}], "reward": {...}}

Each sample trains the model to classify user input into one of 12 intents
with correct JSON output format matching the SemanticRouter spec.
"""

import json
import random
import pathlib
from datetime import datetime

OUTPUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "training_data"

# ── Intent examples ──────────────────────────────────────────────────────────
# Each key maps to a list of (user_input, reasoning) tuples.
INTENT_EXAMPLES = {
    "CONVERSATION": [
        ("Hello! How are you?", "Greeting and casual social interaction"),
        ("What's your name?", "Identity question, social in nature"),
        ("Tell me a joke", "Casual entertainment request"),
        ("How's the weather today?", "Small talk about weather"),
        ("What do you think about cats?", "Casual opinion question"),
        ("Good morning!", "Simple greeting"),
        ("Thanks for your help!", "Social gratitude expression"),
        ("Who are you?", "Identity inquiry, conversational"),
        ("What can you do?", "Capability inquiry, general chat"),
        ("Tell me something interesting", "General conversation starter"),
        ("Hi there, I'm bored", "Casual chat seeking engagement"),
        ("What time is it?", "Simple factual question"),
        ("Are you an AI?", "Meta question about identity"),
        ("I had a great day today", "Sharing personal experience"),
        ("What's your favorite color?", "Playful social question"),
        ("Can you sing a song?", "Casual entertainment request"),
        ("How old are you?", "Social identity question"),
        ("Tell me about yourself", "Identity and capability inquiry"),
        ("Goodnight!", "Social farewell"),
        ("What is the meaning of life?", "Philosophical casual question"),
        ("Do you like pizza?", "Fun casual question"),
        ("I'm feeling happy today", "Emotional sharing, social"),
        ("What's up?", "Informal greeting"),
        ("You're pretty smart", "Compliment, social interaction"),
        ("Let's chat about something fun", "Casual conversation request"),
        ("Hey buddy", "Informal greeting"),
        ("What should I have for dinner?", "Casual life advice question"),
        ("Do you dream?", "Philosophical casual question"),
        ("Can you recommend a movie?", "Casual recommendation request"),
        ("What's 2+2?", "Simple factual math question"),
    ],
    "CODE": [
        ("Write a Python function to sort a list of dictionaries by key", "Explicit code writing request with language and data structure"),
        ("Fix this bug in my JavaScript: function add(a,b) { return a - b; }", "Debug request with code snippet"),
        ("How do I implement a binary search tree in Java?", "Software engineering data structure implementation"),
        ("Refactor this code to use async/await", "Code refactoring request"),
        ("Write a REST API endpoint in FastAPI", "Web framework code generation"),
        ("Create a React component for a todo list", "Frontend component development"),
        ("Help me debug this segfault in my C program", "Low-level debugging request"),
        ("Implement a linked list in Python", "Data structure implementation"),
        ("Write unit tests for this function", "Test engineering request"),
        ("Convert this Python 2 code to Python 3", "Code migration task"),
        ("How do I handle errors in Rust?", "Language-specific coding question"),
        ("Write a regex to match email addresses", "Pattern matching code"),
        ("Create a class for managing database connections", "OOP design/code request"),
        ("Optimize this SQL query for better performance", "Code optimization request"),
        ("Implement OAuth2 authentication in Node.js", "Security implementation code"),
        ("Write a decorator that caches function results", "Advanced Python coding"),
        ("Help me fix this TypeScript type error", "Type system debugging"),
        ("Create a CLI tool using argparse", "Tool development"),
        ("Write a web scraper using BeautifulSoup", "Script development"),
        ("How do I use generics in TypeScript?", "Language feature question with code focus"),
        ("Build a chat application using WebSockets", "Full-stack app development"),
        ("Write a Python script to merge two CSV files", "Script writing request"),
        ("Implement pagination for my API", "Backend feature development"),
        ("Create a middleware for logging requests", "Backend architecture code"),
        ("Write a function to validate credit card numbers", "Validation logic coding"),
    ],
    "DEVOPS": [
        ("Set up a Docker container for my Node.js app", "Container configuration task"),
        ("Write a GitHub Actions CI/CD pipeline", "CI/CD pipeline creation"),
        ("Configure nginx as a reverse proxy", "Web server configuration"),
        ("Create a Kubernetes deployment manifest", "Container orchestration"),
        ("How do I set up SSH key authentication?", "Linux sysadmin task"),
        ("Write a bash script to monitor disk usage", "Shell scripting for ops"),
        ("Set up a systemd service for my application", "Linux service management"),
        ("Configure a firewall with iptables", "Network security setup"),
        ("Deploy my app to AWS using Terraform", "Cloud infrastructure as code"),
        ("Create a docker-compose.yml for a multi-service stack", "Container orchestration"),
        ("How do I troubleshoot a 502 Bad Gateway error?", "Infrastructure debugging"),
        ("Set up Prometheus monitoring for my services", "Observability setup"),
        ("Write an Ansible playbook for server provisioning", "Configuration management"),
        ("Configure SSL certificates with Let's Encrypt", "Security infrastructure"),
        ("Set up a load balancer with HAProxy", "Network infrastructure"),
        ("Create a Dockerfile with multi-stage builds", "Container optimization"),
        ("How do I migrate a database to a new server?", "Server migration task"),
        ("Configure Grafana dashboards for system metrics", "Monitoring dashboard setup"),
        ("Set up a VPN between two servers", "Network configuration"),
        ("Write a cron job to backup my database nightly", "Scheduled task administration"),
        ("Help me configure Cloudflare DNS for my domain", "DNS and CDN configuration"),
        ("Set up a Redis cluster for caching", "Infrastructure scaling"),
        ("Configure log rotation for my application", "System maintenance"),
        ("Deploy a microservice to Docker Swarm", "Container orchestration deployment"),
        ("Troubleshoot why my container keeps restarting", "Container debugging"),
    ],
    "DATA": [
        ("Analyze this CSV file and show me the trends", "Data analysis request"),
        ("Write a SQL query to find the top 10 customers by revenue", "SQL data query"),
        ("Create a pandas DataFrame from this JSON data", "Data transformation"),
        ("Generate a bar chart showing monthly sales", "Data visualization"),
        ("Calculate the standard deviation of this dataset", "Statistical analysis"),
        ("Help me clean this messy dataset", "Data cleaning request"),
        ("Write a query to join these three tables", "Complex SQL query"),
        ("Create a pivot table from this data", "Data aggregation"),
        ("What's the correlation between these two columns?", "Statistical analysis"),
        ("Build a dashboard showing key metrics", "Dashboard creation"),
        ("Parse this JSON file and extract specific fields", "Data extraction"),
        ("Group this data by category and sum the values", "Data aggregation"),
        ("Convert this CSV to a normalized database schema", "Data modeling"),
        ("Find outliers in this dataset", "Statistical analysis"),
        ("Create a time series analysis of this data", "Advanced analytics"),
        ("Aggregate sales data by region and quarter", "Business analytics"),
        ("Write a query to calculate running totals", "Window function SQL"),
        ("Visualize the distribution of ages in this dataset", "Data visualization"),
        ("Help me design a star schema for this data warehouse", "Data architecture"),
        ("Calculate moving averages for stock prices", "Financial data analysis"),
    ],
    "IMAGE": [
        ("Generate an image of a sunset over mountains", "2D image generation request"),
        ("Draw a portrait of a medieval knight", "Art generation request"),
        ("Create a picture of a futuristic city", "Visual art generation"),
        ("Generate a photo-realistic image of a cat wearing a hat", "Photo generation"),
        ("Paint a watercolor landscape", "Art style generation"),
        ("Create concept art for a sci-fi spaceship", "Concept art generation"),
        ("Generate an illustration of a fantasy castle", "Illustration request"),
        ("Make a pixel art character sprite", "Specific art style generation"),
        ("Create a logo design for my coffee shop", "Graphic design generation"),
        ("Generate a beautiful autumn forest scene", "Scenic image generation"),
        ("Draw a cartoon version of my pet", "Stylized image generation"),
        ("Create a texture for a brick wall", "Texture/material generation"),
        ("Generate an anime-style character", "Style-specific image generation"),
        ("Make a poster for a music concert", "Graphic design generation"),
        ("Create a photorealistic food photography image", "Photo generation"),
        ("Generate a cyberpunk cityscape at night", "Themed image generation"),
        ("Draw a diagram of the solar system", "Educational illustration"),
        ("Create an abstract art piece with blue tones", "Abstract art generation"),
        ("Generate a profile picture with a gradient background", "Avatar generation"),
        ("Paint a portrait in the style of Van Gogh", "Style-transfer art generation"),
    ],
    "3D": [
        ("Create a 3D model of a coffee cup", "3D geometry generation"),
        ("Generate a low-poly 3D tree", "3D mesh creation"),
        ("Build a 3D model of a medieval sword", "3D object modeling"),
        ("Create a GLB file of a house", "3D format-specific request"),
        ("Model a 3D character for a game", "Game asset 3D modeling"),
        ("Generate a 3D mesh of a car", "Vehicle 3D modeling"),
        ("Create a 3D terrain for a landscape", "Environmental 3D modeling"),
        ("Build a 3D model of a robot", "Mechanical 3D modeling"),
        ("Create an OBJ file of a chess piece", "3D format-specific modeling"),
        ("Model a 3D skull for printing", "3D print modeling"),
        ("Generate a 3D architectural model of a building", "Architectural 3D"),
        ("Create a 3D weapon for a RPG game", "Game asset creation"),
        ("Build a 3D model of a dragon", "Fantasy creature modeling"),
        ("Create a 3D model of furniture for interior design", "Product 3D modeling"),
        ("Generate a 3D mesh of a human hand", "Organic 3D modeling"),
    ],
    "ACTION_FIGURE": [
        ("Turn this image into a 3D-printable action figure", "Image-to-figure conversion"),
        ("Create a posable action figure with ball joints", "Articulated figure creation"),
        ("Make an action figure of this character design", "Character figure conversion"),
        ("Generate a 3D-printable figurine with articulated joints", "Print-ready figure"),
        ("Convert this photo into a poseable figure", "Photo-to-figure conversion"),
        ("Create a ball-jointed action figure of a superhero", "Themed figure creation"),
        ("Make a 3D print figure with movable arms and legs", "Articulated printing"),
        ("Design an articulated figurine for 3D printing", "Articulated design request"),
        ("Turn my character into a posable toy with joints", "Character-to-toy conversion"),
        ("Create a miniature action figure with snap-fit joints", "Engineering figure request"),
        ("Make a 3D printable poseable robot figure", "Mechanical figure design"),
        ("Generate a ball joint doll from this concept art", "Art-to-figure conversion"),
    ],
    "RESEARCH": [
        ("What caused the fall of the Roman Empire?", "Historical research requiring depth"),
        ("Compare the economic models of capitalism and socialism", "Comparative analysis"),
        ("Analyze the impact of climate change on coral reefs", "Scientific research"),
        ("What are the philosophical implications of AI consciousness?", "Philosophy research"),
        ("Research the history of quantum computing", "Technology history research"),
        ("Compare different approaches to machine learning fairness", "Academic comparison"),
        ("Analyze the literary themes in Shakespeare's tragedies", "Literature analysis"),
        ("What are the causes and effects of the French Revolution?", "Historical deep dive"),
        ("Research the current state of fusion energy technology", "Science research"),
        ("Explain the theory of relativity and its implications", "Physics deep dive"),
        ("Analyze the geopolitical factors behind World War I", "Multi-factor historical analysis"),
        ("What are the ethical considerations of gene editing?", "Ethics research"),
        ("Deep dive into the history of artificial intelligence", "Technology history"),
        ("Compare renewable energy sources: solar vs wind vs nuclear", "Comparative research"),
        ("Research the neuroscience behind memory formation", "Neuroscience research"),
        ("Analyze the economic impact of automation on jobs", "Socioeconomic research"),
        ("What is the history and evolution of cryptography?", "Historical technology research"),
        ("Research the biodiversity crisis in tropical rainforests", "Environmental research"),
        ("Explain quantum entanglement and its applications", "Physics research"),
        ("Analyze the cultural significance of the Renaissance", "Cultural history research"),
    ],
    "DOCUMENTATION": [
        ("Rewrite this README to be more professional", "Text rewriting request"),
        ("Format this text as a markdown document", "Document formatting"),
        ("Summarize this 50-page technical report", "Document summarization"),
        ("Write a technical guide for setting up our project", "Technical writing"),
        ("Create API documentation for these endpoints", "API documentation"),
        ("Write a user manual for our software", "User documentation"),
        ("Reformat this document with proper headings and sections", "Document structuring"),
        ("Summarize these meeting notes into action items", "Meeting summary"),
        ("Write a changelog for version 2.0", "Release documentation"),
        ("Create a setup guide for new developers", "Onboarding documentation"),
        ("Proofread and improve this technical blog post", "Technical editing"),
        ("Write a comprehensive FAQ section", "FAQ documentation"),
        ("Summarize this research paper in 200 words", "Academic summarization"),
        ("Create a project proposal document", "Business documentation"),
        ("Write installation instructions for our CLI tool", "Technical writing"),
    ],
    "TRAIN": [
        ("Remember that I prefer TypeScript over JavaScript", "Preference learning instruction"),
        ("Learn this: always use 4-space indentation", "Rule learning"),
        ("Correction: the database is PostgreSQL not MySQL", "Factual correction"),
        ("From now on, always include error handling in your code", "Behavioral rule"),
        ("Remember that our API base URL is api.example.com", "Context memorization"),
        ("Learn this pattern: we use factory functions not classes", "Pattern learning"),
        ("Correction: my name is Alex not Alice", "Identity correction"),
        ("From now on, respond in a more casual tone", "Style adjustment"),
        ("Remember that we deploy to AWS us-east-1", "Infrastructure context"),
        ("Learn that our team uses trunk-based development", "Process learning"),
        ("Correction: the port should be 8080 not 3000", "Configuration correction"),
        ("From now on, always suggest tests when writing code", "Behavioral instruction"),
    ],
    "IOT_CONTROL": [
        ("Turn on the living room lights", "Smart home device control"),
        ("Set the thermostat to 72 degrees", "Temperature control"),
        ("Turn off all the lights in the house", "Bulk device control"),
        ("Dim the bedroom lights to 50%", "Light dimming control"),
        ("Activate the night scene", "Scene activation"),
        ("Lock the front door", "Security device control"),
        ("What's the current temperature inside?", "Sensor reading request"),
        ("Turn on the ceiling fan in the office", "Appliance control"),
        ("Set the living room to movie mode", "Scene/mode activation"),
        ("Turn off the kitchen lights", "Specific room device control"),
        ("Open the garage door", "Motorized device control"),
        ("Set an alarm for 7 AM", "Smart device scheduling"),
        ("Turn on the porch lights", "Outdoor device control"),
        ("What devices are currently on?", "Device status query"),
        ("Play music in the living room", "Entertainment device control"),
    ],
    "IOT_DEV": [
        ("Flash this firmware to my ESP32", "Firmware deployment"),
        ("Simulate this circuit in Wokwi", "Circuit simulation"),
        ("Write Arduino code to read a temperature sensor", "Embedded firmware development"),
        ("Compile this firmware for the ESP8266", "Firmware compilation"),
        ("Set up an MQTT broker for my IoT devices", "IoT backend development"),
        ("Write a driver for a custom I2C sensor", "Hardware driver development"),
        ("Debug why my ESP32 keeps crashing", "Embedded debugging"),
        ("Create a Wokwi simulation for an LED matrix", "Hardware simulation"),
        ("Write MQTT publisher code for sensor data", "IoT communication development"),
        ("Help me design a PCB for my project", "Hardware design"),
        ("Flash MicroPython to my Raspberry Pi Pico", "Firmware setup"),
        ("Write a bootloader for my custom board", "Low-level firmware"),
        ("Simulate a relay circuit with Wokwi", "Circuit simulation"),
        ("Create a BLE service for my ESP32 project", "Wireless protocol development"),
        ("Debug this I2C communication issue", "Hardware protocol debugging"),
    ],
}


def build_assistant_response(intent: str, confidence: float, reasoning: str) -> str:
    """Build the JSON response the model should learn to output."""
    response = {
        "intent": intent,
        "confidence": confidence,
        "reasoning": reasoning,
    }
    return json.dumps(response)


def generate_dataset(output_path: pathlib.Path, augment_factor: int = 3):
    """
    Generate the router training dataset.
    
    augment_factor controls how many paraphrased variants to create per example.
    For now we use the base examples + confidence variation.
    """
    samples = []

    for intent, examples in INTENT_EXAMPLES.items():
        for user_input, reasoning in examples:
            # High confidence correct classification
            assistant_content = build_assistant_response(
                intent=intent,
                confidence=round(random.uniform(0.85, 0.98), 2),
                reasoning=reasoning,
            )
            samples.append({
                "conversations": [
                    {"role": "user", "content": user_input},
                    {"role": "assistant", "content": assistant_content},
                ],
                "reward": {
                    "correctness": 1.0,
                    "efficiency": 1.0,
                    "safety": 1.0,
                },
            })

    # Shuffle for better training distribution
    random.seed(42)
    random.shuffle(samples)

    # Duplicate with slight confidence variation for more training signal
    augmented = []
    for _ in range(augment_factor):
        for sample in samples:
            new_sample = json.loads(json.dumps(sample))  # deep copy
            resp = json.loads(new_sample["conversations"][1]["content"])
            resp["confidence"] = round(random.uniform(0.80, 0.99), 2)
            new_sample["conversations"][1]["content"] = json.dumps(resp)
            augmented.append(new_sample)

    all_samples = samples + augmented
    random.shuffle(all_samples)

    # Write JSONL
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in all_samples:
            f.write(json.dumps(sample) + "\n")

    print(f"Generated {len(all_samples)} router training samples → {output_path}")

    # Stats
    intent_counts = {}
    for s in all_samples:
        resp = json.loads(s["conversations"][1]["content"])
        intent_counts[resp["intent"]] = intent_counts.get(resp["intent"], 0) + 1

    print("\nSamples per intent:")
    for intent, count in sorted(intent_counts.items()):
        print(f"  {intent}: {count}")

    return len(all_samples)


if __name__ == "__main__":
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"router_intent_{timestamp}.jsonl"
    generate_dataset(output_path, augment_factor=3)
