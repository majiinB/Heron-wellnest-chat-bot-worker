"""
Google Generative AI Configuration Module

@file gemini_config.py
@description This module sets up and exports configurations for interacting with Google's Generative AI,
specifically the Gemini model. It initializes essential objects such as `Client` to manage generative tasks.
Additionally, it defines configuration options to fine-tune generation outputs.

External Dependencies:
- google.genai: Provides access to Google's Generative AI SDK.
- app.config.env_config: Loads validated environment variables.

Key Exports:
- `client`: An instance of genai.Client for interacting with AI models.
- `get_model`: Factory function to get a configured Gemini model instance.
- `default_generation_config`: Default configuration for AI generation outputs.
- `safety_settings`: Safety settings to filter harmful content.

Usage:
- Import these exports in the relevant parts of your project where generative AI features are needed.
- Ensure the `.env` file contains the required `GEMINI_API_KEY` to avoid runtime issues.

@module gemini_config

@author Arthur M. Artugue
@created 2026-01-10
@updated 2026-01-10
"""

from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
from app.config.env_config import env


# Initialize the Gemini AI client with the API key from environment
client = genai.Client(api_key=env.GEMINI_API_KEY)


# Safety settings to control harmful content filtering
safety_settings: List[types.SafetySetting] = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
]


# Default generation configuration
default_generation_config = types.GenerateContentConfig(
    temperature=0.8,           # Randomness level for response generation (0.0 - 2.0)
    top_p=0.95,               # Nucleus sampling threshold
    top_k=64,                 # Top-K sampling limit
    max_output_tokens=8192,   # Maximum number of tokens in the output
    response_mime_type="application/json"  # MIME type of the generated response
)


def get_model(
    model: str = "gemini-2.5-flash",
    temperature: float = 0.8,
    top_p: float = 0.95,
    top_k: int = 64,
    max_output_tokens: int = 8192,
    response_mime_type: str = "application/json",
    response_schema: Optional[Dict[str, Any]] = None,
    system_instruction: Optional[str] = None,
    enable_safety_settings: bool = False
) -> tuple[str, types.GenerateContentConfig]:
    """
    Factory function to get a configured Gemini model identifier with generation config.

    This function creates and returns both the model identifier and its configuration,
    allowing you to reuse the same config across multiple API calls.

    Args:
        model: The Gemini model to use (default: "gemini-2.0-flash-exp")
        temperature: Controls randomness (0.0-2.0, higher = more random)
        top_p: Nucleus sampling threshold (0.0-1.0)
        top_k: Top-K sampling limit
        max_output_tokens: Maximum tokens in output
        response_mime_type: MIME type for response (e.g., "application/json", "text/plain")
        response_schema: Optional JSON schema for structured output
        system_instruction: Optional system instruction for the model
        enable_safety_settings: Whether to enable safety settings (default: False)

    Returns:
        tuple[str, GenerateContentConfig]: Model identifier and configuration object

    Usage:
        # Get model and config
        model_id, config = get_model(
            temperature=1.0,
            response_mime_type="text/plain"
        )

        # Use with client (can reuse config for multiple calls)
        response = client.models.generate_content(
            model=model_id,
            contents="Your prompt here",
            config=config
        )

        # Reuse same config
        response2 = client.models.generate_content(
            model=model_id,
            contents="Another prompt",
            config=config
        )
    """
    config_params: Dict[str, Any] = {
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "max_output_tokens": max_output_tokens,
        "response_mime_type": response_mime_type,
    }

    if system_instruction:
        config_params["system_instruction"] = system_instruction

    if enable_safety_settings:
        config_params["safety_settings"] = safety_settings

    if response_schema:
        config_params["response_schema"] = response_schema

    config = types.GenerateContentConfig(**config_params)

    return model, config


def generate_content(
    prompt: str,
    model: str = "gemini-2.0-flash-exp",
    temperature: float = 0.8,
    top_p: float = 0.95,
    top_k: int = 64,
    max_output_tokens: int = 8192,
    response_mime_type: str = "application/json",
    response_schema: Optional[Dict[str, Any]] = None,
    system_instruction: Optional[str] = None,
    enable_safety_settings: bool = False
) -> types.GenerateContentResponse:
    """
    Helper function to generate content with custom configuration.

    Args:
        prompt: The input prompt/question for the model
        model: The Gemini model to use
        temperature: Controls randomness (0.0-2.0)
        top_p: Nucleus sampling threshold
        top_k: Top-K sampling limit
        max_output_tokens: Maximum tokens in output
        response_mime_type: MIME type for response
        response_schema: Optional JSON schema for structured output
        system_instruction: Optional system instruction
        enable_safety_settings: Whether to enable safety settings

    Returns:
        GenerateContentResponse: The model's response

    Usage:
        response = generate_content(
            prompt="Explain AI in simple terms",
            temperature=1.0,
            response_mime_type="text/plain"
        )
        print(response.text)
    """
    config_params: Dict[str, Any] = {
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "max_output_tokens": max_output_tokens,
        "response_mime_type": response_mime_type,
    }

    if system_instruction:
        config_params["system_instruction"] = system_instruction

    if enable_safety_settings:
        config_params["safety_settings"] = safety_settings

    if response_schema:
        config_params["response_schema"] = response_schema

    config = types.GenerateContentConfig(**config_params)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config
    )

    return response


# Export the configured client for direct use
__all__ = [
    "client",
    "get_model",
    "generate_content",
    "default_generation_config",
    "safety_settings"
]

