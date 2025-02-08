import httpx
import os
from dotenv import load_dotenv
import base64
import litellm
from litellm import completion

load_dotenv()

LLM_API_KEY = os.environ.get('LLM_API_KEY', None)
LLM_API_BASE = os.environ.get('LLM_API_BASE', None)
LLM_TEXT_MODEL = os.environ.get('LLM_TEXT_MODEL', "ollama_chat/llama3.1")
LLM_LOCATOR_MODEL = os.environ.get('LLM_LOCATOR_MODEL', "ollama_chat/llama3.1")
LLM_VISION_MODEL = os.environ.get('LLM_VISION_MODEL', "ollama_chat/llama3.2-vision")

if LLM_API_KEY:
    litellm.api_key = LLM_API_KEY
if LLM_API_BASE:
    litellm.api_base = LLM_API_BASE