import logging
import os
import warnings

import litellm
from dotenv import find_dotenv, load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
# Suppress LiteLLM INFO messages
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
# Suppress httpx INFO messages
logging.getLogger("httpx").setLevel(logging.WARNING)

litellm.suppress_debug_info = True

# Suppress specific Pydantic UserWarning from LiteLLM, which is noisy as of v1.72.6
# See: https://github.com/BerriAI/litellm/issues/11759
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings.*",
    category=UserWarning,
)

env_file = find_dotenv()
if env_file:
    load_dotenv(env_file, override=True)

LLM_API_KEY = os.environ.get("LLM_API_KEY", None)
LLM_API_BASE = os.environ.get("LLM_API_BASE", None)
LLM_TEXT_MODEL = os.environ.get("LLM_TEXT_MODEL", "ollama_chat/llama3.1")
LLM_LOCATOR_MODEL = os.environ.get("LLM_LOCATOR_MODEL", "ollama_chat/llama3.1")
LLM_VISION_MODEL = os.environ.get("LLM_VISION_MODEL", "ollama_chat/llama3.2-vision")

if LLM_API_KEY:
    litellm.api_key = LLM_API_KEY
if LLM_API_BASE:
    litellm.api_base = LLM_API_BASE
