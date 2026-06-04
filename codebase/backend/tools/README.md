# Chatbot Tools

This folder contains local tools that the `/api/chat` endpoint can call before asking Ollama for a response.

- `learner_profile.py`: adds user, quiz, provider, and model context.
- `roadmap_lookup.py`: reads the default roadmap from `frontend/src/app_data.json`.
- `roadmap_modifier.py`: modifies the visible learning roadmap from the user's chat request.
- `resource_recommender.py`: suggests learning resources based on the user's topic.
- `progress_summary.py`: summarizes recent chat and quiz progress.
- `roadmap_data.py`: shared helper for loading/cloning roadmap data.

`chat_tools.py` is now only the registry/orchestration layer. The chat endpoint uses
`select_chat_tools()`, `run_chat_tools()`, and `format_tool_context()` from that file.
