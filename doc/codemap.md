# 后端符号索引（自动生成）

由 `make map` 生成，请勿手工编辑。修改 `backend/app` 后重新生成。

覆盖 `backend/app` 下 68 个 Python 文件。`L<数字>` 为定义起始行号，可据此定向读取行区间。

## 目录

- (root): `__init__`、`main`
- api: `admin`、`api`、`auth`、`backups`、`deps`、`files`、`folders`、`health`、`lan_transfer`、`shares`、`tasks`、`users`、`ws`
- core: `alerting`、`celery_app`、`client_ip`、`config`、`exceptions`、`logging`、`redis`、`security`、`smtp`、`storage`、`webhook`、`ws_manager`
- db: `base`、`base_class`
- middleware: `__init__`、`csrf`、`rate_limit`、`request_logging`、`security_headers`
- models: `__init__`、`file`、`folder`、`share`、`transfer_room`、`user`
- schemas: `__init__`、`backup`、`file`、`folder`、`reset_password`、`share`、`token`、`transfer_room`、`user`
- services: `admin_service`、`auth_service`、`backup_service`、`email_service`、`file_multipart`、`file_service`、`file_validation`、`folder_service`、`health_service`、`lan_transfer_service`、`reset_password_service`、`share_service`、`storage_accounting`、`user_service`
- tasks: `__init__`、`alert_tasks`、`backup_tasks`、`email_tasks`、`thumbnail_tasks`

## 符号

### `backend/app/api/deps.py`

- `def _serialize_user(user)` L23
- `def _deserialize_user(data)` L40
- `async def invalidate_user_cache(user_id)` L61
- `async def get_current_user(request, token, db)` L72
- `async def get_full_user(user, db)` L124
- `async def get_current_admin(current_user)` L137
- `class RoomContext` L146
- `async def get_room_context(request, db)` L152

### `backend/app/api/v1/endpoints/admin.py`

- `async def get_admin_stats(_, db)` L16
- `async def list_users(skip, limit, _, db)` L25
- `async def update_user(user_id, data, current_admin, db)` L35
- `async def delete_user(user_id, current_admin, db)` L55
- `async def recalculate_storage(user_id, _, db)` L66

### `backend/app/api/v1/endpoints/auth.py`

- `async def register(data, db)` L20
- `async def login(request, response, data, db)` L26
- `async def forgot_password(data, db)` L47
- `async def reset_password(data, db)` L56
- `async def get_security_question(data, db)` L65
- `async def reset_password_by_security(data, db)` L76
- `async def logout(request, response)` L85
- `async def refresh_token(request, response, db)` L91

### `backend/app/api/v1/endpoints/backups.py`

- `async def list_backups(_)` L13
- `async def trigger_backup(_)` L18
- `async def download_backup(timestamp, file, _)` L24
- `async def delete_backup(timestamp, _)` L40

### `backend/app/api/v1/endpoints/files.py`

- `async def _acquire_concurrent_slot(user_id, slot_type, max_slots)` L26
- `async def _release_concurrent_slot(key)` L40
- `async def upload_file(request, file, folder_id, db, current_user)` L45
- `async def list_files(skip, limit, file_type, folder_id, all_folders, cursor, db, current_user)` L96
- `async def search_files(keyword, skip, limit, cursor, db, current_user)` L113
- `async def move_files(body, db, current_user)` L126
- `async def list_trash(skip, limit, cursor, db, current_user)` L137
- `async def get_file(file_id, db, current_user)` L149
- `async def preview_file(file_id, db, current_user)` L161
- `async def get_thumbnail(file_id, db, current_user)` L174
- `async def download_file(file_id, db, current_user)` L190
- `async def delete_file(file_id, db, current_user)` L207
- `async def restore_file(file_id, db, current_user)` L230
- `async def purge_file(file_id, db, current_user)` L243
- `async def multipart_init(body, current_user)` L256
- `async def multipart_upload_part(storage_key, upload_id, part_number, part, current_user)` L285
- `async def multipart_complete(body, db, current_user)` L304
- `async def multipart_abort(storage_key, upload_id, current_user)` L346

### `backend/app/api/v1/endpoints/folders.py`

