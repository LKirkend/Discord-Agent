"""
File: schemas.py
Description:
    Shared Pydantic schemas representing the JSON request and response payloads
    for the Antigravity Discord Liaison Bot FastAPI server.
Author: Logan Kirkendall <Logan@LKAud.io>
"""

from typing import List, Optional
from pydantic import BaseModel

class ApprovalRequest(BaseModel):
    """
    Description:
        Pydantic model representing a permission request for executing a tool or command.
    Attributes:
        request_id (Optional[str]): Unique tracking ID for this request.
        agent_name (str): Name of the agent requesting approval.
        conversation_id (str): ID of the active conversation session.
        tool_name (str): The name of the tool (e.g. run_command, write_file).
        arguments (dict): The dictionary of arguments passed to the tool.
        ls_address (Optional[str]): Language server address.
        ls_token (Optional[str]): Language server authentication token.
    """
    request_id: Optional[str] = None
    agent_name: str
    conversation_id: str
    tool_name: str
    arguments: dict
    ls_address: Optional[str] = None
    ls_token: Optional[str] = None

class ApprovalResponse(BaseModel):
    """
    Description:
        Pydantic model representing the response sent back indicating approval status.
    Attributes:
        approved (bool): True if approved by the user, False otherwise.
        reason (Optional[str]): Rejection or approval reason metadata.
    """
    approved: bool
    reason: Optional[str] = None

class MessageRequest(BaseModel):
    """
    Description:
        Pydantic model representing a text message or update payload to be posted.
    Attributes:
        content (str): The text content of the message.
        embed_title (Optional[str]): Optional title for the embed card.
        embed_description (Optional[str]): Optional description for the embed card.
    """
    content: str
    embed_title: Optional[str] = None
    embed_description: Optional[str] = None

class InteractionRequest(BaseModel):
    """
    Description:
        Pydantic model representing an interactive question prompt sent to the user.
    Attributes:
        request_id (Optional[str]): Unique tracking ID for the interaction.
        agent_name (str): Name of the agent triggering the interaction.
        conversation_id (str): Active conversation session ID.
        questions (List[dict]): List of multiple-choice questions to ask.
    """
    request_id: Optional[str] = None
    agent_name: str
    conversation_id: str
    questions: List[dict]

class InteractionResponse(BaseModel):
    """
    Description:
        Pydantic model representing the responses filled out by the user for an interaction.
    Attributes:
        responses (List[dict]): List of response dictionaries.
        cancelled (bool): True if the interaction was skipped/cancelled.
    """
    responses: List[dict]
    cancelled: bool

class SettingsRequest(BaseModel):
    """
    Description:
        Pydantic schema representing client-submitted requests to update the Discord Liaison Bot settings.
        Contains optional configurations for model provider, local auto-switching, bot permissions,
        and credentials for various APIs.
    Attributes:
        model_provider (Optional[str]): The chosen model provider (e.g. gemini, ollama).
        auto_switch_local (Optional[bool]): True if the bot should automatically fall back to local model.
        discord_bot_permissions (Optional[str]): Permissions integer for the Discord bot.
    """
    model_provider: Optional[str] = None
    auto_switch_local: Optional[bool] = None
    discord_bot_permissions: Optional[str] = None
    claude_api_key: Optional[str] = None
    claude_model_name: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_model_name: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_model_name: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openrouter_model_name: Optional[str] = None
    together_api_key: Optional[str] = None
    together_model_name: Optional[str] = None
    hf_api_key: Optional[str] = None
    hf_model_name: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model_name: Optional[str] = None
    custom_api_key: Optional[str] = None
    custom_model_name: Optional[str] = None
    custom_endpoint: Optional[str] = None
    agent_endpoint: Optional[str] = None
    forward_endpoint: Optional[str] = None
    agent_api_key: Optional[str] = None
    forward_api_key: Optional[str] = None
    agent_provider: Optional[str] = None
    agent_model_name: Optional[str] = None
    local_model_name: Optional[str] = None
    force_server_chat: Optional[int] = None
    force_only_server: Optional[int] = None
