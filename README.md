This is my code along hands on for the course. Instructor used openai tool kit so for memory part used same memory inplementaion which was used in project. Instructor used anoconda and pip i used uv and vscode and few potions were created by copiolot for open ai key to set envoronment. i did put few file i gitignored like .env, sINCE mcp highly adopts UV so i used same setting with typicl uv commans like sync,add, venv etc esay to use. Python is not my primary language so an honest approch to lear or used chatgpt google ai tool to understand flow or logic of method used like following like stumbled me
vents = await asyncio.to_thread(
            self._client.list_events,
            memory_id=self.memory_id,
            actor_id=self.actor_id,
            session_id=self.session_id,
            branch_name=self._current_branch or None,
            max_results=100,
            include_payload=True,
        )
