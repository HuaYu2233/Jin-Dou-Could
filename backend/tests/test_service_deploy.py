import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.exceptions import DeployDisabled
from app.main import app
from app.services import deploy_protocol, deploy_service

VALID_TASK_ID = "8f2c1e4a-1111-4a2b-9c3d-1234567890ab"


@pytest.fixture
def deploy_dir(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "deploy"
    monkeypatch.setattr(settings, "DEPLOY_QUEUE_DIR", str(root))
    deploy_protocol.ensure_dirs()
    return root


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "DEPLOY_ENABLED", True)
    monkeypatch.setattr(settings, "DEPLOY_ALLOWED_ACTIONS", "check,deploy,restart")


class TestTaskIdValidation:
    def test_accepts_valid_uuid(self):
        assert deploy_protocol.validate_task_id(VALID_TASK_ID) == VALID_TASK_ID

    def test_accepts_generated_uuid(self):
        task_id = str(uuid4())
        assert deploy_protocol.validate_task_id(task_id) == task_id

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "not-a-uuid",
            "../../etc/passwd",
            "8f2c1e4a-1111-4a2b-9c3d-1234567890a",
            "8f2c1e4a_1111_4a2b_9c3d_1234567890ab",
        ],
    )
    def test_rejects_invalid(self, bad):
        with pytest.raises(ValueError):
            deploy_protocol.validate_task_id(bad)

    def test_task_path_stays_inside_root(self, deploy_dir: Path):
        with pytest.raises(ValueError):
            deploy_protocol.task_path("queue", "../../../tmp/evil")

    def test_rejects_unknown_kind(self, deploy_dir: Path):
        with pytest.raises(ValueError):
            deploy_protocol.task_path("unknown", VALID_TASK_ID)


class TestAtomicJson:
    def test_write_then_read_roundtrip(self, deploy_dir: Path):
        path = deploy_dir / "snapshot" / "meta.json"
        deploy_protocol.write_json_atomic(path, {"app_version": "1.1.0"})
        assert deploy_protocol.read_json(path) == {"app_version": "1.1.0"}

    def test_no_tmp_left_behind(self, deploy_dir: Path):
        path = deploy_dir / "snapshot" / "meta.json"
        deploy_protocol.write_json_atomic(path, {"a": 1})
        assert not path.with_name("meta.json.tmp").exists()

    def test_broken_json_returns_none(self, deploy_dir: Path):
        path = deploy_dir / "snapshot" / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        assert deploy_protocol.read_json(path) is None

    def test_non_object_json_returns_none(self, deploy_dir: Path):
        path = deploy_dir / "snapshot" / "list.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert deploy_protocol.read_json(path) is None

    def test_missing_file_returns_none(self, deploy_dir: Path):
        assert deploy_protocol.read_json(deploy_dir / "snapshot" / "none.json") is None


class TestQueueAndLocate:
    def test_enqueue_writes_queue_file(self, deploy_dir: Path):
        task = {"task_id": VALID_TASK_ID, "action": "check", "target": None, "params": {}}
        path = deploy_protocol.enqueue_task(task)
        assert path == deploy_dir / "queue" / f"{VALID_TASK_ID}.json"
        assert deploy_protocol.read_json(path)["action"] == "check"

    def test_enqueue_rejects_bad_task_id(self, deploy_dir: Path):
        with pytest.raises(ValueError):
            deploy_protocol.enqueue_task({"task_id": "bad", "action": "check"})

    def test_locate_reports_each_stage(self, deploy_dir: Path):
        deploy_protocol.write_json_atomic(deploy_dir / "queue" / f"{VALID_TASK_ID}.json", {"task_id": VALID_TASK_ID})
        deploy_protocol.write_json_atomic(deploy_dir / "running" / f"{VALID_TASK_ID}.json", {"task_id": VALID_TASK_ID})
        assert deploy_protocol.locate_task(VALID_TASK_ID) == ["queue", "running"]

    def test_locate_ignores_tmp_files(self, deploy_dir: Path):
        (deploy_dir / "queue" / f"{VALID_TASK_ID}.json.tmp").write_text("{}", encoding="utf-8")
        assert deploy_protocol.locate_task(VALID_TASK_ID) == []

    def test_list_queue_ignores_tmp_files(self, deploy_dir: Path):
        (deploy_dir / "queue" / "a.json.tmp").write_text("{}", encoding="utf-8")
        assert deploy_protocol.list_queue() == []


