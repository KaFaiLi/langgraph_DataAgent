"""Centralized, typed configuration.

Everything the template needs is read from environment variables (optionally via
a ``.env`` file). Import :func:`get_settings` anywhere you need config; it is
cached so the ``.env`` file is only parsed once per process.
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root is the directory containing the data_agent package.
REPO_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Runtime settings, populated from the environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM -----------------------------------------------------------------
    llm_provider: str = Field(default="deepseek", description="deepseek | socgenai")
    genai_model: str = Field(default="gpt-4o-mini")
    genai_temperature: float = Field(default=0.0)
    socgenai_low_cost_model: str = Field(default="gpt-5-mini")
    socgenai_high_cost_model: str = Field(default="gpt-5.4")
    deepseek_low_cost_model: str = Field(default="deepseek-v4-flash")
    deepseek_high_cost_model: str = Field(default="deepseek-v4-pro")
    deepseek_model: str = Field(default="deepseek-chat")
    deepseek_temperature: float = Field(default=0.0)
    deepseek_api_key: SecretStr | None = Field(default=None)

    # --- MCP server ----------------------------------------------------------
    mcp_transport: str = Field(default="stdio", description="stdio | http")
    mcp_host: str = Field(default="127.0.0.1")
    mcp_port: int = Field(default=8000)
    mcp_server_name: str = Field(default="mcp-agent-template")
    mcp_tool_timeout: float = Field(
        default=30.0,
        description=(
            "Seconds to wait for an MCP tool call to complete (HTTP connect "
            "+ server processing). Raise this for slow tools or beefy LLM calls "
            "that happen inside a tool. Corresponds to the `timeout` field of "
            "langchain-mcp-adapters' streamable-HTTP connection."
        ),
    )
    mcp_read_timeout: float = Field(
        default=300.0,
        description=(
            "Seconds to keep the SSE stream open waiting for the next event "
            "(i.e. max silence between chunks). 300 s (5 min) is the library "
            "default. Raise this if a tool streams a very long response. "
            "Corresponds to the `sse_read_timeout` field."
        ),
    )

    # --- Source tools -------------------------------------------------------
    source_root: str = Field(
        default="sources",
        description=(
            "Directory containing read-only source material. Relative paths "
            "are resolved from the repository root."
        ),
    )

    @field_validator("source_root", mode="before")
    @classmethod
    def _coerce_source_root(cls, value: object) -> str:
        """Accept ``Path`` overrides in tests and embedding applications."""
        return os.fspath(value) if isinstance(value, os.PathLike) else str(value)

    # --- Skills --------------------------------------------------------------
    skills_dir: str = Field(default="skills")

    # --- Agent ---------------------------------------------------------------
    agent_max_iterations: int = Field(
        default=10,
        description=(
            "Maximum number of tool-call rounds the ReAct agent is allowed per "
            "run. Each round = one LLM call + its tool calls. Mapped to "
            "LangGraph's `recursion_limit` at invocation time (approx. "
            "max_iterations × 3 to account for hook + model + tool nodes). "
            "Raise this for multi-step tasks; lower it to cap costs."
        ),
    )

    # --- Logging -------------------------------------------------------------
    log_level: str = Field(default="INFO")

    @property
    def skills_path(self) -> Path:
        """Absolute path to the skills directory."""
        p = Path(self.skills_dir)
        return p if p.is_absolute() else (REPO_ROOT / p)

    @property
    def mcp_http_url(self) -> str:
        """Streamable-HTTP endpoint used by clients when transport=http."""
        return f"http://{self.mcp_host}:{self.mcp_port}/mcp"

    @property
    def source_path(self) -> Path:
        """Absolute configured source directory used by source MCP tools."""
        path = Path(self.source_root)
        return path if path.is_absolute() else (REPO_ROOT / path)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached :class:`Settings`."""
    return Settings()