- `async def create_folder(body, db, current_user)` L24
- `async def list_folder_contents(folder_id, skip, limit, db, current_user)` L34
- `async def rename_folder(folder_id, body, db, current_user)` L51
- `async def delete_folder(folder_id, db, current_user)` L64
- `async def list_trash_folders(skip, limit, db, current_user)` L77
- `async def restore_folder(folder_id, db, current_user)` L91
- `async def purge_folder(folder_id, db, current_user)` L104

### `backend/app/api/v1/endpoints/health.py`

- `async def health()` L10
- `async def health_ready()` L20

### `backend/app/api/v1/endpoints/lan_transfer.py`

- `def _room_payload(room, used_size, file_count, join_url)` L37
- `def _file_item(record, uploader)` L53
- `def _upload_size(file)` L65
- `async def create_room(request, body, db, current_user)` L75
- `async def get_room_detail(room_id, request, db, current_user)` L97
- `async def close_room(room_id, db, current_user)` L115
- `async def join_room(request, code, body, db)` L127
- `async def list_room_files(ctx, db)` L155
- `async def upload_room_file(file, ctx, db)` L172
- `async def init_room_multipart(body, ctx, db)` L192
- `async def upload_room_multipart_part(request, upload_id, part_number, ctx)` L210
- `async def complete_room_multipart(body, ctx, db)` L223
- `async def abort_room_multipart(upload_id, storage_key, ctx)` L243
- `async def download_room_file(request, file_id, ctx, db)` L254
- `async def delete_room_file(file_id, ctx, db)` L296

### `backend/app/api/v1/endpoints/shares.py`

- `async def create_share(file_id, body, db, current_user)` L25
- `async def list_shares(skip, limit, db, current_user)` L48
- `async def delete_share(share_id, db, current_user)` L59
- `async def get_share_info(token, db)` L71
- `async def verify_share(request, token, body, db)` L82
- `async def download_shared_file(request, token, extract_code, db)` L93

### `backend/app/api/v1/endpoints/tasks.py`

- `async def get_task_status(task_id, _)` L11
- `async def get_active_tasks(_)` L24

### `backend/app/api/v1/endpoints/users.py`

- `async def read_me(current_user)` L14
- `async def upload_avatar(file, current_user, db)` L19
- `async def get_avatar(current_user)` L32
- `async def update_profile(data, current_user, db)` L40
- `async def change_password(request, data, current_user, db)` L51
- `async def update_security_question(data, current_user, db)` L64

### `backend/app/api/v1/endpoints/ws.py`

- `async def _authenticate(ws)` L20
- `async def ws_connect(ws)` L81

### `backend/app/core/alerting.py`

- `class AlertManager` L16
  - `def __new__()` L20
  - `def _init()` L28
  - `def _should_alert(key)` L32
  - `def _build_text(record)` L41
  - `def notify(record)` L54
  - `async def _async_fallback_webhook(text)` L89
  - `async def _async_fallback_email(subject, text)` L95
  - `def _on_fallback_task_done(task)` L102
  - `def _fallback_webhook(text)` L109
  - `def _fallback_email(subject, text)` L123
- `def alert_sink(message)` L148

### `backend/app/core/celery_app.py`

- `def _build_celery_url(base_url, db)` L7
- `def _mask_credentials(url)` L16

### `backend/app/core/client_ip.py`

- `def get_trusted_proxies()` L10
- `def _resolve(direct_ip, xff, x_real_ip)` L16
- `def get_client_ip(request)` L28
- `def get_client_ip_from_scope(scope)` L37

### `backend/app/core/config.py`

- `class Settings`(BaseSettings) L7
  - `def _validate_secret_key(v)` L128
- `def get_settings()` L153

### `backend/app/core/exceptions.py`

- `class AppError`(Exception) L6
  - `def __init__(message)` L11
  - `def to_payload()` L16
- `class ValidationFailed`(AppError) L23
- `class QuotaExceeded`(AppError) L29
- `class PayloadTooLarge`(AppError) L35
- `class NotFound`(AppError) L41
- `class Gone`(AppError) L47
- `class Forbidden`(AppError) L53
- `class Conflict`(AppError) L59
- `class InsufficientStorage`(AppError) L65
- `class UnsupportedMediaType`(AppError) L71
- `class Unauthorized`(AppError) L77
- `class RateLimited`(AppError) L83
- `class ServiceUnavailable`(AppError) L89
- `def register_exception_handlers(app)` L95

### `backend/app/core/logging.py`

- `def _sanitize(obj, depth)` L29
- `def _json_patcher(record)` L41
- `def setup_logging()` L78

