This repository contains my hands-on implementation of the course material.

The instructor used the OpenAI toolkit, and for the memory component I followed the same implementation approach used in the course project. While the instructor worked with Anaconda and pip, I chose to use uv along with VS Code. Some configuration steps—such as setting up the OpenAI API key environment variables—were assisted by GitHub Copilot.

Certain files (e.g., .env) have been intentionally excluded via .gitignore for security and best practices.

Since MCP strongly adopts uv, I followed the same workflow using common uv commands like sync, add, and venv, which I found straightforward and efficient.

Python is not my primary language, so I approached this as a learning exercise. I used tools like ChatGPT and Google AI to better understand the flow and logic of various methods. For example, the following async pattern initially required deeper exploration:

events = await asyncio.to_thread(
    self._client.list_events,
    memory_id=self.memory_id,
    actor_id=self.actor_id,
    session_id=self.session_id,
    branch_name=self._current_branch or None,
    max_results=100,
    include_payload=True,
)
