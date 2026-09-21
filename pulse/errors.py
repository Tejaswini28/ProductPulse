"""Classify LLM-call failures into PM-safe structured results.

langchain_openai already wraps every openai.* exception raised inside a
ChatOpenAI call (including ones made deep inside a LangGraph agent loop) into
its own typed subclasses — OpenAIAuthenticationError, OpenAIRateLimitError,
OpenAIContextOverflowError, etc. (see langchain_openai/chat_models/base.py).
Those subclasses inherit both the real openai.APIStatusError (status_code,
response, body, message) and a LangChain-generic Model*Error base, so
isinstance checks against them are precise and version-correct — this module
classifies off those rather than guessing from exception name strings.

Retrying once for recoverable errors already happens beneath this: both
ChatOpenAI constructors in pulse/rag.py are built with max_retries=1, which
configures the openai SDK's own bounded retry (with backoff) for exactly the
categories that should be retried — rate limits, timeouts, connection errors,
5xx. This module classifies whatever reaches Python code AFTER that transport
retry is exhausted or skipped (skipped because the error wasn't retryable in
the first place, e.g. a 400 or 401).
"""
import logging
from datetime import datetime,timezone

try:
    import openai
    from langchain_openai.chat_models.base import (
        OpenAIAuthenticationError,OpenAIPermissionDeniedError,OpenAIInvalidRequestError,
        OpenAIModelNotFoundError,OpenAIRateLimitError,OpenAIAPIError,OpenAIConnectionError,
        OpenAITimeoutError,OpenAIContextOverflowError,
    )
except ImportError:  # pragma: no cover - only true if dependencies are missing entirely
    openai=None

logger=logging.getLogger(__name__)

CATEGORIES=('authentication','rate_limit','invalid_request','context_limit',
    'malformed_tool_request','temporary_service_failure','unknown')

RETRYABLE_CATEGORIES={'rate_limit','temporary_service_failure'}

PM_MESSAGE={
    'authentication':"Product Pulse couldn't complete the analysis because of a system configuration issue.",
    'rate_limit':"Product Pulse couldn't complete the analysis because the AI service is temporarily unavailable.",
    'invalid_request':"Product Pulse couldn't complete the analysis because of a system configuration issue.",
    'context_limit':"Product Pulse couldn't complete the analysis because the request was too large to process.",
    'malformed_tool_request':"Product Pulse couldn't complete the analysis because of a system configuration issue.",
    'temporary_service_failure':"Product Pulse couldn't complete the analysis because the AI service is temporarily unavailable.",
    'unknown':"Product Pulse couldn't complete the analysis because of an unexpected error.",
}

def classify(error: Exception) -> str:
    """Map an exception to one of CATEGORIES. Never raises."""
    if openai is None:
        return 'unknown'
    if isinstance(error,(OpenAIAuthenticationError,OpenAIPermissionDeniedError,OpenAIModelNotFoundError)):
        return 'authentication'
    if isinstance(error,OpenAIRateLimitError):
        return 'rate_limit'
    if isinstance(error,OpenAIContextOverflowError):
        return 'context_limit'
    if isinstance(error,OpenAIInvalidRequestError):
        message=(getattr(error,'message',None) or str(error)).lower()
        if 'tool' in message or 'function' in message or 'parallel_tool_calls' in message:
            return 'malformed_tool_request'
        return 'invalid_request'
    if isinstance(error,(OpenAIAPIError,OpenAIConnectionError,OpenAITimeoutError)):
        return 'temporary_service_failure'
    # Fall back to the raw openai/httpx status where langchain didn't wrap it
    # (e.g. a raised inside a tool call rather than a ChatOpenAI invocation).
    status=getattr(error,'status_code',None) or getattr(getattr(error,'response',None),'status_code',None)
    if status in (401,403):return 'authentication'
    if status==429:return 'rate_limit'
    if status==400:return 'invalid_request'
    if status is not None and status>=500:return 'temporary_service_failure'
    return 'unknown'

def describe(error: Exception, stage: str, model: str|None=None) -> dict:
    """Log full internal detail and return a PM-safe structured failure result.

    The returned dict is safe to put directly in front of a PM: `message` is
    generic and provider-agnostic. `technical_error` carries the real detail
    and must only ever be shown behind a collapsed "Technical details" panel.
    """
    category=classify(error)
    status=getattr(error,'status_code',None) or getattr(getattr(error,'response',None),'status_code',None)
    provider_message=getattr(error,'message',None) or str(error)
    timestamp=datetime.now(timezone.utc).isoformat()
    logger.warning('LLM call failed — stage=%s category=%s type=%s status=%s model=%s time=%s message=%s',
        stage,category,type(error).__name__,status,model,timestamp,provider_message)
    return {
        'status':'unavailable',
        'stage':stage,
        'message':PM_MESSAGE[category],
        'retryable':category in RETRYABLE_CATEGORIES,
        'category':category,
        'technical_error':f'{type(error).__name__} (status={status}, category={category}) at {timestamp}: {provider_message}',
    }
