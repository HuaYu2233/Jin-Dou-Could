from pydantic import BaseModel, Field


class EnvField(BaseModel):
    key: str
    value: str
    group: str
    hint: str = ""
    required: bool = False
    sensitive: bool = False


class EnvConfigGroup(BaseModel):
    name: str
    fields: list[EnvField]


class EnvConfigResponse(BaseModel):
    enabled: bool
    path: str
    backup: str | None = None
    groups: list[EnvConfigGroup] = []


class EnvConfigSaveRequest(BaseModel):
    values: dict[str, str]


class EnvConfigSaveResponse(BaseModel):
    ok: bool = True
    path: str
    backup: str
    errors: list[str] = Field(default_factory=list)
