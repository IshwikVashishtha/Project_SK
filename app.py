import streamlit as st
import json
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import OllamaLLM
from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory, CombinedMemory
from langchain.chains import LLMChain
# Optional: Web search
try:
    from langchain.utilities import SerpAPIWrapper
    from langchain.agents import initialize_agent, Tool
    from langchain.agents import AgentType
    SERPAPI_KEY = os.getenv("SERPAPI_API_KEY" , "58a0267ad1a9fcd13ff6f818918cd0b9d2a462d3d678bb247d9deff1ec5bf8af")  # Set your SerpAPI key in env
    serp = SerpAPIWrapper(serpapi_api_key=SERPAPI_KEY) if SERPAPI_KEY else None
except Exception as e:
    serp = None

# ---------------------------
# ✅ Backend logic directly here
# ---------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.5:11434")
MAIN_MODEL = os.getenv("OLLAMA_MAIN_MODEL", "gemma2:2b")
SUMMARY_MODEL = os.getenv("OLLAMA_SUMMARY_MODEL", "phi3")

llm = OllamaLLM(model=MAIN_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.2, top_p=0.9, streaming=True)
summary_llm = OllamaLLM(model=SUMMARY_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.2, top_p=0.9, streaming=False)

system_prompt = """
You are EduBot, a friendly and knowledgeable AI friend. Explain in simple language, use examples, be positive.
"""
template = f"""
System Prompt:
{system_prompt}

Past conversation:
{{message_buffer_log}}

Conversation summary:
{{message_summary_log}}

Question: {{question}}

Answer:
"""
prompt = ChatPromptTemplate.from_template(template)

buffer_memory = ConversationBufferMemory(memory_key="message_buffer_log", input_key="question", return_messages=False)
summary_memory = ConversationSummaryMemory(llm=summary_llm, memory_key="message_summary_log", input_key="question", return_messages=False)
combined_memory = CombinedMemory(memories=[summary_memory, buffer_memory])
chat_chain = LLMChain(llm=llm, prompt=prompt, memory=combined_memory, output_parser=StrOutputParser())

def ask_question(question: str, use_stream: bool = True, use_search: bool = True) -> str:
    # logger.info(f"Asking: {question}")
    if use_search and serp:
        tools = [Tool(name="Search", func=serp.run, description="useful for web search")]
        agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)
        return agent.run(question)
    if use_stream:
        response = ""
        for chunk in chat_chain.stream({"question": question}):
            text = chunk.get("text", "")
            print(text, end="", flush=True)
            response += text
        print()
        # save_memory()
        return response
    else:
        result = chat_chain.invoke({"question": question})
        # save_memory()
        return result["text"]
# ---------------------------
# ✅ Streamlit UI
# ---------------------------
st.set_page_config(page_title="EduBot Chatbot", page_icon="🤖", layout="centered")
st.title("EduBot 🤖💬")
st.write("Your friendly knowledgeable AI friend.")

if "history" not in st.session_state:
    st.session_state.history = []

question = st.text_input("Ask me anything:")

if st.button("Send"):
    if question:
        answer = ask_question(question)
        st.session_state.history.append(("You", question))
        st.session_state.history.append(("EduBot", answer))

for role, msg in st.session_state.history:
    st.markdown(f"**{role}:** {msg}")
