# Project_SK: A Multi-Modal AI Assistant

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-blueviolet)](https://www.langchain.com/)
[![Ollama](https://img.shields.io/badge/Ollama-orange)](https://ollama.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-red)](https://streamlit.io/)

**Project_SK** is a powerful, voice-activated AI assistant built with Python, LangChain, and local Large Language Models (LLMs). It's designed to be a versatile companion that can understand voice commands, reason about tasks, use a variety of tools to interact with the digital world, and hold context-aware conversations.

The entire system runs locally using **Ollama**, ensuring complete privacy, no API costs, and full control over your data.

---

## 🚀 Key Features

-   **🗣️ Voice-Activated Control:** Hands-free interaction using a customizable wake word for commands.
-   **🤖 Multi-Modal Interaction:** Supports both voice (speech-to-text, text-to-speech) and text-based (Streamlit UI) communication.
-   **🧠 Local LLM Powered:** Leverages Ollama to run powerful open-source models like `gemma2` and `phi3` locally, eliminating API costs and privacy concerns.
-   **🛠️ Agentic Tool Use:** The AI can autonomously use a suite of tools to perform actions:
    -   **Web Search:** Access up-to-date information from the internet via SerpAPI.
    -   **YouTube Control:** Search and play videos, pause/resume, and even skip ads using Selenium.
    -   **Information Retrieval:** Get current weather updates and fetch summaries from Wikipedia.
    -   **Data & Math:** Solve complex mathematical expressions and perform quick analysis on CSV files.
-   **💬 Intelligent Conversation Memory:** Utilizes a combination of buffer and summary memory to maintain context over long conversations, with the state persisted to a local file.
-   **🌐 Simple Web Interface:** A clean and functional web UI built with Streamlit for easy text-based chatting.

---

## 🛠️ Tech Stack

-   **Core:** Python, LangChain
-   **LLMs:** Ollama (with models like `gemma2:2b`, `phi3`)
-   **Voice:** `speech_recognition`, `pyttsx3`
-   **Web UI:** Streamlit
-   **Tooling:** Selenium (for YouTube), Pandas (for CSV), Requests
-   **APIs:** SerpAPI (for search), OpenWeatherMap (for weather)

---

## 📂 Project Structure

```
project_SK/
├── app.py                  # Streamlit web application for text-based chat
├── fullworking_chatbot.ipynb # Jupyter Notebook with the full voice agent logic
├── sk_listen.py            # Handles wake-word detection and speech-to-text
├── sk_speak.py             # Handles text-to-speech conversion
├── sk_tools.py             # Defines the suite of tools for the LangChain agent
├── yt_control.py           # Manages Selenium-based YouTube browser automation
├── chat_memory.json        # Stores conversation history to maintain context
└── README.md               # You are here!
```

---

## ⚙️ Setup and Installation

Follow these steps to get Project_SK running on your local machine.

### Prerequisites

-   Python 3.9+
-   Ollama installed and running.
-   Google Chrome browser (for Selenium-based YouTube control).
-   A working microphone for voice commands.

### Installation Steps

1.  **Clone the Repository**

    ```bash
    git clone https://github.com/IshwikVashishtha/Project_SK.git
    cd Project_SK
    ```

2.  **Create a Virtual Environment**

    ```bash
    # For Windows
    python -m venv .venv
    .\.venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Dependencies**

    Create a `requirements.txt` file with the following content:

    ```txt
    langchain
    langchain-core
    langchain-ollama
    streamlit
    speechrecognition
    pyttsx3
    PyAudio
    selenium
    pandas
    requests
    wikipedia
    google-search-results
    ```

    Then, install them using pip:

    ```bash
    pip install -r requirements.txt
    ```

4.  **Pull Ollama Models**

    Run the following commands in your terminal to download the required LLMs:

    ```bash
    ollama pull gemma2:2b
    ollama pull phi3
    ```

5.  **Set Up Environment Variables**

    Create a file named `.env` in the root of the project directory and add your API keys and local configuration.

    ```env
    # .env

    # Your machine's local IP where Ollama is running
    OLLAMA_BASE_URL="http://192.168.8.4:11434"

    # API key for web search (get one from https://serpapi.com/)
    SERPAPI_API_KEY="your_serpapi_key_here"

    # API key for weather (get one from https://openweathermap.org/api)
    WETHER_API_KEY="your_openweathermap_key_here"
    ```

    *Note: Replace `192.168.1.5` with your machine's actual local IP address.*

---

## ▶️ How to Run

### 1. Voice-Activated Assistant

The primary logic for the voice assistant is contained within `fullworking_chatbot.ipynb`.

1.  Start a Jupyter server: `jupyter notebook`
2.  Open `fullworking_chatbot.ipynb`.
3.  Run the cells in order. The last cell will start the listener.
4.  The console will print `🎤 Listening continuously...`. You can now use the wake word.

**Usage Example:**
> "Jarvis, what's the weather like in New York?"

> "Jarvis, play a song by Arijit Singh on YouTube."

> "Jarvis, what is 5 factorial?"

### 2. Streamlit Web App (Text-Only)

For a simple, text-based chat interface, run the Streamlit app.

```bash
streamlit run app.py
```

This will open a new tab in your browser where you can chat with the AI.