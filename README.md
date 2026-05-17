# 🐝 Swarm Intelligence Framework

[![PyPI version](https://img.shields.io/pypi/v/swarmai.svg)](https://pypi.org/project/swarmai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/ProgVM/swarm.svg)](https://github.com/ProgVM/swarm/stargazers)

**Swarm** is a professional, highly flexible multi-agent intelligence framework powered by Google's **Gemini 3.1 Flash Lite**. It allows an arbitrary number of autonomous agents to collaborate, use system tools, execute code, and perform web searches in a shared environmental context.

## 🚀 Key Features

- **N-Agent Support**: Run as many agents as your tasks require.
- **Autonomous Toolchain**: Agents use `web_search` and `shell_exec` to solve complex problems.
- **Dynamic Configuration**: Configure any agent parameter (name, model, temperature, system prompt) directly via CLI flags.
- **Handover Logic**: Agents can autonomously pass control to specific peers using the `pass_turn` tool.
- **Shared Environment**: Tool execution outputs are shared with all agents via automatic **System Reports**.
- **Files API Integration**: Agents can upload and analyze local files (PDFs, images, logs) on the fly.
- **Smart Sandboxing**: Per-agent regex blacklists for terminal commands and file system paths.
- **Persistent Sessions**: Save and load complete Swarm states, including histories and turn orders.

## 🛠 Installation

```bash
pip install swarmai
```
*Requires Python 3.9+ and a Google Gemini API Key.*

## 💻 Quick Start

### Basic Two-Agent Discussion
```bash
swarm --keys YOUR_API_KEY --agents_count 2
```

### Autonomous Developer & Auditor
```bash
swarm --keys YOUR_API_KEY \
      --first_msg "Write a secure Python data scraper" \
      --ai1_name "Dev" --ai1_sys "You are a senior coder." \
      --ai2_name "Security" --ai2_sys "You look for vulnerabilities."
```

## ⚙️ Advanced CLI Configuration

Swarm uses a dynamic argument system. You can prefix any standard parameter with `aiN_` to target a specific agent:

- `--ai1_model "gemini-1.5-pro"` (Use a heavier model for the lead agent)
- `--ai2_temp 0.1` (Make the auditor more deterministic)
- `--ai3_name "Researcher"` (Set a custom name for the 3rd agent)
- `--cmd_blacklist "rm" "sudo"` (Global security policy)

### Global Parameters:
- `--agents_count`: Number of agents in session (default: 2).
- `--log_level`: DEBUG, INFO, or WARNING.
- `--no_pause`: Disable "Press Enter" delays for fully autonomous runs.
- `--config`: Path to a JSON file containing all these parameters.

## ⌨️ Command Center (Ctrl+C)

Press `Ctrl+C` during execution to pause the Swarm and access the interactive menu:
1. **Change Keys**: Rotate or update API keys on the fly.
2. **Toggle Pauses**: Switch between manual and autonomous modes.
3. **Save State**: Export the entire session to a JSON file.
4. **Inject Directive**: Manually "whisper" a command to one or all agents.
5. **Log Level**: Adjust verbosity without restarting.

## 📄 Tool Documentation

- **web_search**: Browses the web for real-time data.
- **shell_exec**: Runs bash commands. Supports complex multi-line scripts.
- **upload_file**: Uploads local assets to the AI context.
- **pass_turn**: Moves the turn to a specific agent by name.

## 🤝 Contributing

Swarm is maintained by **ProgVM**. 
- **GitHub**: [https://github.com/ProgVM](https://github.com/ProgVM)
- **Email**: [progvminc@gmail.com](mailto:progvminc@gmail.com)

Feel free to open issues or submit pull requests for new features!

*License: MIT*