class TestLogStream:
    def _append(self, deploy_dir: Path, events: list[dict]) -> None:
        path = deploy_dir / "logs" / f"{VALID_TASK_ID}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def test_incremental_read_uses_offset(self, deploy_dir: Path):
        self._append(deploy_dir, [{"step": "preflight", "pct": 10}])
        first, offset = deploy_protocol.read_log_events(VALID_TASK_ID, 0)
        assert len(first) == 1
        assert offset > 0
        second, offset2 = deploy_protocol.read_log_events(VALID_TASK_ID, offset)
        assert second == []
        assert offset2 == offset
        self._append(deploy_dir, [{"step": "build", "pct": 55}])
        third, offset3 = deploy_protocol.read_log_events(VALID_TASK_ID, offset)
        assert [e["step"] for e in third] == ["build"]
        assert offset3 > offset

    def test_partial_line_is_not_consumed(self, deploy_dir: Path):
        path = deploy_dir / "logs" / f"{VALID_TASK_ID}.jsonl"
        path.write_text('{"step": "preflight"}\n{"step": "buil', encoding="utf-8")
        events, offset = deploy_protocol.read_log_events(VALID_TASK_ID, 0)
        assert [e["step"] for e in events] == ["preflight"]
        assert offset == len('{"step": "preflight"}\n')

    def test_bad_line_is_skipped(self, deploy_dir: Path):
        path = deploy_dir / "logs" / f"{VALID_TASK_ID}.jsonl"
        path.write_text('{"step": "a"}\nnot json\n[1,2]\n{"step": "b"}\n', encoding="utf-8")
        events, _ = deploy_protocol.read_log_events(VALID_TASK_ID, 0)
        assert [e["step"] for e in events] == ["a", "b"]

    def test_offset_beyond_size_resets(self, deploy_dir: Path):
        self._append(deploy_dir, [{"step": "a"}])
        events, offset = deploy_protocol.read_log_events(VALID_TASK_ID, 10_000)
        assert [e["step"] for e in events] == ["a"]
        assert offset == len('{"step": "a"}\n')

    def test_tail_returns_last_lines(self, deploy_dir: Path):
        self._append(deploy_dir, [{"pct": i} for i in range(10)])
        tail = deploy_protocol.read_log_tail(VALID_TASK_ID, 3)
        assert [e["pct"] for e in tail] == [7, 8, 9]

    def test_tail_limit_zero_returns_empty(self, deploy_dir: Path):
        self._append(deploy_dir, [{"pct": 1}])
        assert deploy_protocol.read_log_tail(VALID_TASK_ID, 0) == []

    def test_missing_log_returns_empty(self, deploy_dir: Path):
        events, offset = deploy_protocol.read_log_events(str(uuid4()), 0)
        assert events == []
        assert offset == 0


class TestHeartbeat:
    def test_missing_heartbeat_is_offline(self, deploy_dir: Path):
        assert deploy_protocol.heartbeat_age_seconds() is None
        assert deploy_protocol.runner_online() is False

    def test_fresh_heartbeat_is_online(self, deploy_dir: Path, monkeypatch):
        monkeypatch.setattr(settings, "DEPLOY_HEARTBEAT_TIMEOUT", 30)
        (deploy_dir / "heartbeat").write_text("", encoding="utf-8")
        age = deploy_protocol.heartbeat_age_seconds()
        assert age is not None
        assert age < 1
        assert deploy_protocol.runner_online() is True

    def test_stale_heartbeat_is_offline(self, deploy_dir: Path, monkeypatch):
        monkeypatch.setattr(settings, "DEPLOY_HEARTBEAT_TIMEOUT", 1)
        path = deploy_dir / "heartbeat"
        path.write_text("", encoding="utf-8")
        os.utime(path, (0, 0))
        assert deploy_protocol.runner_online() is False


class TestSnapshots:
    def test_container_snapshot_none_when_absent(self, deploy_dir: Path):
        assert deploy_protocol.container_snapshot() is None

    def test_container_snapshot_read(self, deploy_dir: Path):
        payload = {"collected_at": "2026-11-16T09:14:15Z", "services": [{"service": "backend"}]}
        deploy_protocol.write_json_atomic(deploy_dir / "snapshot" / "containers.json", payload)
        assert deploy_protocol.container_snapshot() == payload

    def test_meta_snapshot_read(self, deploy_dir: Path):
        payload = {"app_version": "1.1.0", "compose_hash": "abc"}
        deploy_protocol.write_json_atomic(deploy_dir / "snapshot" / "meta.json", payload)
        assert deploy_protocol.meta_snapshot() == payload

    def test_recent_results_sorted_by_finished_at(self, deploy_dir: Path):
        for finished in ["2026-11-16T01:00:00Z", "2026-11-16T03:00:00Z", "2026-11-16T02:00:00Z"]:
            tid = str(uuid4())
            deploy_protocol.write_json_atomic(
                deploy_dir / "results" / f"{tid}.json",
                {"task_id": tid, "action": "deploy", "status": "success", "finished_at": finished},
            )
        items = deploy_protocol.recent_results(3)
        assert [i["finished_at"] for i in items] == [
            "2026-11-16T03:00:00Z",
            "2026-11-16T02:00:00Z",
            "2026-11-16T01:00:00Z",
        ]

    def test_recent_results_respects_limit(self, deploy_dir: Path):
        for idx in range(5):
            tid = str(uuid4())
            deploy_protocol.write_json_atomic(
                deploy_dir / "results" / f"{tid}.json",
                {"task_id": tid, "action": "check", "status": "success", "finished_at": f"2026-11-16T0{idx}:00:00Z"},
            )
        assert len(deploy_protocol.recent_results(2)) == 2

    def test_latest_result_none_when_empty(self, deploy_dir: Path):
        assert deploy_protocol.latest_result() is None