### `backend/app/core/redis.py`

- `async def ping_redis()` L24
- `async def close_redis()` L31
- `async def close_redis_pubsub()` L35

### `backend/app/core/security.py`

- `def hash_password(password)` L12
- `def verify_password(plain, hashed)` L16
- `def hash_security_answer(answer)` L21
- `def verify_security_answer(plain, hashed)` L26
- `def _get_signing_key()` L36
- `def _get_verifying_key()` L47
- `def _create_token(data, expires_delta, token_type)` L61
- `def create_access_token(data)` L68
- `def create_refresh_token(data)` L72
- `def create_room_token(room_id, role, subject, expires_delta)` L79
- `def decode_token(token)` L87
- `async def revoke_token(token)` L94

### `backend/app/core/smtp.py`

- `def resolve_smtp()` L7
- `def send_smtp_message(message, recipients)` L17

### `backend/app/core/storage.py`

- `async def init_s3_clients()` L32
- `async def close_s3_clients()` L61
- `async def get_s3_client()` L76
- `async def get_presigned_s3_client()` L83
- `async def ensure_bucket()` L89
- `async def upload_file(storage_key, data, mime_type)` L127
- `async def upload_fileobj(storage_key, fileobj, mime_type)` L137
- `def _is_async_readable(stream)` L147
- `async def _read_chunk(stream, size)` L152
- `async def upload_stream_multipart(storage_key, stream, mime_type, total_size, chunk_size, max_size)` L162
- `async def delete_file(storage_key)` L236
- `async def batch_delete_files(storage_keys)` L244
- `async def get_presigned_download_url(storage_key, expires, filename)` L264
- `async def get_presigned_preview_url(storage_key, mime_type, filename, expires)` L285
- `async def create_multipart(storage_key, mime_type)` L307
- `async def upload_part(storage_key, upload_id, part_number, data)` L317
- `async def complete_multipart(storage_key, upload_id, parts)` L334
- `async def head_object_size(storage_key)` L348
- `async def head_object(storage_key)` L357
- `async def open_object_stream(storage_key, range_header)` L366
- `async def abort_multipart(storage_key, upload_id)` L375

### `backend/app/core/webhook.py`

- `def build_webhook_payload(text)` L6

### `backend/app/core/ws_manager.py`

- `class ConnectionManager` L17
  - `def __init__()` L18
  - `def connect(user_id, ws)` L25
  - `def disconnect(user_id, ws)` L35
  - `async def send_to_user(user_id, event, data)` L46
  - `async def _send_local(user_id, payload)` L60
  - `async def _publish(user_id, payload)` L71
  - `async def _subscribe_user(user_id)` L82
  - `async def _unsubscribe_user(user_id)` L92
  - `async def _resubscribe()` L102
  - `async def start_pubsub()` L112
  - `async def stop_pubsub()` L125
  - `async def _listen_loop()` L143
  - `async def _consume_messages()` L154
  - `def _unwrap_payload(raw)` L172

### `backend/app/db/base.py`

- `async def get_db()` L24
- `async def dispose_engine()` L29

### `backend/app/db/base_class.py`

- `class Base`(DeclarativeBase) L4

### `backend/app/main.py`

- `def _check_production_security()` L25
- `async def lifespan(app)` L54
- `async def _cleanup_orphan_multipart_uploads()` L102
- `async def _cleanup_expired_rooms()` L160
- `async def _unhandled_exception_handler(request, exc)` L190

### `backend/app/middleware/csrf.py`

- `def _get_cookie_from_scope(scope, name)` L15
- `def _get_header_from_scope(scope, name)` L28
- `class CSRFMiddleware` L36
  - `def __init__(app)` L37
  - `async def __call__(scope, receive, send)` L40
  - `def _build_cookie(token)` L111
  - `async def _run_with_cookie(scope, receive, send, token)` L118

### `backend/app/middleware/rate_limit.py`

- `class RateLimitMiddleware` L17
  - `def __init__(app)` L18
  - `async def __call__(scope, receive, send)` L21
  - `def _get_client_ip(scope)` L89

### `backend/app/middleware/request_logging.py`

- `class RequestLoggingMiddleware` L17
  - `def __init__(app)` L18
  - `async def __call__(scope, receive, send)` L21
  - `async def _send_fallback_500(send, request_id, correlation_id)` L104

