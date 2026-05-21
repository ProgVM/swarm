import json
from swarm.core import SwarmSession

# Mock-класс для аргументов
class Args:
    def __init__(self):
        self.agents_count = 2
        self.model = "gemini-3.1-flash-lite"
        self.first_msg = "Test"
        self.no_pause = True

# Имитация битого состояния сессии
def test_index_out_of_bounds():
    args = Args()
    keys = ["fake_key"]
    session = SwarmSession(args, keys)
    
    # Имитируем ситуацию, когда сохраненный индекс больше количества агентов
    session.current_agent_idx = 99 
    
    # Вызываем валидацию индексов сессии, которая должна вернуть индекс к 0
    session.validate_indices()
    
    assert session.current_agent_idx == 0
    # Проверяем, что теперь доступ к текущему агенту безопасен
    agent = session.agents[session.current_agent_idx]
    assert agent is not None
    assert agent.name == "Agent_1"
