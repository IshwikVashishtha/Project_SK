"""
Universal LLM Provider Class
Supports multiple LLM providers with a unified interface
"""

import os
import httpx
from dotenv import load_dotenv
from typing import Optional, Dict, Any, Union

load_dotenv()
from enum import Enum
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_huggingface import ChatHuggingFace
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI


class LLMProvider(Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    GOOGLE_GEMINI = "google_gemini"
    GROQ = "groq"
    HUGGINGFACE = "huggingface"
    google_gemini = "google_gemini"
    OPENROUTER = "openrouter"
    CUSTOM_OPENAI = "custom_openai"  # For OpenAI-compatible APIs


class UniversalLLM:
    """
    Universal LLM class that supports multiple providers.
    
    Usage:
        llm = UniversalLLM(provider=LLMProvider.OPENAI)
        model = llm.get_model()
        
    Environment variables needed (depending on provider):
        - OPENAI_API_KEY
        - ANTHROPIC_API_KEY  
        - GOOGLE_API_KEY
        - GROQ_API_KEY
        - HUGGINGFACEHUB_API_TOKEN
        - OPENROUTER_API_KEY
        - AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT
        - google_gemini_BASE_URL (optional, defaults to http://localhost:11434)
        - CUSTOM_OPENAI_API_KEY, CUSTOM_OPENAI_BASE_URL
    """
    
    def __init__(
        self,
        provider: Union[LLMProvider, str] = LLMProvider.OPENAI,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        **kwargs
    ):
        """
        Initialize the Universal LLM.
        
        Args:
            provider: LLM provider (LLMProvider enum or string)
            model: Model name (provider-specific)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
        """
        self.provider = provider if isinstance(provider, LLMProvider) else LLMProvider(provider.lower())
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs
        self._model_instance = None
        
        # Set default models for each provider if not specified
        if self.model is None:
            self.model = self._get_default_model()
    
    def _get_default_model(self) -> str:
        """Get default model for each provider"""
        defaults = {
            LLMProvider.OPENAI: "gpt-4o",
            LLMProvider.AZURE_OPENAI: "",  # Must be specified for Azure
            LLMProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
            LLMProvider.GOOGLE_GEMINI: "",
            LLMProvider.GROQ: "",
            LLMProvider.HUGGINGFACE: "google/flan-t5-xxl",
            LLMProvider.google_gemini: "llama2",
            LLMProvider.OPENROUTER: "openai/gpt-3.5-turbo",
            LLMProvider.CUSTOM_OPENAI: "deepseek"
        }
        return defaults.get(self.provider, "")
    
    def _get_http_client(self) -> Optional[httpx.Client]:
        """Create HTTP client with optional certificate verification"""
        cert_path = self.kwargs.get("cert_path")
        if cert_path and os.path.exists(cert_path):
            return httpx.Client(verify=cert_path, timeout=30.0)
        return None
    
    def _get_async_http_client(self) -> Optional[httpx.AsyncClient]:
        """Create async HTTP client with optional certificate verification"""
        cert_path = self.kwargs.get("cert_path")
        if cert_path and os.path.exists(cert_path):
            return httpx.AsyncClient(verify=cert_path, timeout=30.0)
        return None
    
    def get_model(self):
        """Get the LangChain model instance for the configured provider"""
        if self._model_instance is not None:
            return self._model_instance
            
        common_params = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **self.kwargs
        }
        
        # Remove our custom parameters from common_params
        common_params.pop("cert_path", None)
        
        if self.provider == LLMProvider.OPENAI:
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY or API_KEY environment variable is required")
            
            self._model_instance = ChatOpenAI(
                api_key=api_key,
                model=self.model,
                **common_params
            )
            
        elif self.provider == LLMProvider.AZURE_OPENAI:
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT") or self.model
            
            if not all([api_key, endpoint, deployment]):
                raise ValueError("AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT environment variables are required")
            
            self._model_instance = AzureChatOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                azure_deployment=deployment,
                api_version="2024-02-15-preview",
                **common_params
            )
            
        elif self.provider == LLMProvider.ANTHROPIC:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable is required")
            
            self._model_instance = ChatAnthropic(
                api_key=api_key,
                model=self.model,
                **common_params
            )
            
        elif self.provider == LLMProvider.GOOGLE_GEMINI:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable is required")
            
            self._model_instance = ChatGoogleGenerativeAI(
                api_key=api_key,
                model=self.model,
                **common_params
            )
            
        elif self.provider == LLMProvider.GROQ:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable is required")
            
            self._model_instance = ChatGroq(
                api_key=api_key,
                model_name=self.model,
                **common_params
            )
            
        elif self.provider == LLMProvider.HUGGINGFACE:
            api_key = os.getenv("HUGGINGFACEHUB_API_TOKEN")
            if not api_key:
                raise ValueError("HUGGINGFACEHUB_API_TOKEN environment variable is required")
            
            # Note: Hugging Face might require additional setup
            from langchain_huggingface import HuggingFaceEndpoint
            
            self._model_instance = ChatHuggingFace(
                llm=HuggingFaceEndpoint(
                    repo_id=self.model,
                    huggingfacehub_api_token=api_key,
                    **common_params
                )
            )
            
        elif self.provider == LLMProvider.google_gemini:
            base_url = os.getenv("google_gemini_BASE_URL", "http://localhost:11434")
            
            self._model_instance = ChatGoogleGenerativeAI(
                base_url=base_url,
                model=self.model,
                **common_params
            )
            
        elif self.provider == LLMProvider.OPENROUTER:
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY environment variable is required")
            
            self._model_instance = ChatOpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                model=self.model,
                default_headers={
                    "HTTP-Referer": os.getenv("OPENROUTER_REFERRER", "https://github.com"),
                    "X-Title": os.getenv("OPENROUTER_APP_TITLE", "DVWA Agent"),
                },
                **common_params
            )
            
        elif self.provider == LLMProvider.CUSTOM_OPENAI:
            api_key = os.getenv("CUSTOM_OPENAI_API_KEY") or os.getenv("API_KEY")
            base_url = os.getenv("CUSTOM_OPENAI_BASE_URL")
            
            if not api_key:
                raise ValueError("CUSTOM_OPENAI_API_KEY or API_KEY environment variable is required")
            if not base_url:
                raise ValueError("CUSTOM_OPENAI_BASE_URL environment variable is required")
            
            http_client = self._get_http_client()
            async_http_client = self._get_async_http_client()
            
            self._model_instance = ChatOpenAI(
                api_key=api_key,
                base_url=base_url,
                model=self.model,
                http_client=http_client,
                http_async_client=async_http_client,
                **common_params
            )
            
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        return self._model_instance
    
    def tool_binding(self, tools):
        """Bind tools to the model (for agent use)"""
        model = self.get_model()
        return model.bind_tools(tools)
    
    def get_llm(self):
        """Alias for get_model() for backward compatibility"""
        return self.get_model()
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]):
        """Create UniversalLLM from configuration dictionary"""
        return cls(**config)
    
    @classmethod
    def get_available_providers(cls):
        """Get list of available provider names"""
        return [provider.value for provider in LLMProvider]


# # Example usage and backward compatibility
# if __name__ == "__main__":
#     # Example 1: Using OpenAI
#     llm = UniversalLLM(provider="openai", model="gpt-4o", temperature=0.7)
#     model = llm.get_model()
#     print(f"Created OpenAI model: {model}")
    
#     # Example 2: Using google_gemini
#     llm2 = UniversalLLM(provider="google_gemini", model="llama2")
#     model2 = llm2.get_model()
#     print(f"Created google_gemini model: {model2}")
    
#     # Example 3: Using custom OpenAI-compatible API (like current setup)
#     llm3 = UniversalLLM(
#         provider="custom_openai",
#         model="deepseek",
#         cert_path="C:\\Users\\rogers\\Desktop\\dvwa_agent\\ca.crt"
#     )
#     model3 = llm3.get_model()
#     print(f"Created custom OpenAI model: {model3}")