### `backend/app/middleware/security_headers.py`

- `class SecurityHeadersMiddleware` L10
  - `def __init__(app)` L11
  - `async def __call__(scope, receive, send)` L14

### `backend/app/models/file.py`

- `class File`(Base) L11

### `backend/app/models/folder.py`

- `class Folder`(Base) L11

### `backend/app/models/share.py`

- `class Share`(Base) L11

### `backend/app/models/transfer_room.py`

- `class TransferRoom`(Base) L11
- `class TransferRoomFile`(Base) L30

### `backend/app/models/user.py`

- `class User`(Base) L11

### `backend/app/schemas/backup.py`

- `class BackupPostgresInfo`(BaseModel) L4
- `class BackupMinioInfo`(BaseModel) L10
- `class BackupManifest`(BaseModel) L15
- `class BackupFile`(BaseModel) L23
- `class BackupInfo`(BaseModel) L29
- `class BackupTriggerResponse`(BaseModel) L38

### `backend/app/schemas/file.py`

- `class FileResponse`(BaseModel) L7
- `class FileListResponse`(BaseModel) L23
- `class FileUploadResponse`(BaseModel) L29
- `class FileMoveRequest`(BaseModel) L38
- `class MultipartInitRequest`(BaseModel) L43
- `class MultipartInitResponse`(BaseModel) L50
- `class MultipartPartRequest`(BaseModel) L57
- `class MultipartCompleteRequest`(BaseModel) L62

### `backend/app/schemas/folder.py`

- `class FolderCreateRequest`(BaseModel) L9
- `class FolderRenameRequest`(BaseModel) L14
- `class FolderResponse`(BaseModel) L18
- `class FolderTrashResponse`(BaseModel) L30
- `class FolderBreadcrumbItem`(BaseModel) L43
- `class FolderListResponse`(BaseModel) L49
- `class FolderTrashListResponse`(BaseModel) L56

### `backend/app/schemas/reset_password.py`

- `class ForgotPasswordRequest`(BaseModel) L6
- `class ResetPasswordRequest`(BaseModel) L10
  - `def _validate_password(v)` L17
- `class SecurityQuestionRequest`(BaseModel) L21
- `class SecurityResetRequest`(BaseModel) L25
  - `def _validate_password(v)` L32

### `backend/app/schemas/share.py`

- `class ShareCreateRequest`(BaseModel) L7
- `class ShareCreateResponse`(BaseModel) L11
- `class ShareItemResponse`(BaseModel) L22
- `class ShareListResponse`(BaseModel) L37
- `class ShareInfoResponse`(BaseModel) L42
- `class ShareVerifyRequest`(BaseModel) L51
- `class ShareVerifyResponse`(BaseModel) L55

### `backend/app/schemas/token.py`

- `class LoginResponse`(BaseModel) L4

### `backend/app/schemas/transfer_room.py`

- `class RoomCreateRequest`(BaseModel) L7
- `class RoomJoinRequest`(BaseModel) L13
- `class RoomResponse`(BaseModel) L17
- `class RoomJoinResponse`(BaseModel) L31
- `class RoomFileItem`(BaseModel) L43
- `class RoomFileListResponse`(BaseModel) L56
- `class RoomMultipartInitRequest`(BaseModel) L63
- `class RoomMultipartInitResponse`(BaseModel) L70
- `class RoomMultipartPartResponse`(BaseModel) L77
- `class RoomMultipartCompleteRequest`(BaseModel) L82

### `backend/app/schemas/user.py`

- `def _validate_password_complexity(v)` L8
- `class UserCreate`(BaseModel) L18
  - `def _validate_password(v)` L25
- `class UserLogin`(BaseModel) L30
- `class UserResponse`(BaseModel) L35
- `class ProfileUpdate`(BaseModel) L51
- `class SecurityQuestionUpdate`(BaseModel) L55
- `class PasswordChange`(BaseModel) L60
  - `def _validate_new_password(v)` L66
- `class UserUpdate`(BaseModel) L70
- `class UserListItem`(BaseModel) L77
- `class AdminStats`(BaseModel) L91

### `backend/app/services/admin_service.py`

- `async def get_stats(db)` L17
- `async def list_users(db, skip, limit)` L43
- `async def update_user(db, target_id, admin_id, username, storage_quota, is_active, is_admin)` L48
- `async def delete_user(db, target_id, admin_id)` L84

