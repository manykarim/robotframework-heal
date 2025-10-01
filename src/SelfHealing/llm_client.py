import httpx
import os
from dotenv import load_dotenv, find_dotenv
import base64
import litellm
from litellm import completion
from robot.api import logger

env_file = find_dotenv()
if env_file:
    print(f"Loading .env from: {os.path.abspath(env_file)}")
    load_dotenv(env_file, override=True)
else:
    print("No .env file found in current directory or parent directories")

LLM_API_KEY = os.environ.get('LLM_API_KEY', None)
LLM_API_BASE = os.environ.get('LLM_API_BASE', None)
LLM_TEXT_MODEL = os.environ.get('LLM_TEXT_MODEL', "ollama_chat/llama3.1")
LLM_LOCATOR_MODEL = os.environ.get('LLM_LOCATOR_MODEL', "ollama_chat/llama3.1")
LLM_VISION_MODEL = os.environ.get('LLM_VISION_MODEL', "ollama_chat/llama3.2-vision")

if LLM_API_KEY:
    litellm.api_key = LLM_API_KEY
if LLM_API_BASE:
    litellm.api_base = LLM_API_BASE