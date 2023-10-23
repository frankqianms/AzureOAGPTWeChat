# agents
from utils.agent import create_agent

from langchain.memory import ConversationBufferMemory

class AIAsker:
    def __init__(self):
        self._chat_history = []
        self._answer = None
        self._memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        self._agent = None

    def askGPT(self, query: str):
        self._chat_history = [(query, self._answer if self._answer else "")]
        if self._agent is None:
            self._agent = create_agent()
            
        self._answer = self._agent.run(query)
        return self._answer
