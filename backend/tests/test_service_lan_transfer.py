import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import Conflict, Forbidden, InsufficientStorage, QuotaExceeded, RateLimited
from app.services import lan_transfer_service as svc


class TestBuildJoinUrl:
    def test_prefers_public_base_url(self):
        with patch.object(svc.settings, "LAN_TRANSFER_PUBLIC_BASE_URL", "http://192.168.1.10"):
            url = svc.build_join_url("ABCD1234", "http://localhost:3000", None)
        assert url == "http://192.168.1.10/transfer/ABCD1234"

    def test_falls_back_to_origin(self):
        with patch.object(svc.settings, "LAN_TRANSFER_PUBLIC_BASE_URL", ""):
            url = svc.build_join_url("ABCD1234", "http://192.168.1.20:3000", None)
        assert url == "http://192.168.1.20:3000/transfer/ABCD1234"

    def test_falls_back_to_referer(self):
        with patch.object(svc.settings, "LAN_TRANSFER_PUBLIC_BASE_URL", ""):
            url = svc.build_join_url("ABCD1234", None, "http://192.168.1.30/dashboard")
        assert url == "http://192.168.1.30/transfer/ABCD1234"

    def test_returns_relative_path_without_origin(self):
        with patch.object(svc.settings, "LAN_TRANSFER_PUBLIC_BASE_URL", ""):
            url = svc.build_join_url("ABCD1234", None, None)
        assert url == "/transfer/ABCD1234"


class TestFeatureAvailability:
    def test_disabled_flag_wins(self):
        with patch.object(svc.settings, "LAN_TRANSFER_ENABLED", False):
            assert svc.is_feature_available() is False

    def test_low_disk_pauses_feature(self):
        with (
            patch.object(svc.settings, "LAN_TRANSFER_ENABLED", True),
            patch.object(svc.settings, "LAN_TRANSFER_MIN_FREE_BYTES", 100),
            patch.object(svc, "get_disk_usage", return_value=(1000, 950, 50)),
        ):
            assert svc.is_feature_available() is False

    def test_ensure_raises_forbidden_when_disabled(self):
        with patch.object(svc.settings, "LAN_TRANSFER_ENABLED", False), pytest.raises(Forbidden):
            svc.ensure_feature_available()

    def test_ensure_raises_insufficient_storage(self):
        with (
            patch.object(svc.settings, "LAN_TRANSFER_ENABLED", True),
            patch.object(svc.settings, "LAN_TRANSFER_MIN_FREE_BYTES", 100),
            patch.object(svc, "get_disk_usage", return_value=(1000, 950, 50)),
            pytest.raises(InsufficientStorage),
        ):
            svc.ensure_feature_available()


class TestResolveLimits:
    def test_uses_user_storage_quota(self):
        user = SimpleNamespace(is_admin=False, storage_quota=1073741824)
        assert svc.resolve_limits(user) == (1073741824, 1073741824)

    def test_admin_shares_same_pool(self):
        user = SimpleNamespace(is_admin=True, storage_quota=4294967296)
        assert svc.resolve_limits(user) == (4294967296, 4294967296)

    def test_none_quota_falls_back_to_zero(self):
        user = SimpleNamespace(is_admin=False, storage_quota=None)
        assert svc.resolve_limits(user) == (0, 0)


class TestSameSubnetHint:
    def test_disabled_returns_false(self):
        with patch.object(svc.settings, "LAN_TRANSFER_REQUIRE_SAME_SUBNET", False):
            assert svc._same_subnet_hint("8.8.8.8") is False

    def test_private_ip_is_same_subnet_by_default(self):
        with (
            patch.object(svc.settings, "LAN_TRANSFER_REQUIRE_SAME_SUBNET", True),
            patch.object(svc.settings, "LAN_TRANSFER_ALLOWED_CIDRS", ""),
        ):
            assert svc._same_subnet_hint("192.168.1.5") is False

    def test_public_ip_hints_different_subnet(self):
        with (
            patch.object(svc.settings, "LAN_TRANSFER_REQUIRE_SAME_SUBNET", True),
            patch.object(svc.settings, "LAN_TRANSFER_ALLOWED_CIDRS", ""),
        ):
            assert svc._same_subnet_hint("8.8.8.8") is True

    def test_allowed_cidrs_match(self):
        with (
            patch.object(svc.settings, "LAN_TRANSFER_REQUIRE_SAME_SUBNET", True),
            patch.object(svc.settings, "LAN_TRANSFER_ALLOWED_CIDRS", "10.0.0.0/8,192.168.0.0/16"),
        ):
            assert svc._same_subnet_hint("10.1.2.3") is False

    def test_allowed_cidrs_mismatch(self):
        with (
            patch.object(svc.settings, "LAN_TRANSFER_REQUIRE_SAME_SUBNET", True),
            patch.object(svc.settings, "LAN_TRANSFER_ALLOWED_CIDRS", "10.0.0.0/8"),
        ):
            assert svc._same_subnet_hint("192.168.1.5") is True

    def test_invalid_ip_hints_different_subnet(self):
        with (
            patch.object(svc.settings, "LAN_TRANSFER_REQUIRE_SAME_SUBNET", True),
            patch.object(svc.settings, "LAN_TRANSFER_ALLOWED_CIDRS", ""),
        ):
            assert svc._same_subnet_hint("not-an-ip") is True


