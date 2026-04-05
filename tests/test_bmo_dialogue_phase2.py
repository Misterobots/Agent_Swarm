import pytest
from agents.specialized.voice_assistant import VoiceAssistantAgent, Message

@pytest.fixture
def agent():
    return VoiceAssistantAgent(user_id="test_user")

def test_multi_turn_coherence(agent):
    # Simulate a multi-turn conversation about lights
    turns = [
        ("Turn on the bedroom light", "Turned on light.bedroom"),
        ("Make it blue", "Turned on light.bedroom with blue color"),
        ("What about the kitchen?", "Turned on light.kitchen"),
        ("Turn it off", "Turned off light.kitchen"),
    ]
    for user, expected in turns:
        msg = Message(role="user", content=user)
        response = agent.process(msg)
        assert expected.split()[0] in response.content  # Basic check


def test_reference_resolution(agent):
    # User gives name, then asks for it
    agent.process(Message(role="user", content="My name is Finn"))
    agent.end_session()
    agent2 = VoiceAssistantAgent(user_id="test_user")
    response = agent2.process(Message(role="user", content="What's my name?"))
    assert "Finn" in response.content


def test_clarification_request(agent):
    # Ambiguous command triggers clarification
    response = agent.process(Message(role="user", content="Turn on the light"))
    if agent.dialogue.state.pending_clarification:
        assert "which room" in agent.dialogue.state.clarification_context.lower() or "which device" in agent.dialogue.state.clarification_context.lower()