class TestQueueClaim:
    def test_next_queue_task_returns_earliest(self, deploy_dir: Path):
        first = str(uuid4())
        second = str(uuid4())
        deploy_protocol.enqueue_task({"task_id": first, "action": "check"})
        deploy_protocol.enqueue_task({"task_id": second, "action": "check"})
        picked = deploy_protocol.next_queue_task()
        assert picked is not None
        assert picked[0] == first

    def test_next_queue_task_empty(self, deploy_dir: Path):
        assert deploy_protocol.next_queue_task() is None

    def test_claim_moves_to_running(self, deploy_dir: Path):
        task_id = str(uuid4())
        deploy_protocol.enqueue_task({"task_id": task_id, "action": "check", "status": "queued"})
        claimed = deploy_protocol.claim_task(task_id)
        assert claimed is not None
        assert claimed["task_id"] == task_id
        assert (deploy_dir / "running" / f"{task_id}.json").is_file()
        assert not (deploy_dir / "queue" / f"{task_id}.json").exists()

    def test_claim_twice_returns_none(self, deploy_dir: Path):
        task_id = str(uuid4())
        deploy_protocol.enqueue_task({"task_id": task_id, "action": "check"})
        assert deploy_protocol.claim_task(task_id) is not None
        assert deploy_protocol.claim_task(task_id) is None

    def test_update_running_merges_fields(self, deploy_dir: Path):
        task_id = str(uuid4())
        deploy_protocol.enqueue_task({"task_id": task_id, "action": "check"})
        deploy_protocol.claim_task(task_id)
        updated = deploy_protocol.update_running(task_id, {"step": "preflight", "pct": 40})
        assert updated is not None
        assert updated["step"] == "preflight"
        assert updated["pct"] == 40

    def test_update_running_missing_returns_none(self, deploy_dir: Path):
        assert deploy_protocol.update_running(str(uuid4()), {"pct": 10}) is None

    def test_finish_task_writes_result_and_cleans_running(self, deploy_dir: Path):
        task_id = str(uuid4())
        deploy_protocol.enqueue_task({"task_id": task_id, "action": "check"})
        deploy_protocol.claim_task(task_id)
        path = deploy_protocol.finish_task(task_id, {"task_id": task_id, "status": "success"})
        assert path.is_file()
        assert not (deploy_dir / "running" / f"{task_id}.json").exists()
        assert deploy_protocol.task_state(task_id) == "finished"

    def test_task_state_transitions(self, deploy_dir: Path):
        task_id = str(uuid4())
        deploy_protocol.enqueue_task({"task_id": task_id, "action": "check"})
        assert deploy_protocol.task_state(task_id) == "queued"
        deploy_protocol.claim_task(task_id)
        assert deploy_protocol.task_state(task_id) == "running"
        deploy_protocol.finish_task(task_id, {"task_id": task_id, "status": "success"})
        assert deploy_protocol.task_state(task_id) == "finished"
        assert deploy_protocol.task_state(str(uuid4())) is None

    def test_task_state_rejects_bad_id(self, deploy_dir: Path):
        with pytest.raises(ValueError):
            deploy_protocol.task_state("../escape")


class TestTaskDetail:
    def _seed(self, deploy_dir: Path, state: str, payload: dict) -> str:
        task_id = str(uuid4())
        payload.setdefault("task_id", task_id)
        deploy_protocol.enqueue_task(payload)
        if state in ("running", "finished"):
            deploy_protocol.claim_task(task_id)
        if state == "finished":
            deploy_protocol.finish_task(task_id, payload)
        return task_id

    def test_queued_detail(self, deploy_dir: Path):
        task_id = self._seed(deploy_dir, "queued", {"action": "check", "total_steps": 2})
        detail = deploy_protocol.task_detail(task_id, 50)
        assert detail is not None
        assert detail["status"] == "queued"
        assert detail["action"] == "check"
        assert detail["logs"] == []

    def test_running_detail_includes_logs(self, deploy_dir: Path):
        task_id = self._seed(deploy_dir, "running", {"action": "check", "total_steps": 2, "step_index": 1})
        line = json.dumps({"step": "preflight", "pct": 10, "msg": "生产编排校验通过"})
        with open(deploy_protocol.log_path(task_id), "a", encoding="utf-8") as f:
            f.write(line + "\n")
        detail = deploy_protocol.task_detail(task_id, 50)
        assert detail is not None
        assert detail["status"] == "running"
        assert detail["pct"] == 50
        assert detail["logs"] == ["生产编排校验通过"]

    def test_finished_detail_from_results(self, deploy_dir: Path):
        task_id = self._seed(
            deploy_dir,
            "finished",
            {"action": "check", "status": "success", "pct": 100, "total_steps": 2, "step_index": 2},
        )
        detail = deploy_protocol.task_detail(task_id, 50)
        assert detail is not None
        assert detail["status"] == "success"
        assert detail["pct"] == 100

    def test_missing_task_returns_none(self, deploy_dir: Path):
        assert deploy_protocol.task_detail(str(uuid4()), 50) is None

    def test_log_tail_respects_limit(self, deploy_dir: Path):
        task_id = self._seed(deploy_dir, "running", {"action": "check"})
        with open(deploy_protocol.log_path(task_id), "w", encoding="utf-8") as f:
            for i in range(10):
                f.write(json.dumps({"msg": f"line-{i}"}) + "\n")
        detail = deploy_protocol.task_detail(task_id, 3)
        assert detail is not None
        assert detail["logs"] == ["line-7", "line-8", "line-9"]

    def test_stalled_detection(self, deploy_dir: Path, monkeypatch):
        task_id = self._seed(
            deploy_dir,
            "running",
            {"action": "check", "started_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z"},
        )
        assert deploy_protocol.is_stalled(task_id, 60) is True

    def test_fresh_task_not_stalled(self, deploy_dir: Path):
        task_id = self._seed(deploy_dir, "running", {"action": "check", "updated_at": "2099-01-01T00:00:00Z"})
        assert deploy_protocol.is_stalled(task_id, 60) is False

    def test_queued_task_not_stalled(self, deploy_dir: Path):
        task_id = self._seed(deploy_dir, "queued", {"action": "check"})
        assert deploy_protocol.is_stalled(task_id, 1) is False