class TestCapacityReservation:
    @pytest.mark.asyncio
    async def test_reserve_within_limit(self):
        room = SimpleNamespace(id=uuid4(), max_total_size=1000)
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.incrby = AsyncMock(return_value=400)
            mock_redis.expire = AsyncMock()
            mock_redis.decrby = AsyncMock()
            await svc.reserve_capacity(room, 500, 400)
            mock_redis.incrby.assert_awaited_once_with(svc._reserved_key(room.id), 400)
            mock_redis.decrby.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reserve_rejects_over_limit_and_rolls_back(self):
        room = SimpleNamespace(id=uuid4(), max_total_size=1000)
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.incrby = AsyncMock(return_value=700)
            mock_redis.expire = AsyncMock()
            mock_redis.decrby = AsyncMock()
            with pytest.raises(InsufficientStorage):
                await svc.reserve_capacity(room, 500, 700)
            mock_redis.decrby.assert_awaited_once_with(svc._reserved_key(room.id), 700)

    @pytest.mark.asyncio
    async def test_release_ignores_non_positive_size(self):
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.decrby = AsyncMock()
            await svc.release_capacity(uuid4(), 0)
            mock_redis.decrby.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_release_deletes_key_when_empty(self):
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.decrby = AsyncMock(return_value=0)
            mock_redis.delete = AsyncMock()
            await svc.release_capacity(uuid4(), 100)
            mock_redis.delete.assert_awaited_once()


class TestRoomRateLimit:
    @pytest.mark.asyncio
    async def test_skips_without_jti(self):
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.incr = AsyncMock()
            await svc.check_room_rate_limit(uuid4(), None, 10)
            mock_redis.incr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_when_exceeded(self):
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.incr = AsyncMock(return_value=11)
            mock_redis.expire = AsyncMock()
            with pytest.raises(RateLimited):
                await svc.check_room_rate_limit(uuid4(), "jti-1", 10)

    @pytest.mark.asyncio
    async def test_redis_failure_is_swallowed(self):
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.incr = AsyncMock(side_effect=RuntimeError("redis down"))
            await svc.check_room_rate_limit(uuid4(), "jti-1", 10)

    @pytest.mark.asyncio
    async def test_bucket_uses_separate_counter_key(self):
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.incr = AsyncMock(return_value=1)
            mock_redis.expire = AsyncMock()
            await svc.check_room_rate_limit(uuid4(), "jti-1", 10, bucket="list")
            key = mock_redis.incr.await_args.args[0]
            assert key.endswith(":list:jti-1")


class TestRoomCodeGeneration:
    @pytest.mark.asyncio
    async def test_code_length_and_charset(self):
        db = AsyncMock()
        db.scalar = AsyncMock(return_value=0)
        code = await svc._generate_code(db)
        assert len(code) == svc.ROOM_CODE_LEN
        assert all(c in svc.ROOM_CODE_CHARS for c in code)

    @pytest.mark.asyncio
    async def test_retries_when_code_taken(self):
        db = AsyncMock()
        db.scalar = AsyncMock(side_effect=[1, 1, 0])
        code = await svc._generate_code(db)
        assert len(code) == svc.ROOM_CODE_LEN


