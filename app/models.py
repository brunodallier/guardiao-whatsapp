from pydantic import BaseModel, Field, field_validator, model_validator

from app.moderation.urls import normalize_domain, canonical_url


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: str = Field(min_length=10, max_length=200)


class GroupInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    participant_count: int = Field(default=0, ge=0, le=100000)
    active: bool = True

    @field_validator("name")
    @classmethod
    def trim(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Informe um nome com pelo menos dois caracteres.")
        return value.strip()


class AffiliateInput(BaseModel):
    platform: str = Field(min_length=2, max_length=100)
    domain: str = Field(max_length=253)
    referral_url: str = Field(default="", max_length=2000)
    affiliate_code: str = Field(default="", max_length=200)
    affiliate_parameters: list[str] = Field(default_factory=list, max_length=30)
    affiliate_path_prefix: str = Field(default="", max_length=200)
    allowed_links: list[str] = Field(default_factory=list, max_length=100)
    allowed_domains: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("platform")
    @classmethod
    def platform_valid(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Informe um nome de plataforma.")
        return value.strip()

    @field_validator("domain")
    @classmethod
    def domain_valid(cls, value):
        return normalize_domain(value)

    @field_validator("allowed_domains")
    @classmethod
    def domains_valid(cls, values):
        return [normalize_domain(value) for value in values]

    @field_validator("referral_url")
    @classmethod
    def referral_valid(cls, value):
        if value:
            canonical_url(value)
        return value.strip()

    @field_validator("allowed_links")
    @classmethod
    def links_valid(cls, values):
        for value in values:
            canonical_url(value)
        return values

    @field_validator("affiliate_parameters")
    @classmethod
    def params_valid(cls, values):
        if any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("Parâmetros inválidos.")
        return list(dict.fromkeys(value.strip().lower() for value in values))

    @model_validator(mode="after")
    def validate_profile(self):
        if self.referral_url:
            from urllib.parse import urlsplit
            host = urlsplit(canonical_url(self.referral_url)).hostname
            if host != self.domain and not host.endswith("." + self.domain):
                raise ValueError("O link de indicação deve pertencer ao domínio da plataforma.")
        if self.affiliate_path_prefix and not self.affiliate_path_prefix.startswith("/"):
            raise ValueError("O prefixo do caminho deve começar com /.")
        return self


class RulesInput(BaseModel):
    casino_domains: list[str] = Field(max_length=500)
    marketplace_domains: list[str] = Field(max_length=500)
    shortener_domains: list[str] = Field(max_length=500)
    allowed_domains: list[str] = Field(max_length=500)
    allowed_links: list[str] = Field(max_length=500)
    affiliate_parameters: list[str] = Field(max_length=50)
    enabled: dict[str, bool]
    repeat_threshold: int = Field(ge=2, le=1000)
    repeat_window_seconds: int = Field(ge=1, le=86400)
    burst_threshold: int = Field(ge=2, le=1000)
    burst_window_seconds: int = Field(ge=1, le=86400)
    link_burst_threshold: int = Field(ge=2, le=1000)
    link_burst_window_seconds: int = Field(ge=1, le=86400)
    retention_days: int = Field(ge=1, le=365)

    @field_validator("casino_domains", "marketplace_domains", "shortener_domains", "allowed_domains")
    @classmethod
    def domains_valid(cls, values):
        return [normalize_domain(value) for value in values]

    @field_validator("allowed_links")
    @classmethod
    def links_valid(cls, values):
        return [canonical_url(value) for value in values]

    @field_validator("affiliate_parameters")
    @classmethod
    def params_valid(cls, values):
        if any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("Parâmetros inválidos.")
        return list(dict.fromkeys(value.strip().lower() for value in values))

    @field_validator("enabled")
    @classmethod
    def enabled_valid(cls, value):
        expected = {"casino", "affiliate", "marketplace", "unknown_link", "repeat", "burst", "link_burst"}
        if set(value) != expected:
            raise ValueError("Informe exatamente as sete regras disponíveis.")
        return value


class MessageInput(BaseModel):
    group_id: int = Field(gt=0)
    participant: str = Field(min_length=2, max_length=100)
    content: str = Field(min_length=1, max_length=10000)

    @field_validator("participant", "content")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("O campo não pode estar vazio.")
        return value.strip()


class DeleteHistoryInput(BaseModel):
    confirmation: str
    group_id: int | None = None
