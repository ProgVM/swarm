# 🐝 Swarm

**Swarm** is an advanced, open-source multi-agent intelligence framework designed for autonomous collaboration. Powered by Google's **Gemini 3.1 Flash Lite**, Swarm allows multiple agents to interact, use tools, execute code, and perform web searches in a shared environment.

## 🚀 Key Features

- **N-Agent Collaboration**: Run any number of agents in a single session.
- **Autonomous Tool Usage**: Agents can perform Google searches and execute Shell commands.
- **Agent Sandboxing**: Per-agent blacklists for terminal commands and file paths.
- **Turn Management**: Agents can autonomously pass turns to specific peers using `pass_turn`.
- **ReAct Loop**: High-level reasoning before acting, supporting multi-step tool execution.
- **Files API Support**: Agents can upload and analyze PDF, images, and logs via Google Files API.
- **Persistent Sessions**: Save and load full agent histories and environment states.

## 🛠 Installation

```bash
# Clone the repository
git clone https://github.com/ProgVM/swarm
cd swarm

# Install dependencies
pip install .
```

Or:
```bash
pip install swarmai
```

## 💻 CLI Usage

Start a basic conversation with two agents:
```bash
swarm --keys YOUR_API_KEY --agents_count 2
```

Start an autonomous coding session:
```bash
swarm --first_msg "Write a web scraper in Python and test it" \
      --sys1 "You are an Expert Coder" \
      --sys2 "You are a Security Auditor" \
      --cmd_timeout 600
```

### Advanced Configuration
Swarm supports individual parameters for every agent using `aiN_` prefixes:
- `--ai1_name "Architect"`
- `--ai1_model "gemini-2.0-flash"`
- `--ai2_name "Tester"`
- `--ai2_temp 0.2`

## ⚙️ Configuration File
You can use a JSON config to manage complex Swarms:
```json
{
  "agents_count": 3,
  "model": "gemini-3.1-flash-lite",
  "cmd_blacklist": ["rm -rf", "format"],
  "no_pause": true
}
```
Run with: `swarm --config my_swarm.json`

## ⌨️ Command Center (Interactive Menu)
Press `Ctrl+C` at any time to:
- Rotate API Keys.
- Toggle reading pauses.
- Save the current state.
- Change logging levels (DEBUG, INFO, WARNING).
- Inject manual directives into agents' minds.

## 🤝 Contributing
Developed by **ProgVM**. 
- Email: progvminc@gmail.com
- GitHub: [https://github.com/ProgVM](https://github.com/ProgVM)

License: MIT
