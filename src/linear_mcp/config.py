"""Configuration management for Linear MCP CLI."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Linear MCP Server URL
LINEAR_MCP_URL = "https://mcp.linear.app/mcp"


class LinearConfig(BaseModel):
    """Linear API configuration."""

    api_key: str = Field(default="", description="Linear API key or OAuth token")


class McpServerConfig(BaseModel):
    """MCP Server configuration."""

    timeout: int = Field(default=30, description="HTTP request timeout in seconds")
    sse_read_timeout: int = Field(default=300, description="SSE read timeout in seconds")


class Config(BaseSettings):
    """Main configuration for Linear MCP CLI."""

    model_config = SettingsConfigDict(
        env_prefix="LINEAR_MCP_",
        env_nested_delimiter="__",
    )

    linear: LinearConfig = Field(default_factory=LinearConfig)
    mcp_server: McpServerConfig = Field(default_factory=McpServerConfig)


def get_config_path() -> Path:
    """Get the configuration file path."""
    # Check for config in current directory first
    local_config = Path.cwd() / ".linear-mcp.yaml"
    if local_config.exists():
        return local_config

    # Fall back to user config directory
    config_dir = Path.home() / ".config" / "linear-mcp"
    return config_dir / "config.yaml"


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file and environment variables.

    Priority (highest to lowest):
    1. Environment variables (LINEAR_MCP_* prefix)
    2. Config file values
    3. Default values
    """
    if config_path is None:
        config_path = get_config_path()

    config_data: dict = {}

    if config_path.exists():
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}

    # Override with environment variables for Linear credentials
    if linear_api_key := os.getenv("LINEAR_API_KEY"):
        config_data.setdefault("linear", {})["api_key"] = linear_api_key

    return Config(**config_data)
