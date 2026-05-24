from google.genai import types
from swarm.core import clean_history, safe_append_to_history

def test_clean_history_consecutive_roles():
    history = [
        types.Content(role="user", parts=[types.Part(text="Hello")]),
        types.Content(role="user", parts=[types.Part(text="World")]),
        types.Content(role="model", parts=[types.Part(text="AI response")]),
        types.Content(role="model", parts=[types.Part(text="More AI response")]),
    ]
    
    cleaned = clean_history(history)
    assert len(cleaned) == 2
    assert cleaned[0].role == "user"
    assert len(cleaned[0].parts) == 2
    assert cleaned[0].parts[0].text == "Hello"
    assert cleaned[0].parts[1].text == "World"
    
    assert cleaned[1].role == "model"
    assert len(cleaned[1].parts) == 2
    assert cleaned[1].parts[0].text == "AI response"
    assert cleaned[1].parts[1].text == "More AI response"

def test_clean_history_with_dicts():
    history = [
        {"role": "user", "parts": ["hello"]},
        {"role": "user", "parts": ["there"]},
    ]
    cleaned = clean_history(history)
    assert len(cleaned) == 1
    assert cleaned[0]["role"] == "user"
    assert cleaned[0]["parts"] == ["hello", "there"]

def test_safe_append_to_history():
    history = []
    
    # 1. Append to empty history
    safe_append_to_history(history, "user", [types.Part(text="First msg")])
    assert len(history) == 1
    assert history[0].role == "user"
    assert history[0].parts[0].text == "First msg"
    
    # 2. Append same role
    safe_append_to_history(history, "user", [types.Part(text="Second msg")])
    assert len(history) == 1
    assert len(history[0].parts) == 2
    assert history[0].parts[1].text == "Second msg"
    
    # 3. Append different role
    safe_append_to_history(history, "model", [types.Part(text="Model response")])
    assert len(history) == 2
    assert history[1].role == "model"
    assert len(history[1].parts) == 1