class TestTimeHelpers:
    def test_as_aware_marks_naive_datetime(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        assert svc._as_aware(naive).tzinfo is UTC

    def test_as_aware_keeps_aware_datetime(self):
        aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert svc._as_aware(aware) is aware

    def test_expired_room_detected(self):
        room = SimpleNamespace(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        assert svc._is_expired(room) is True

    def test_active_room_not_expired(self):
        room = SimpleNamespace(expires_at=datetime.now(UTC) + timedelta(hours=1))
        assert svc._is_expired(room) is False


class TestCreateRoom:
    @pytest.mark.asyncio
    async def test_create_room_sets_fields(self):
        db = AsyncMock()
        db.scalar = AsyncMock(return_value=0)
        db.add = lambda record: None
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        owner = SimpleNamespace(id=uuid4(), is_admin=False, storage_quota=1073741824)
        with (
            patch.object(svc.settings, "LAN_TRANSFER_ENABLED", True),
            patch.object(svc, "get_disk_usage", return_value=(10**12, 0, 10**12)),
        ):
            room = await svc.create_room(db, owner, title="我的房间", password="secret1", ttl_hours=6)
        assert room.code and len(room.code) == svc.ROOM_CODE_LEN
        assert room.title == "我的房间"
        assert room.password_hash
        assert room.max_total_size == 1073741824
        ttl = (svc._as_aware(room.expires_at) - datetime.now(UTC)).total_seconds()
        assert 6 * 3600 - 120 < ttl <= 6 * 3600

    @pytest.mark.asyncio
    async def test_rejects_when_active_rooms_reach_limit(self):
        db = AsyncMock()
        db.scalar = AsyncMock(return_value=5)
        owner = SimpleNamespace(id=uuid4(), is_admin=False, storage_quota=1073741824)
        with (
            patch.object(svc.settings, "LAN_TRANSFER_ENABLED", True),
            patch.object(svc.settings, "LAN_TRANSFER_MAX_ACTIVE_ROOMS", 5),
            patch.object(svc, "get_disk_usage", return_value=(10**12, 0, 10**12)),
            pytest.raises(Conflict),
        ):
            await svc.create_room(db, owner)

    @pytest.mark.asyncio
    async def test_allows_when_below_active_room_limit(self):
        db = AsyncMock()
        db.scalar = AsyncMock(side_effect=[4, 0])
        db.add = lambda record: None
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        owner = SimpleNamespace(id=uuid4(), is_admin=False, storage_quota=1073741824)
        with (
            patch.object(svc.settings, "LAN_TRANSFER_ENABLED", True),
            patch.object(svc.settings, "LAN_TRANSFER_MAX_ACTIVE_ROOMS", 5),
            patch.object(svc, "get_disk_usage", return_value=(10**12, 0, 10**12)),
        ):
            room = await svc.create_room(db, owner)
        assert room.max_total_size == 1073741824


class TestOwnerCapacity:
    @pytest.mark.asyncio
    async def test_reserve_owner_capacity_rejects_when_exceeded(self):
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.incrby = AsyncMock(return_value=1073741824)
            mock_redis.expire = AsyncMock()
            mock_redis.decrby = AsyncMock()
            with pytest.raises(QuotaExceeded):
                await svc.reserve_owner_capacity(uuid4(), 1024, 1073741824, 1073741824)
            mock_redis.decrby.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reserve_owner_capacity_accepts_within_quota(self):
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.incrby = AsyncMock(return_value=2048)
            mock_redis.expire = AsyncMock()
            await svc.reserve_owner_capacity(uuid4(), 0, 1073741824, 2048)
            mock_redis.decrby.assert_not_called()

    @pytest.mark.asyncio
    async def test_owner_pool_spans_multiple_rooms(self):
        owner_id = uuid4()
        with patch.object(svc, "redis_client") as mock_redis:
            mock_redis.incrby = AsyncMock(side_effect=[536870912, 1073741824, 1610612736])
            mock_redis.expire = AsyncMock()
            mock_redis.decrby = AsyncMock()
            await svc.reserve_owner_capacity(owner_id, 0, 1073741824, 536870912)
            await svc.reserve_owner_capacity(owner_id, 0, 1073741824, 536870912)
            with pytest.raises(QuotaExceeded):
                await svc.reserve_owner_capacity(owner_id, 0, 1073741824, 536870912)
        assert mock_redis.incrby.await_args.args[0] == f"lan_owner:{owner_id}:reserved"

    @pytest.mark.asyncio
    async def test_reserve_room_capacity_rolls_back_room_on_owner_failure(self):
        room = SimpleNamespace(id=uuid4(), owner_id=uuid4(), max_total_size=1073741824)
        db = AsyncMock()
        db.scalar = AsyncMock(return_value=SimpleNamespace(used_storage=0, storage_quota=1073741824))
        with (
            patch.object(svc, "get_room_used", AsyncMock(return_value=0)),
            patch.object(svc, "reserve_capacity", AsyncMock()),
            patch.object(svc, "reserve_owner_capacity", AsyncMock(side_effect=QuotaExceeded("满"))),
            patch.object(svc, "release_capacity", AsyncMock()) as mock_release,
            pytest.raises(QuotaExceeded),
        ):
            await svc._reserve_room_capacity(db, room, 1024)
        mock_release.assert_awaited_once_with(room.id, 1024)