### `backend/app/services/auth_service.py`

- `def get_client_ip(request)` L24
- `async def check_login_rate_limit(client_ip, email)` L28
- `async def record_login_failure(client_ip, email)` L35
- `async def clear_login_rate_limit(client_ip, email)` L50
- `async def authenticate_user(db, email, password)` L55
- `def _apply_token_cookies(response, access_token, refresh_token)` L63
- `def set_auth_cookies(response, user)` L83
- `async def logout(request, response)` L90
- `async def refresh_access_token(request, response, db)` L99
- `async def _revoke_family(family)` L144

### `backend/app/services/backup_service.py`

- `def _backup_root()` L10
- `def _dir_size(path)` L16
- `def _parse_manifest(dir_path)` L25
- `def list_backups()` L37
- `def get_backup_dir(timestamp)` L81
- `def get_backup_file_path(timestamp, filename)` L90
- `async def trigger_backup()` L102
- `def delete_backup(timestamp)` L109

### `backend/app/services/email_service.py`

- `def send_verification_code_async(to_email, code)` L1

### `backend/app/services/file_multipart.py`

- `async def init_multipart_upload(owner, filename, mime_type, total_size, folder_id, part_size, total_parts)` L32
- `async def upload_multipart_part(storage_key, upload_id, part_number, data, owner_id)` L73
- `async def complete_multipart_upload(db, owner, upload_id, storage_key, filename, mime_type, total_size, folder_id, parts)` L118
- `async def abort_multipart_upload(storage_key, upload_id, owner_id)` L211

### `backend/app/services/file_service.py`

- `async def _count_files(db, filters)` L33
- `async def _paginate(db)` L38
- `async def invalidate_file_caches(owner_id)` L87
- `async def create_file(db, owner, filename, fileobj, mime_type, size, folder_id)` L98
- `async def get_file(db, file_id, owner_id)` L159
- `async def list_files(db, owner_id, skip, limit, file_type, folder_id, cursor, all_folders)` L164
- `async def search_files(db, owner_id, keyword, skip, limit, cursor)` L199
- `async def move_files(db, owner_id, file_ids, target_folder_id)` L233
- `async def list_trash_files(db, owner_id, skip, limit, cursor)` L253
- `async def soft_delete_file(db, file_id, owner_id)` L275
- `async def restore_file(db, file_id, owner_id)` L286
- `async def purge_file(db, file_id, owner_id)` L304
- `async def recalculate_used_storage(db, owner_id)` L324
- `async def prepare_upload(user, file_size)` L328
- `async def get_preview_url(file)` L334
- `async def get_thumbnail_url(thumbnail_key)` L340
- `async def get_download_url(file)` L346

### `backend/app/services/file_validation.py`

- `def _canonical_mime(mime_type)` L73
- `def sanitize_filename(name)` L80
- `async def detect_real_mime_type(fileobj, declared)` L89
- `def ensure_mime_allowed(mime_type, allowed)` L116
- `def validate_mime_type(declared, detected)` L122
- `def _is_compatible_mime(declared, detected)` L130
- `def categorize_file_type(mime_type)` L139

### `backend/app/services/folder_service.py`

- `async def create_folder(db, owner_id, name, parent_id)` L16
- `async def _get_folder(db, folder_id, owner_id)` L50
- `async def _get_trashed_folder(db, folder_id, owner_id)` L61
- `async def _collect_subfolder_ids(db, folder_id, owner_id)` L72
- `async def rename_folder(db, folder_id, owner_id, name)` L84
- `async def delete_folder(db, folder_id, owner_id)` L99
- `async def list_trash_folders(db, owner_id, skip, limit)` L130
- `async def restore_folder(db, folder_id, owner_id)` L157
- `async def purge_folder(db, folder_id, owner_id)` L197
- `async def list_folder_contents(db, owner_id, folder_id, skip, limit)` L239
- `async def _get_breadcrumbs(db, folder_id, owner_id)` L286

### `backend/app/services/health_service.py`

- `async def check_postgres()` L12
- `async def check_minio()` L25
- `async def check_redis()` L38
- `async def get_health()` L52

### `backend/app/services/lan_transfer_service.py`

