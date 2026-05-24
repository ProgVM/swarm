import pytest
from swarm.core import SwarmSession, Agent

class MockArgs:
    def __init__(self):
        self.agents_count = 2
        self.model = "gemini-3.1-flash-lite"
        self.first_msg = "Hello"
        self.no_pause = True
        self.max_history = 10

def test_global_message_injection():
    args = MockArgs()
    keys = ["fake_key"]
    session = SwarmSession(args, keys)
    
    # Inject message globally
    res = session.inject_message("Globally injected msg")
    assert "Message injected globally" in res
    assert session.last_interaction == "Globally injected msg"
    
    # Verify it is appended to current agent's history (Agent_1 is index 0)
    agent1 = session.agents[0]
    assert len(agent1.history) == 1
    assert agent1.history[0].parts[0].text == "Globally injected msg"

def test_targeted_message_injection_by_id():
    args = MockArgs()
    keys = ["fake_key"]
    session = SwarmSession(args, keys)
    
    # Inject to Agent_2 (ID 2)
    res = session.inject_message("Hello Agent 2", targets="2")
    assert "Message injected to agent(s): Agent_2" in res
    
    # Verify current agent switched to index 1 (Agent_2)
    assert session.current_agent_idx == 1
    assert session.last_interaction == "Hello Agent 2"
    
    # Verify history of Agent_2 has the message
    agent2 = session.agents[1]
    assert len(agent2.history) == 1
    assert agent2.history[0].parts[0].text == "Hello Agent 2"

def test_targeted_message_injection_by_name():
    args = MockArgs()
    keys = ["fake_key"]
    session = SwarmSession(args, keys)
    
    # Inject to Agent_1 by name
    res = session.inject_message("Hello Agent 1", targets="Agent_1")
    assert "Message injected to agent(s): Agent_1" in res
    assert session.current_agent_idx == 0
    assert session.last_interaction == "Hello Agent 1"
    
    agent1 = session.agents[0]
    assert len(agent1.history) == 1
    assert agent1.history[0].parts[0].text == "Hello Agent 1"

def test_targeted_multiple_agents():
    args = MockArgs()
    keys = ["fake_key"]
    session = SwarmSession(args, keys)
    
    # Inject to both Agents
    res = session.inject_message("Group instruction", targets="Agent_1, 2")
    assert "Agent_1" in res
    assert "Agent_2" in res
    
    # Verify both got the message
    assert len(session.agents[0].history) == 1
    assert session.agents[0].history[0].parts[0].text == "Group instruction"
    assert len(session.agents[1].history) == 1
    assert session.agents[1].history[0].parts[0].text == "Group instruction"
    
    # Active agent should switch to the first matched target (Agent_1)
    assert session.current_agent_idx == 0
