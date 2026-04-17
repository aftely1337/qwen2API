import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.api import images
from backend.core import config as core_config
from backend.services.upstream_file_uploader import UpstreamFileUploader
from backend.upstream.payload_builder import build_chat_payload


class _FakeBucket:
    instances = []

    def __init__(self, *args, **kwargs):
        self.put_calls = []
        _FakeBucket.instances.append(self)

    def put_object(self, key, raw, headers=None):
        self.put_calls.append({
            "key": key,
            "raw": raw,
            "headers": headers or {},
        })
        return SimpleNamespace(status=200)


class _FakeUploadClient:
    def __init__(self, sts_data):
        self.sts_data = sts_data
        self.calls = []

    async def _request_json(self, method, path, token, body=None, timeout=30.0):
        self.calls.append({
            "method": method,
            "path": path,
            "token": token,
            "body": body,
            "timeout": timeout,
        })
        return {
            "status": 200,
            "body": json.dumps({"success": True, "data": self.sts_data}),
        }


class _FakeAccountPool:
    def __init__(self):
        self.acc = SimpleNamespace(email="demo@example.com", token="tok-demo")
        self.released = []
        self.rate_limited = []

    async def acquire_wait(self, timeout=30, exclude=None):
        return self.acc

    def release(self, acc):
        self.released.append(acc)

    def mark_rate_limited(self, acc, error_message=""):
        self.rate_limited.append((acc, error_message))


class _FakeQwenClient:
    def __init__(self):
        self.account_pool = _FakeAccountPool()
        self.chat_calls = []
        self.deleted = []

    async def chat_stream_events_with_retry(
        self,
        model,
        content,
        has_custom_tools=False,
        files=None,
        fixed_account=None,
        existing_chat_id=None,
        chat_type="t2t",
        size=None,
    ):
        self.chat_calls.append({
            "model": model,
            "content": content,
            "has_custom_tools": has_custom_tools,
            "files": files,
            "fixed_account": fixed_account,
            "existing_chat_id": existing_chat_id,
            "chat_type": chat_type,
            "size": size,
        })
        yield {"type": "meta", "chat_id": "chat-demo", "acc": self.account_pool.acc}
        yield {"type": "event", "event": {"url": "https://example.com/result.png"}}

    async def list_chats(self, token, limit=20):
        return [{"id": "chat-demo"}]

    async def delete_chat(self, token, chat_id):
        self.deleted.append((token, chat_id))


class _FakeUploader:
    def __init__(self):
        self.calls = []

    async def upload_local_file(self, acc, local_meta):
        self.calls.append({
            "acc": acc,
            "local_meta": local_meta,
        })
        return {
            "remote_ref": {
                "type": "image",
                "id": "remote-file-1",
                "url": "https://signed.example.com/input.jpg",
                "name": "demo.jpg",
                "file_type": "image/jpeg",
                "showType": "image",
                "file_class": "vision",
            }
        }


class _FakeFileStore:
    def __init__(self):
        self.calls = []

    async def save_bytes(self, filename, content_type, raw, purpose):
        self.calls.append({
            "filename": filename,
            "content_type": content_type,
            "raw": raw,
            "purpose": purpose,
        })
        return {
            "filename": filename,
            "path": str(Path(tempfile.gettempdir()) / filename),
            "content_type": content_type,
        }


class ImageEditPayloadBuilderTests(unittest.TestCase):
    def test_t2i_payload_with_reference_image_matches_web_contract(self):
        payload = build_chat_payload(
            "chat-1",
            "qwen3.6-plus",
            "把这张图改成卡通插画风格",
            files=[{"file_type": "image/jpeg"}],
            chat_type="t2i",
            size="16:9",
        )

        self.assertEqual(payload["size"], "16:9")
        self.assertEqual(payload["messages"][0]["chat_type"], "t2i")
        self.assertEqual(payload["messages"][0]["sub_chat_type"], "t2i")
        self.assertEqual(payload["messages"][0]["extra"]["meta"], {"subChatType": "t2i", "size": "16:9"})
        self.assertEqual(payload["messages"][0]["feature_config"], {
            "thinking_enabled": False,
            "output_schema": "phase",
            "research_mode": "normal",
            "auto_thinking": False,
            "thinking_mode": "Fast",
            "auto_search": True,
        })
        self.assertNotIn("mode", payload["messages"][0]["extra"]["meta"])


class ImageEditUploaderContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_local_file_uses_image_shape_and_signed_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "demo.jpg"
            local_path.write_bytes(b"fake-image")
            sts_data = {
                "file_id": "remote-file-1",
                "file_path": "user-1/remote-file-1_demo.jpg",
                "bucketname": "qwen-webui-prod",
                "endpoint": "oss-accelerate.aliyuncs.com",
                "region": "oss-ap-southeast-1",
                "access_key_id": "ak",
                "access_key_secret": "sk",
                "security_token": "sts-token",
                "file_url": "https://signed.example.com/user-1/remote-file-1_demo.jpg?sig=1",
            }
            fake_client = _FakeUploadClient(sts_data)
            uploader = UpstreamFileUploader(fake_client, SimpleNamespace(CONTEXT_UPLOAD_PARSE_TIMEOUT_SECONDS=1))
            acc = SimpleNamespace(email="demo@example.com", token="tok-demo")
            local_meta = {
                "filename": "demo.jpg",
                "path": str(local_path),
                "content_type": "image/jpeg",
            }

            with patch("backend.services.upstream_file_uploader.oss2.StsAuth", return_value=object()), patch(
                "backend.services.upstream_file_uploader.oss2.Bucket",
                _FakeBucket,
            ):
                remote_info = await uploader.upload_local_file(acc, local_meta)

        self.assertEqual(fake_client.calls[0]["body"]["filetype"], "image")
        remote_ref = remote_info["remote_ref"]
        self.assertEqual(remote_ref["type"], "image")
        self.assertEqual(remote_ref["showType"], "image")
        self.assertEqual(remote_ref["file_class"], "vision")
        self.assertEqual(remote_ref["url"], sts_data["file_url"])
        self.assertEqual(remote_ref["file_type"], "image/jpeg")
        self.assertEqual(remote_ref["file"]["meta"], {
            "name": "demo.jpg",
            "size": len(b"fake-image"),
            "content_type": "image/jpeg",
        })


class ImageEditRouteContractTests(unittest.TestCase):
    def test_edits_route_reuses_t2i_with_reference_image(self):
        app = FastAPI()
        app.include_router(images.router)
        app.state.qwen_client = _FakeQwenClient()
        app.state.upstream_file_uploader = _FakeUploader()
        app.state.file_store = _FakeFileStore()

        with patch.object(core_config, "API_KEYS", set()):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/images/edits",
                    data={
                        "prompt": "把这张图改成卡通插画风格",
                        "n": "1",
                        "size": "1024x576",
                        "model": "dall-e-3",
                    },
                    files={"image": ("demo.jpg", b"fake-image", "image/jpeg")},
                )

        self.assertEqual(response.status_code, 200, response.text)
        call = app.state.qwen_client.chat_calls[0]
        self.assertEqual(call["chat_type"], "t2i")
        self.assertEqual(call["size"], "16:9")
        self.assertEqual(call["content"], "把这张图改成卡通插画风格")
        self.assertEqual(call["files"][0]["type"], "image")

    def test_generations_route_uses_raw_prompt_with_t2i_contract(self):
        app = FastAPI()
        app.include_router(images.router)
        app.state.qwen_client = _FakeQwenClient()

        with patch.object(core_config, "API_KEYS", set()):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/images/generations",
                    json={
                        "prompt": "Turn this into a watercolor concept art scene.",
                        "n": 1,
                        "size": "1024x576",
                        "model": "qwen-image",
                    },
                )

        self.assertEqual(response.status_code, 200, response.text)
        call = app.state.qwen_client.chat_calls[0]
        self.assertEqual(call["chat_type"], "t2i")
        self.assertEqual(call["size"], "16:9")
        self.assertEqual(call["content"], "Turn this into a watercolor concept art scene.")
        self.assertEqual(call["files"], None)