class TestDeployServiceActions:
    def _patch_redis(self, monkeypatch, *, lock_acquired: bool = True):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=lock_acquired)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.setex = AsyncMock(return_value=True)
        monkeypatch.setattr(deploy_service, "redis_client", mock_redis)
        return mock_redis

    async def test_check_enqueues_task(self, deploy_dir: Path, enabled, monkeypatch):
        self._patch_redis(monkeypatch)
        result = await deploy_service.submit_action(
            action="check",
            target=None,
            params=None,
            confirm_token=None,
            admin_id="admin-1",
        )
        assert result["status"] == "queued"
        task_id = result["task_id"]
        assert (deploy_dir / "queue" / f"{task_id}.json").is_file()

    async def test_invalid_action_rejected(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployInvalidAction

        self._patch_redis(monkeypatch)
        with pytest.raises(DeployInvalidAction):
            await deploy_service.submit_action(
                action="drop-database",
                target=None,
                params=None,
                confirm_token=None,
                admin_id="admin-1",
            )

    async def test_restart_requires_known_target(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployInvalidAction

        self._patch_redis(monkeypatch)
        with pytest.raises(DeployInvalidAction):
            await deploy_service.submit_action(
                action="restart",
                target="mysql",
                params=None,
                confirm_token=None,
                admin_id="admin-1",
            )

    async def test_restart_accepts_known_target(self, deploy_dir: Path, enabled, monkeypatch):
        self._patch_redis(monkeypatch)
        result = await deploy_service.submit_action(
            action="restart",
            target="backend",
            params=None,
            confirm_token=None,
            admin_id="admin-1",
        )
        assert result["status"] == "queued"
        task = deploy_protocol.read_json(deploy_dir / "queue" / f"{result['task_id']}.json")
        assert task is not None
        assert task["target"] == "backend"
        assert task["total_steps"] == 2

    async def test_deploy_requires_confirm_token(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployConfirmRequired

        self._patch_redis(monkeypatch)
        with pytest.raises(DeployConfirmRequired):
            await deploy_service.submit_action(
                action="deploy",
                target=None,
                params=None,
                confirm_token=None,
                admin_id="admin-1",
            )

    async def test_confirm_token_consumed_once(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployConfirmRequired

        mock_redis = self._patch_redis(monkeypatch)
        token = "tok-abc"
        mock_redis.get = AsyncMock(return_value=json.dumps({"action": "deploy", "target": None, "user_id": "admin-1"}))
        first = await deploy_service.submit_action(
            action="deploy",
            target=None,
            params=None,
            confirm_token=token,
            admin_id="admin-1",
        )
        assert first["status"] == "queued"
        mock_redis.get = AsyncMock(return_value=None)
        with pytest.raises(DeployConfirmRequired):
            await deploy_service.submit_action(
                action="deploy",
                target=None,
                params=None,
                confirm_token=token,
                admin_id="admin-1",
            )

    async def test_confirm_token_bound_to_admin(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployConfirmRequired

        mock_redis = self._patch_redis(monkeypatch)
        mock_redis.get = AsyncMock(return_value=json.dumps({"action": "deploy", "target": None, "user_id": "admin-1"}))
        with pytest.raises(DeployConfirmRequired):
            await deploy_service.submit_action(
                action="deploy",
                target=None,
                params=None,
                confirm_token="tok",
                admin_id="admin-2",
            )

    async def test_busy_when_lock_held(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployBusy

        mock_redis = self._patch_redis(monkeypatch, lock_acquired=False)
        mock_redis.get = AsyncMock(return_value="existing-task")
        with pytest.raises(DeployBusy):
            await deploy_service.submit_action(
                action="check",
                target=None,
                params=None,
                confirm_token=None,
                admin_id="admin-1",
            )

    async def test_idempotent_same_action(self, deploy_dir: Path, enabled, monkeypatch):
        self._patch_redis(monkeypatch)
        first = await deploy_service.submit_action(
            action="check",
            target=None,
            params=None,
            confirm_token=None,
            admin_id="admin-1",
        )
        second = await deploy_service.submit_action(
            action="check",
            target=None,
            params=None,
            confirm_token=None,
            admin_id="admin-1",
        )
        assert second["task_id"] == first["task_id"]

    async def test_lock_released_on_enqueue_failure(self, deploy_dir: Path, enabled, monkeypatch):
        mock_redis = self._patch_redis(monkeypatch)

        def boom(_task):
            raise OSError("disk full")

        monkeypatch.setattr(deploy_protocol, "enqueue_task", boom)
        with pytest.raises(OSError):
            await deploy_service.submit_action(
                action="check",
                target=None,
                params=None,
                confirm_token=None,
                admin_id="admin-1",
            )
        mock_redis.delete.assert_awaited_with(deploy_service.LOCK_KEY)

    async def test_issue_confirm_token_only_for_dangerous(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployInvalidAction

        mock_redis = self._patch_redis(monkeypatch)
        issued = await deploy_service.issue_confirm_token(action="deploy", target=None, admin_id="admin-1")
        assert issued["expires_in"] == deploy_service.CONFIRM_TTL_SECONDS
        assert issued["confirm_token"]
        mock_redis.setex.assert_awaited()
        with pytest.raises(DeployInvalidAction):
            await deploy_service.issue_confirm_token(action="check", target=None, admin_id="admin-1")

    async def test_get_task_reports_stalled(self, deploy_dir: Path, enabled, monkeypatch):
        monkeypatch.setattr(settings, "DEPLOY_TASK_TIMEOUT", 1)
        task_id = str(uuid4())
        deploy_protocol.enqueue_task(
            {
                "task_id": task_id,
                "action": "check",
                "updated_at": "2020-01-01T00:00:00Z",
                "started_at": "2020-01-01T00:00:00Z",
            }
        )
        deploy_protocol.claim_task(task_id)
        detail = deploy_service.get_task(task_id)
        assert detail["status"] == "stalled"

    async def test_get_task_not_found(self, deploy_dir: Path, enabled):
        from app.core.exceptions import DeployTaskNotFound

        with pytest.raises(DeployTaskNotFound):
            deploy_service.get_task(str(uuid4()))


class TestDeployActionParams:
    def _patch_redis(self, monkeypatch, *, lock_acquired: bool = True):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=lock_acquired)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.setex = AsyncMock(return_value=True)
        monkeypatch.setattr(deploy_service, "redis_client", mock_redis)
        return mock_redis

    async def test_deploy_defaults_backup_and_pull(self, deploy_dir: Path, enabled, monkeypatch):
        monkeypatch.setattr(settings, "DEPLOY_REQUIRE_BACKUP", True)
        mock_redis = self._patch_redis(monkeypatch)
        mock_redis.get = AsyncMock(return_value=json.dumps({"action": "deploy", "target": None, "user_id": "admin-1"}))
        result = await deploy_service.submit_action(
            action="deploy",
            target=None,
            params=None,
            confirm_token="tok",
            admin_id="admin-1",
        )
        task = deploy_protocol.read_json(deploy_dir / "queue" / f"{result['task_id']}.json")
        assert task is not None
        assert task["params"] == {"backup_first": True, "pull": True}
        assert task["total_steps"] == 7

    async def test_deploy_rejects_unknown_param(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployInvalidAction

        mock_redis = self._patch_redis(monkeypatch)
        mock_redis.get = AsyncMock(return_value=json.dumps({"action": "deploy", "target": None, "user_id": "admin-1"}))
        with pytest.raises(DeployInvalidAction):
            await deploy_service.submit_action(
                action="deploy",
                target=None,
                params={"image": "evil:latest"},
                confirm_token="tok",
                admin_id="admin-1",
            )

    async def test_deploy_rejects_non_bool_param(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployInvalidAction

        mock_redis = self._patch_redis(monkeypatch)
        mock_redis.get = AsyncMock(return_value=json.dumps({"action": "deploy", "target": None, "user_id": "admin-1"}))
        with pytest.raises(DeployInvalidAction):
            await deploy_service.submit_action(
                action="deploy",
                target=None,
                params={"pull": "yes"},
                confirm_token="tok",
                admin_id="admin-1",
            )

    async def test_deploy_honors_explicit_params(self, deploy_dir: Path, enabled, monkeypatch):
        mock_redis = self._patch_redis(monkeypatch)
        mock_redis.get = AsyncMock(return_value=json.dumps({"action": "deploy", "target": None, "user_id": "admin-1"}))
        result = await deploy_service.submit_action(
            action="deploy",
            target=None,
            params={"backup_first": False, "pull": False},
            confirm_token="tok",
            admin_id="admin-1",
        )
        task = deploy_protocol.read_json(deploy_dir / "queue" / f"{result['task_id']}.json")
        assert task is not None
        assert task["params"] == {"backup_first": False, "pull": False}

    async def test_check_rejects_params(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployInvalidAction

        self._patch_redis(monkeypatch)
        with pytest.raises(DeployInvalidAction):
            await deploy_service.submit_action(
                action="check",
                target=None,
                params={"pull": True},
                confirm_token=None,
                admin_id="admin-1",
            )

    async def test_rollback_steps_and_confirm(self, deploy_dir: Path, enabled, monkeypatch):
        from app.core.exceptions import DeployConfirmRequired

        monkeypatch.setattr(settings, "DEPLOY_ALLOWED_ACTIONS", "check,deploy,restart,rollback")
        mock_redis = self._patch_redis(monkeypatch)
        mock_redis.get = AsyncMock(return_value=None)
        with pytest.raises(DeployConfirmRequired):
            await deploy_service.submit_action(
                action="rollback",
                target=None,
                params=None,
                confirm_token=None,
                admin_id="admin-1",
            )
        mock_redis.get = AsyncMock(
            return_value=json.dumps({"action": "rollback", "target": None, "user_id": "admin-1"})
        )
        result = await deploy_service.submit_action(
            action="rollback",
            target=None,
            params=None,
            confirm_token="tok",
            admin_id="admin-1",
        )
        task = deploy_protocol.read_json(deploy_dir / "queue" / f"{result['task_id']}.json")
        assert task is not None
        assert task["action"] == "rollback"
        assert task["total_steps"] == 3

    def test_action_steps_cover_p3_actions(self):
        assert deploy_service.ACTION_STEPS["deploy"] == (
            "preflight",
            "backup",
            "tag_rollback",
            "pull",
            "build",
            "up",
            "health",
        )
        assert deploy_service.ACTION_STEPS["rollback"] == ("tag_rollback", "up", "health")


class TestDeployServiceStatus:
    def test_disabled_raises(self, deploy_dir: Path, monkeypatch):
        monkeypatch.setattr(settings, "DEPLOY_ENABLED", False)
        with pytest.raises(DeployDisabled):
            deploy_service.get_status()

    def test_enabled_returns_runner_offline(self, deploy_dir: Path, enabled):
        status = deploy_service.get_status()
        assert status["enabled"] is True
        assert status["runner_online"] is False
        assert status["running_task_id"] is None
        assert status["allowed_actions"] == ["check", "deploy", "restart"]
        assert status["last_result"] is None

    def test_running_task_reported(self, deploy_dir: Path, enabled):
        deploy_protocol.write_json_atomic(
            deploy_dir / "running" / f"{VALID_TASK_ID}.json",
            {"task_id": VALID_TASK_ID, "action": "deploy"},
        )
        status = deploy_service.get_status()
        assert status["running_task_id"] == VALID_TASK_ID

    def test_last_result_reported(self, deploy_dir: Path, enabled):
        deploy_protocol.write_json_atomic(
            deploy_dir / "results" / f"{VALID_TASK_ID}.json",
            {
                "task_id": VALID_TASK_ID,
                "action": "deploy",
                "status": "success",
                "finished_at": "2026-11-16T09:14:02Z",
            },
        )
        status = deploy_service.get_status()
        assert status["last_result"]["task_id"] == VALID_TASK_ID
        assert status["last_result"]["status"] == "success"

    def test_allowed_actions_trims_and_drops_empty(self, deploy_dir: Path, monkeypatch):
        monkeypatch.setattr(settings, "DEPLOY_ENABLED", True)
        monkeypatch.setattr(settings, "DEPLOY_ALLOWED_ACTIONS", " check , ,deploy ")
        assert deploy_service.allowed_actions() == ["check", "deploy"]


class TestDeployServiceReads:
    def test_containers_unavailable_without_snapshot(self, deploy_dir: Path, enabled):
        data = deploy_service.get_containers()
        assert data["available"] is False
        assert data["services"] == []
        assert data["runner_online"] is False

    def test_containers_with_snapshot(self, deploy_dir: Path, enabled, monkeypatch):
        monkeypatch.setattr(settings, "DEPLOY_HEARTBEAT_TIMEOUT", 30)
        (deploy_dir / "heartbeat").write_text("", encoding="utf-8")
        deploy_protocol.write_json_atomic(
            deploy_dir / "snapshot" / "containers.json",
            {
                "collected_at": "2026-11-16T09:14:15Z",
                "compose_project": "jindou-cloud",
                "services": [{"service": "backend", "state": "running", "health": "healthy"}, "junk"],
            },
        )
        data = deploy_service.get_containers()
        assert data["available"] is True
        assert data["compose_project"] == "jindou-cloud"
        assert data["services"] == [{"service": "backend", "state": "running", "health": "healthy"}]
        assert data["runner_online"] is True
        assert data["heartbeat_age_seconds"] == 0

    def test_versions_fallback_to_settings(self, deploy_dir: Path, enabled):
        data = deploy_service.get_versions()
        assert data["app_version"] == settings.APP_VERSION
        assert data["image_tags"] == {}
        assert data["compose_hash"] is None

    def test_versions_from_meta(self, deploy_dir: Path, enabled):
        deploy_protocol.write_json_atomic(
            deploy_dir / "snapshot" / "meta.json",
            {
                "app_version": "1.2.0",
                "image_tags": {"backend": "jindou-cloud-backend:latest"},
                "compose_hash": "deadbeef",
                "git_commit": "abc1234",
                "collected_at": "2026-11-16T09:14:15Z",
            },
        )
        data = deploy_service.get_versions()
        assert data["app_version"] == "1.2.0"
        assert data["image_tags"] == {"backend": "jindou-cloud-backend:latest"}
        assert data["git_commit"] == "abc1234"

    def test_versions_ignores_non_dict_image_tags(self, deploy_dir: Path, enabled):
        deploy_protocol.write_json_atomic(
            deploy_dir / "snapshot" / "meta.json",
            {"app_version": "1.2.0", "image_tags": ["backend"]},
        )
        assert deploy_service.get_versions()["image_tags"] == {}

    def test_history_maps_result_fields(self, deploy_dir: Path, enabled):
        deploy_protocol.write_json_atomic(
            deploy_dir / "results" / f"{VALID_TASK_ID}.json",
            {
                "task_id": VALID_TASK_ID,
                "action": "deploy",
                "target": None,
                "status": "rolled_back",
                "step": "health",
                "started_at": "2026-11-16T09:12:03Z",
                "finished_at": "2026-11-16T09:14:02Z",
                "rolled_back": True,
                "requested_by": "admin-1",
                "error": "健康检查失败",
            },
        )
        items = deploy_service.get_history(20)
        assert len(items) == 1
        assert items[0]["status"] == "rolled_back"
        assert items[0]["rolled_back"] is True
        assert items[0]["error"] == "健康检查失败"

    def test_history_disabled_raises(self, deploy_dir: Path, monkeypatch):
        monkeypatch.setattr(settings, "DEPLOY_ENABLED", False)
        with pytest.raises(DeployDisabled):
            deploy_service.get_history()


class TestDeployEndpoints:
    def _client(self, admin) -> TestClient:
        from app.api.deps import get_current_admin

        app.dependency_overrides[get_current_admin] = lambda: admin
        return TestClient(app)

    def _clear(self) -> None:
        app.dependency_overrides.clear()

    def test_status_requires_admin(self, deploy_dir: Path, enabled):
        from unittest.mock import AsyncMock, patch

        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/v1/admin/deploy/status")
            assert resp.status_code in (401, 403)

    def test_status_403_when_disabled(self, deploy_dir: Path, monkeypatch, fake_admin):
        monkeypatch.setattr(settings, "DEPLOY_ENABLED", False)
        client = self._client(fake_admin)
        try:
            resp = client.get("/api/v1/admin/deploy/status")
            assert resp.status_code == 403
            assert resp.json()["code"] == "deploy_disabled"
        finally:
            self._clear()

    def test_status_ok_when_enabled(self, deploy_dir: Path, enabled, fake_admin):
        client = self._client(fake_admin)
        try:
            resp = client.get("/api/v1/admin/deploy/status")
            assert resp.status_code == 200
            body = resp.json()
            assert body["enabled"] is True
            assert body["runner_online"] is False
            assert body["allowed_actions"] == ["check", "deploy", "restart"]
        finally:
            self._clear()

    def test_versions_ok(self, deploy_dir: Path, enabled, fake_admin):
        client = self._client(fake_admin)
        try:
            resp = client.get("/api/v1/admin/deploy/versions")
            assert resp.status_code == 200
            assert resp.json()["app_version"] == settings.APP_VERSION
        finally:
            self._clear()

    def test_containers_ok(self, deploy_dir: Path, enabled, fake_admin):
        client = self._client(fake_admin)
        try:
            resp = client.get("/api/v1/admin/deploy/containers")
            assert resp.status_code == 200
            assert resp.json()["available"] is False
        finally:
            self._clear()

    def test_history_ok(self, deploy_dir: Path, enabled, fake_admin):
        client = self._client(fake_admin)
        try:
            resp = client.get("/api/v1/admin/deploy/history")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            self._clear()

    def test_history_rejects_bad_limit(self, deploy_dir: Path, enabled, fake_admin):
        client = self._client(fake_admin)
        try:
            resp = client.get("/api/v1/admin/deploy/history?limit=0")
            assert resp.status_code == 422
        finally:
            self._clear()

    def test_action_requires_admin(self, deploy_dir: Path, enabled):
        from unittest.mock import AsyncMock, patch

        with patch("app.api.deps.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.exists = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.post("/api/v1/admin/deploy/actions", json={"action": "check"})
            assert resp.status_code in (401, 403)

    def test_action_403_when_disabled(self, deploy_dir: Path, monkeypatch, fake_admin):
        monkeypatch.setattr(settings, "DEPLOY_ENABLED", False)
        client = self._client(fake_admin)
        try:
            resp = client.post("/api/v1/admin/deploy/actions", json={"action": "check"})
            assert resp.status_code == 403
            assert resp.json()["code"] == "deploy_disabled"
        finally:
            self._clear()

    def test_action_invalid_returns_400(self, deploy_dir: Path, enabled, fake_admin, monkeypatch):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.setex = AsyncMock(return_value=True)
        monkeypatch.setattr(deploy_service, "redis_client", mock_redis)
        client = self._client(fake_admin)
        try:
            resp = client.post("/api/v1/admin/deploy/actions", json={"action": "rm-rf"})
            assert resp.status_code == 400
            assert resp.json()["code"] == "deploy_invalid_action"
        finally:
            self._clear()

    def test_action_check_ok(self, deploy_dir: Path, enabled, fake_admin, monkeypatch):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.setex = AsyncMock(return_value=True)
        monkeypatch.setattr(deploy_service, "redis_client", mock_redis)
        client = self._client(fake_admin)
        try:
            resp = client.post("/api/v1/admin/deploy/actions", json={"action": "check"})
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "queued"
            assert body["task_id"]
        finally:
            self._clear()

    def test_action_deploy_without_token_returns_403(self, deploy_dir: Path, enabled, fake_admin, monkeypatch):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.setex = AsyncMock(return_value=True)
        monkeypatch.setattr(deploy_service, "redis_client", mock_redis)
        client = self._client(fake_admin)
        try:
            resp = client.post("/api/v1/admin/deploy/actions", json={"action": "deploy"})
            assert resp.status_code == 403
            assert resp.json()["code"] == "deploy_confirm_required"
        finally:
            self._clear()

    def test_confirm_issues_token(self, deploy_dir: Path, enabled, fake_admin, monkeypatch):
        mock_redis = MagicMock()
        mock_redis.setex = AsyncMock(return_value=True)
        monkeypatch.setattr(deploy_service, "redis_client", mock_redis)
        client = self._client(fake_admin)
        try:
            resp = client.post("/api/v1/admin/deploy/confirm", json={"action": "deploy"})
            assert resp.status_code == 200
            body = resp.json()
            assert body["expires_in"] == deploy_service.CONFIRM_TTL_SECONDS
            assert body["confirm_token"]
        finally:
            self._clear()

    def test_confirm_rejects_safe_action(self, deploy_dir: Path, enabled, fake_admin, monkeypatch):
        mock_redis = MagicMock()
        mock_redis.setex = AsyncMock(return_value=True)
        monkeypatch.setattr(deploy_service, "redis_client", mock_redis)
        client = self._client(fake_admin)
        try:
            resp = client.post("/api/v1/admin/deploy/confirm", json={"action": "check"})
            assert resp.status_code == 400
        finally:
            self._clear()

    def test_task_detail_ok(self, deploy_dir: Path, enabled, fake_admin):
        task_id = str(uuid4())
        deploy_protocol.enqueue_task({"task_id": task_id, "action": "check", "total_steps": 2})
        client = self._client(fake_admin)
        try:
            resp = client.get(f"/api/v1/admin/deploy/tasks/{task_id}")
            assert resp.status_code == 200
            assert resp.json()["status"] == "queued"
        finally:
            self._clear()

    def test_task_detail_404(self, deploy_dir: Path, enabled, fake_admin):
        client = self._client(fake_admin)
        try:
            resp = client.get(f"/api/v1/admin/deploy/tasks/{uuid4()}")
            assert resp.status_code == 404
            assert resp.json()["code"] == "deploy_task_not_found"
        finally:
            self._clear()

    def test_task_detail_rejects_path_traversal(self, deploy_dir: Path, enabled, fake_admin):
        client = self._client(fake_admin)
        try:
            resp = client.get("/api/v1/admin/deploy/tasks/..%2F..%2Fetc%2Fpasswd")
            assert resp.status_code in (400, 404, 422)
        finally:
            self._clear()

    def test_non_admin_gets_403(self, deploy_dir: Path, enabled, fake_user):
        from app.api.deps import get_current_user

        app.dependency_overrides[get_current_user] = lambda: fake_user
        client = TestClient(app)
        try:
            resp = client.post(
                "/api/v1/admin/deploy/actions",
                json={"action": "check"},
            )
            assert resp.status_code == 403
            assert "管理员" in resp.json()["detail"]
        finally:
            self._clear()

    def test_csrf_missing_returns_403(self, deploy_dir: Path, enabled, fake_admin, monkeypatch):
        monkeypatch.setattr(settings, "CSRF_ENABLED", True)
        client = self._client(fake_admin)
        try:
            resp = client.post("/api/v1/admin/deploy/actions", json={"action": "check"})
            assert resp.status_code == 403
            assert "CSRF" in resp.json()["detail"]
        finally:
            self._clear()

    def test_csrf_matching_header_passes(self, deploy_dir: Path, enabled, fake_admin, monkeypatch):
        monkeypatch.setattr(settings, "CSRF_ENABLED", True)
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.setex = AsyncMock(return_value=True)
        monkeypatch.setattr(deploy_service, "redis_client", mock_redis)
        client = self._client(fake_admin)
        client.cookies.set("csrf_token", "token-value")
        try:
            resp = client.post(
                "/api/v1/admin/deploy/actions",
                json={"action": "check"},
                headers={"x-csrf-token": "token-value"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "queued"
        finally:
            client.cookies.clear()
            self._clear()

    def test_triple_click_yields_single_task(self, deploy_dir: Path, enabled, fake_admin, monkeypatch):
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.setex = AsyncMock(return_value=True)
        monkeypatch.setattr(deploy_service, "redis_client", mock_redis)
        client = self._client(fake_admin)
        try:
            task_ids = {
                client.post("/api/v1/admin/deploy/actions", json={"action": "check"}).json()["task_id"]
                for _ in range(3)
            }
            assert len(task_ids) == 1
            queued = list((deploy_dir / "queue").glob("*.json"))
            assert len(queued) == 1
        finally:
            self._clear()
