from pydantic import BaseModel, Field


class DeployLastResult(BaseModel):
    task_id: str
    action: str
    status: str
    finished_at: str | None = None


class DeployStatus(BaseModel):
    enabled: bool
    runner_online: bool
    running_task_id: str | None = None
    allowed_actions: list[str] = []
    last_result: DeployLastResult | None = None


class DeployContainerItem(BaseModel):
    service: str
    container: str = ""
    state: str = "unknown"
    health: str | None = None
    image: str = ""
    created: str | None = None
    restart_count: int = 0
    ports: list[str] = []


class DeployContainers(BaseModel):
    available: bool
    collected_at: str | None = None
    compose_project: str | None = None
    heartbeat_age_seconds: int | None = None
    runner_online: bool = False
    services: list[DeployContainerItem] = []


class DeployVersions(BaseModel):
    app_version: str
    image_tags: dict[str, str] = {}
    compose_hash: str | None = None
    git_commit: str | None = None
    collected_at: str | None = None


class DeployActionRequest(BaseModel):
    action: str
    target: str | None = None
    params: dict = Field(default_factory=dict)
    confirm_token: str | None = None


class DeployActionResponse(BaseModel):
    task_id: str
    status: str = "queued"


class DeployConfirmRequest(BaseModel):
    action: str
    target: str | None = None


class DeployConfirmResponse(BaseModel):
    confirm_token: str
    expires_in: int


class DeployTaskDetail(BaseModel):
    task_id: str
    action: str
    status: str
    step: str | None = None
    step_index: int = 0
    total_steps: int = 0
    pct: int = 0
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    logs: list[str] = []
    error: str | None = None


class DeployHistoryItem(BaseModel):
    task_id: str
    action: str
    target: str | None = None
    status: str
    step: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    rolled_back: bool = False
    requested_by: str | None = None
    error: str | None = None