- `def get_disk_usage()` L55
- `def is_feature_available()` L65
- `def ensure_feature_available()` L71
- `def _ensure_disk_for(size)` L78
- `def resolve_limits(user)` L84
- `def _reserved_key(room_id)` L95
- `def _used_key(room_id)` L99
- `def _files_key(room_id)` L103
- `async def _invalidate_room_caches(room_id)` L107
- `async def get_room_used(db, room_id)` L112
- `async def get_room_file_count(db, room_id)` L125
- `async def reserve_capacity(room, used_size, size)` L136
- `async def release_capacity(room_id, size)` L145
- `async def check_room_rate_limit(room_id, jti, limit)` L155
- `async def _generate_code(db)` L171
- `def _now()` L180
- `def _as_aware(value)` L184
- `def _is_expired(room)` L190
- `async def create_room(db, owner, title, password, ttl_hours)` L194
- `async def get_room(db, room_id)` L221
- `async def get_owned_room(db, room_id, owner_id)` L232
- `async def _record_join_failure(code, client_ip)` L239
- `def _same_subnet_hint(client_ip)` L252
- `async def join_room(db, code, password, client_ip)` L269
- `async def list_room_files(db, room_id)` L307
- `async def get_room_file(db, room_id, file_id)` L317
- `def _validate_mime(declared, detected)` L326
- `async def _check_size_and_count(db, room, size)` L333
- `async def _reserve_room_capacity(db, room, size)` L343
- `def _prepare_filename_and_mime(filename, mime_type)` L347
- `async def add_room_file(db, room, uploader_id, filename, fileobj, mime_type, size)` L356
- `async def init_room_multipart(db, room, filename, mime_type, total_size, total_parts)` L413
- `async def upload_room_part(room, upload_id, part_number, data)` L461
- `async def complete_room_multipart(db, room, upload_id, storage_key, filename, mime_type, total_size, parts)` L501
- `async def abort_room_multipart(room, upload_id, storage_key)` L575
- `async def delete_room_file(db, room, file_id)` L595
- `async def close_room(db, room)` L604
- `def build_join_url(code, origin, referer)` L616
- `async def cleanup_expired_rooms()` L629

### `backend/app/services/reset_password_service.py`

- `def _generate_code()` L18
- `async def send_code(db, email)` L22
- `async def reset_password(db, email, code, new_password)` L42
- `async def get_security_question(db, email)` L59
- `async def reset_password_by_security(db, email, answer, new_password)` L67

### `backend/app/services/share_service.py`

- `def _generate_token()` L22
- `def _generate_code()` L26
- `async def create_share(db, file_id, owner_id, expires_days)` L30
- `async def list_shares(db, owner_id, skip, limit)` L76
- `async def delete_share(db, share_id, owner_id)` L113
- `async def get_share_info(db, token)` L123
- `async def verify_share(db, token, extract_code)` L147
- `async def check_share_rate_limit(token, client_ip)` L177
- `async def record_share_verify_failure(token, client_ip)` L184
- `async def clear_share_verify_attempts(token, client_ip)` L195
- `async def verify_share_with_rate_limit(db, token, extract_code, client_ip)` L199
- `async def download_shared_file(db, token, extract_code, client_ip)` L209

### `backend/app/services/storage_accounting.py`

- `def has_room(owner, size)` L11
- `def ensure_quota(owner, size)` L15
- `def add(owner, size)` L20
- `def subtract(owner, size)` L24
- `async def get_owner(db, owner_id)` L28
- `async def adjust(db, owner_id, size)` L33
- `async def recalculate(db, owner_id)` L47

### `backend/app/services/user_service.py`

- `async def create_user(db, data)` L18
- `async def upload_avatar(db, user, content, mime_type)` L44
- `async def get_avatar_url(user)` L60
- `async def update_profile(db, user, username)` L66
- `async def change_password(db, user, old_password, new_password, access_token)` L76
- `async def update_security_question(db, user, question, answer)` L89

### `backend/app/tasks/alert_tasks.py`

- `def send_alert_webhook(text)` L17

### `backend/app/tasks/backup_tasks.py`

- `def trigger_backup()` L21

### `backend/app/tasks/email_tasks.py`

- `def send_verification_email(to_email, code)` L18
- `def send_alert_email(subject, text)` L70

### `backend/app/tasks/thumbnail_tasks.py`

- `def generate_thumbnail(storage_key, file_id)` L22
- `def _run_coroutine(coro)` L70
- `async def _apply_thumbnail_key(file_id, thumb_key)` L79
- `def _update_thumbnail_key(file_id, thumb_key)` L91
