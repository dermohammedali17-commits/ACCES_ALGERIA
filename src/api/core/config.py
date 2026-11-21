from __future__ import annotations

import ipaddress
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "ACCESS ALGERIA Intelligence API"
    api_v1_prefix: str = "/api/v1"
    debug_mode: bool = False
    environment: str = "development"

    # P6.1 Security Configuration
    jwt_secret_key: SecretStr = Field(
        default=SecretStr("insecure-default-secret-key-change-me"),
        description="Cryptographic signing key for JWT access tokens",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_access_token_expire_minutes: int = Field(default=15, description="Access token lifetime in minutes")
    jwt_issuer: str = Field(default="access-algeria-auth", description="JWT issuer claim")
    jwt_audience: str = Field(default="access-algeria-api", description="JWT audience claim")

    trusted_proxy_ips: list[str] = Field(
        default_factory=lambda: ["127.0.0.1", "::1"],
        description="Explicitly configured trusted proxy IPs (defaults to loopback for dev/test only)",
    )

    admin_initial_email: str | None = Field(default=None, description="Initial administrator email for bootstrap")
    admin_initial_password: SecretStr | None = Field(
        default=None, description="Initial administrator password for bootstrap (protected SecretStr)"
    )

    auth_database_path: str = Field(
        default="data/access_algeria_auth.duckdb",
        description="Path to authentication DuckDB database",
    )

    lpsme_database_path: str = Field(
        default="data/access_algeria_lpsme.duckdb",
        description="Path to LPSME intelligence DuckDB database",
    )

    security_headers_enabled: bool = Field(default=True, description="Enable modern security headers middleware")
    rate_limiting_enabled: bool = Field(default=True, description="Enable rate limiting middleware")
    deployment_workers: int = Field(default=1, description="Number of deployment workers (restricted to 1 for Phase 6.1)")

    @field_validator("trusted_proxy_ips", mode="before")
    @classmethod
    def parse_trusted_proxy_ips(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            parsed = [ip.strip() for ip in v.split(",") if ip.strip()]
            return parsed if parsed else ["127.0.0.1", "::1"]
        if isinstance(v, list):
            parsed = [str(ip).strip() for ip in v if str(ip).strip()]
            return parsed if parsed else ["127.0.0.1", "::1"]
        return ["127.0.0.1", "::1"]
    @field_validator("trusted_proxy_ips")
    @classmethod
    def validate_trusted_proxy_ips(cls, values: list[str]) -> list[str]:
        validated: list[str] = []

        for value in values:
            try:
                normalized = str(ipaddress.ip_address(value))
            except ValueError as exc:
                raise ValueError(
                    f"Invalid trusted proxy IP address: {value}"
                ) from exc

            if normalized not in validated:
                validated.append(normalized)

        return validated
    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        if v not in ("HS256",):
            raise ValueError(f"Unsupported JWT algorithm '{v}'. Phase 6.1 requires HS256.")
        return v

    @field_validator("jwt_access_token_expire_minutes")
    @classmethod
    def validate_token_expiration(cls, v: int) -> int:
        if v <= 0 or v > 60:
            raise ValueError("JWT access token expiration must be between 1 and 60 minutes.")
        return v

    @field_validator("deployment_workers")
    @classmethod
    def validate_deployment_workers(cls, v: int) -> int:
        if v != 1:
            raise ValueError(
                f"Unsupported deployment workers count ({v}). Phase 6.1 strictly requires single-worker deployment (DEPLOYMENT_WORKERS=1)."
            )
        return v

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        secret_val = self.jwt_secret_key.get_secret_value()
        insecure_defaults = {
            "insecure-default-secret-key-change-me",
            "secret",
            "changeme",
            "password",
            "default",
        }
        if self.environment.lower() in ("production", "prod"):
            if secret_val in insecure_defaults:
                raise ValueError(
                    "Insecure or default JWT_SECRET_KEY detected in production environment. "
                    "A strong cryptographic secret must be provided via environment variables."
                )
            # In production, trusted proxies must be explicitly configured and not rely on default loopback if strict proxy isolation is needed.
            if len(secret_val.encode("utf-8")) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 bytes long in production."
                )
        return self


settings = Settings()
