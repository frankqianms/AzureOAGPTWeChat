from langchain.agents import load_tools, initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from utils.model import llm

## conversational agent
def create_agent(tool):
    tools = load_tools(["bing-search", "llm-math"], llm=llm)
    tools.append(tool)
    memory = ConversationBufferMemory(memory_key="chat_history")
    agent_chain = initialize_agent(tools, llm, agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION, verbose=True, memory=memory, handle_parsing_errors=True)
    agent = agent_chain
    return agent
