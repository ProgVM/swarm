import json
from swarm.core import SwarmSession

# Mock class for arguments
class Args:
    def __init__(self):
        self.agents_count = 2
        self.model = "gemini-3.1-flash-lite"
        self.first_msg = "Test"
        self.no_pause = True

# Simulation of a broken session state
def test_index_out_of_bounds():
    args = Args()
    keys = ["fake_key"]
    session = SwarmSession(args, keys)
    
    # Simulate a situation where the saved index is greater than the number of agents
    session.current_agent_idx = 99 
    
    # Call session index validation, which should reset the index to 0
    session.validate_indices()
    
    assert session.current_agent_idx == 0
    # Check that accessing the current agent is now safe
    agent = session.agents[session.current_agent_idx]
    assert agent is not None
    assert agent.name == "Agent_1"
