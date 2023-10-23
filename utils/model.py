import os
# from langchain.llms import AzureOpenAI
from langchain.chat_models import AzureChatOpenAI
from envconfig import *

# set llm language model
os.environ["OPENAI_API_TYPE"]=OPENAI_API_TYPE
os.environ["OPENAI_API_VERSION"]=OPENAI_API_VERSION
os.environ["OPENAI_API_BASE"]=api_base1
os.environ["OPENAI_API_KEY"]=key1
llm = AzureChatOpenAI(deployment_name=deployment_id, model_name='gpt-35-turbo', temperature=0.2)