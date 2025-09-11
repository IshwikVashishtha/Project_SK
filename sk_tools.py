import os
import ast 
import operator
import math , requests
import pandas as pd
from yt_control import YouTubeController
from langchain.agents import Tool
from langchain.tools import tool
from langchain.utilities import WikipediaAPIWrapper, SerpAPIWrapper

# --------------------------------
# 🔧 Utility functions for math
# --------------------------------
operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}

allowed_functions = {
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'log': math.log,
    'log10': math.log10,
    'sqrt': math.sqrt,
    'factorial': math.factorial,
    'floor': math.floor,
    'ceil': math.ceil,
    'abs': abs,
    'round': round
}

allowed_names = {
    'pi': math.pi,
    'e': math.e
}

def safe_eval(node):
    if isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        return operators[type(node.op)](safe_eval(node.left), safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        return operators[type(node.op)](safe_eval(node.operand))
    elif isinstance(node, ast.Call):
        func_name = node.func.id
        if func_name not in allowed_functions:
            raise ValueError(f"Function '{func_name}' is not allowed.")
        args = [safe_eval(arg) for arg in node.args]
        return allowed_functions[func_name](*args)
    elif isinstance(node, ast.Name):
        if node.id in allowed_names:
            return allowed_names[node.id]
        else:
            raise ValueError(f"Name '{node.id}' is not allowed.")
    else:
        raise ValueError(f"Unsupported expression: {type(node)}")

yt = YouTubeController()

# --------------------------------
# 📦 Toolkit Class
# --------------------------------
class AgentTools:
    """Collection of static methods that return ready-to-use LangChain Tools."""

    # 🔧 Calculator Tool
    @staticmethod
    @tool
    def calculator(expression: str) -> str:
        """Evaluate math expressions with +,-,*,/,%,**, sin, cos, sqrt, etc."""
        try:
            parsed = ast.parse(expression, mode='eval')
            result = safe_eval(parsed.body)
            return f"The result of `{expression}` is {result}"
        except Exception as e:
            return f"⚠️ Error: {e}"

    # 📊 CSV Analyzer Tool
    @staticmethod
    @tool
    def analyze_csv(path: str) -> str:
        """Analyze a CSV file and return stats (columns, rows, head)."""
        try:
            df = pd.read_csv(path)
            return f"✅ CSV loaded!\nRows: {len(df)}\nColumns: {list(df.columns)}\nHead:\n{df.head()}"
        except Exception as e:
            return f"⚠️ Error reading CSV: {e}"

    # 📐 Unit Converter Tool
    @staticmethod
    @tool
    def convert_units(text: str) -> str:
        """
        Convert units. Example inputs:
        'Convert 100 cm to m'
        'convert 5 km to m'
        """
        try:
            parts = text.lower().replace("convert", "").strip().split()
            # naive parsing: value, from_unit, to_unit
            value = float(parts[0])
            from_unit = parts[1]
            to_unit = parts[3]
            if from_unit == "cm" and to_unit == "m":
                return f"{value} cm = {value / 100} m"
            elif from_unit == "m" and to_unit == "cm":
                return f"{value} m = {value * 100} cm"
            elif from_unit == "km" and to_unit == "m":
                return f"{value} km = {value * 1000} m"
            elif from_unit == "m" and to_unit == "km":
                return f"{value} m = {value / 1000} km"
            else:
                return f"⚠️ Conversion from {from_unit} to {to_unit} not supported."
        except Exception as e:
            return f"⚠️ Error converting units: {e}"


    # 📚 Wikipedia Tool
    @staticmethod
    def get_wikipedia_tool() -> Tool:
        wiki = WikipediaAPIWrapper()
        return Tool(
            name="Wikipedia",
            func=wiki.run,
            description="Search and summarize information from Wikipedia."
        )

    # 🔎 Search Tool
    @staticmethod
    def get_search_tool() -> Tool | None:
        serp_api_key = os.getenv("SERPAPI_API_KEY")
        if serp_api_key:
            serp = SerpAPIWrapper(serpapi_api_key=serp_api_key)
            return Tool(
                name="Search",
                func=serp.run,
                description="Use for web searches and up-to-date info."
            )
        return None


    # 🌦️ Weather Tool
    @staticmethod
    def get_weather_tool(api_key: str) -> Tool:
        """Return a LangChain Tool for fetching weather information."""
        def fetch_weather(city: str) -> str:
            try:
                url = "https://api.openweathermap.org/data/2.5/weather"
                params = {
                    "q": city,
                    "appid": api_key,
                    "units": "metric"
                }
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                weather_desc = data["weather"][0]["description"].capitalize()
                temp = data["main"]["temp"]
                feels_like = data["main"]["feels_like"]
                humidity = data["main"]["humidity"]
                city_name = data["name"]
                country = data["sys"]["country"]

                return (
                    f"🌤️ Weather in {city_name}, {country}:\n"
                    f"Condition: {weather_desc}\n"
                    f"Temperature: {temp}°C (feels like {feels_like}°C)\n"
                    f"Humidity: {humidity}%"
                )
            except requests.exceptions.RequestException as e:
                return f"⚠️ Weather fetch error: {e}"
            except KeyError:
                return "⚠️ Could not parse weather data. Please check the city name or API key."

        return Tool(
            name="Weather",
            func=fetch_weather,
            description="Get current weather information for a given city."
        )


    @staticmethod
    @tool
    def play_youtube_song_tool(query: str) -> str:
        """Play a song on YouTube based on the given search query."""
        return yt.play_song(query)

    @staticmethod
    @tool
    def youtube_play_pause_tool(dummy: str = "") -> str:
        """Pause or play the video on YouTube in the currently opened window."""
        return yt.play_pause()

    @staticmethod
    @tool
    def youtube_skip_ad_tool(dummy: str = "") -> str:
        """Skip ads on YouTube if a 'Skip Ad' button is present."""
        return yt.skip_ad()
    
    @staticmethod
    def get_all_tools(include_search: bool = True) -> list:
        tools = [
            AgentTools.calculator,
            AgentTools.analyze_csv,
            AgentTools.convert_units,
            AgentTools.get_weather_tool(api_key=os.getenv('WETHER_API_KEY')),
            AgentTools.play_youtube_song_tool,
            AgentTools.youtube_play_pause_tool,
            AgentTools.youtube_skip_ad_tool,
        ]
        if include_search:
            search_tool = AgentTools.get_search_tool()
            if search_tool:
                tools.append(search_tool)
        return tools