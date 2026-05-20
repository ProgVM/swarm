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
    
    try:
        agent = session.agents[session.current_agent_idx]
        print(f"Ошибка не воспроизведена: {agent.name}")
    except IndexError:
        print("Баг подтвержден: IndexError при доступе к агенту с неверным индексом.")

if __name__ == "__main__":
    test_index_out_of_bounds()
