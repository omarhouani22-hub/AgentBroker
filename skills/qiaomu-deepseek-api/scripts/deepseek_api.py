#!/usr/bin/env python3
"""A small command-line client for the official DeepSeek application APIs."""
from __future__ import annotations

import argparse
import base64
import getpass
import ipaddress
import json
import mimetypes
import os
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave
from pathlib import Path

ORIGIN = "https://api.deepseek.com"
MODEL = "deepseek-flash"
KEYS_URL = "https://platform.deepseek.com/api_keys"
VOICES = (
    {"id": "stella", "label": "海星 / Stella", "description": "女声 / Female", "default": True},
    {"id": "tide", "label": "暗潮 / Tide", "description": "男声 / Male", "default": False},
)
MIB = 1024 * 1024
JSON_LIMIT = 32 * MIB
AUDIO_LIMIT = 24_000 * 2 * 60 * 30
TOOLS = {
    "search": "deepseek_web_search",
    "deep": "deepseek_web_search",
    "read": "deepseek_read_url",
    "image": "deepseek_web_search",
}
IMAGE_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}
FILE_ID = re.compile(r"file-api-[A-Za-z0-9_-]+")


class APIError(Exception):
    def __init__(self, message, code="invalid_input", status=None, **details):
        super().__init__(message)
        self.payload = {"code": code, "message": message, **details}
        if status is not None:
            self.payload["http_status"] = status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def config_path():
    root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config").expanduser()
    if not root.is_absolute():
        raise APIError("XDG_CONFIG_HOME must be an absolute path.")
    return root / "qiaomu-deepseek-api" / "credentials.json"


def validate_key(key):
    if not isinstance(key, str) or not re.fullmatch(r"[!-~]{1,512}", key.strip()):
        raise APIError("The API key must be non-empty ASCII without whitespace.", "invalid_key")
    return key.strip()


def load_key():
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if key.strip():
        return validate_key(key)
    path = config_path()
    if path.is_symlink() or path.parent.is_symlink():
        raise APIError("The credential file and its directory must not be symlinks.", "unsafe_config")
    try:
        with path.open(encoding="utf-8") as file:
            info = os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode) or (os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077):
                raise APIError("Credential file must be a regular file with permissions 600.", "unsafe_config")
            return validate_key(json.load(file)["api_key"])
    except FileNotFoundError:
        raise APIError("Inject DEEPSEEK_API_KEY or run setup in your own terminal.", "missing_key", key_url=KEYS_URL) from None
    except (ValueError, KeyError, TypeError):
        raise APIError("Credential file is invalid. Run setup again.", "invalid_config") from None


def setup(_args):
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise APIError("Run setup in your own interactive terminal.", "terminal_required", key_url=KEYS_URL)
    path = config_path()
    if path.is_symlink() or path.parent.is_symlink():
        raise APIError("The credential file and its directory must not be symlinks.", "unsafe_config")
    print(f"Create an official API key at {KEYS_URL}", file=sys.stderr)
    key = validate_key(getpass.getpass("DeepSeek API key (hidden): "))
    verified = verify_key(Client(key, timeout=30))
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump({"api_key": key}, file)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)
    if os.getenv("DEEPSEEK_API_KEY", "").strip():
        print("The environment key takes precedence. Update it in your host if needed.", file=sys.stderr)
    return {"configured": True, **verified, "path": str(path)}


def verify_key(client, _args=None):
    result = client.request("/models", method="GET")
    models = result.get("data")
    if not isinstance(models, list):
        raise APIError("Model catalog response has no data array.", "bad_response")
    return {"verified": True, "model_count": len(models),
            "flash_listed": any(isinstance(item, dict) and item.get("id") == MODEL for item in models)}


def provider_error(status, raw=None):
    payload = raw.get("error", {}) if isinstance(raw, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    message = payload.get("message")
    if not isinstance(message, str) or not message:
        message = {
            401: "DeepSeek rejected the API key.",
            402: "DeepSeek reports insufficient balance.",
            403: "DeepSeek refused the request.",
            429: "DeepSeek rate limit reached; retry later.",
        }.get(status, "DeepSeek returned an error.")
    return APIError(message[:1200], "provider_error", status, provider_code=payload.get("code"))


class Client:
    def __init__(self, key, timeout=180):
        self.key = key
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, path, payload=None, *, method="POST", multipart=None, audio=False, messages=False, beta=False):
        headers = {"Content-Type": "application/json"}
        if messages:
            headers["x-api-key"] = self.key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = "Bearer " + self.key
        if beta:
            headers["anthropic-beta"] = "files-api-2025-04-14"
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        if multipart is not None:
            data, headers["Content-Type"] = multipart
        request = urllib.request.Request(ORIGIN + path, data, headers, method=method)
        limit = AUDIO_LIMIT if audio else JSON_LIMIT
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                status = response.status
                content_type = response.headers.get_content_type()
                raw = response.read(limit + 1)
        except urllib.error.HTTPError as error:
            with error:
                raw = error.read(8192)
            raise provider_error(error.code, self.decode(raw, strict=False)) from None
        except (OSError, TimeoutError, urllib.error.URLError) as error:
            raise APIError(str(error).replace(self.key, "[REDACTED]"), "network_error") from None
        if len(raw) > limit:
            raise APIError("Response exceeds the client size limit.", "response_limit", status)
        if audio and content_type in {"audio/pcm", "application/octet-stream"}:
            if not raw or len(raw) % 2:
                raise APIError("TTS returned invalid or empty 16-bit PCM.", "bad_audio", status)
            return raw
        result = self.decode(raw)
        if result.get("error"):
            raise provider_error(status, result)
        if audio:
            raise APIError("TTS did not return PCM audio.", "bad_audio", status)
        return result

    def decode(self, raw, strict=True):
        try:
            data = json.loads(raw.decode("utf-8").replace(self.key, "[REDACTED]"))
            if isinstance(data, dict):
                return data
        except (ValueError, UnicodeError):
            pass
        if strict:
            raise APIError("DeepSeek returned an invalid JSON response.", "bad_response")
        return {}


def bounded_text(value, limit, label):
    if not value.strip() or len(value) > limit:
        raise APIError(f"{label} must contain 1 to {limit} characters.")
    return value


def public_url(value):
    try:
        url = urllib.parse.urlsplit(value)
        host = (url.hostname or "").rstrip(".")
        port = url.port
        if (len(value) > 8192 or url.scheme not in ("http", "https") or
                url.username is not None or not host or (port is None and url.netloc.endswith(":")) or
                re.search(r"[\s\x00-\x1f\x7f\\]", value)):
            raise ValueError
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or host.endswith((".local", ".localhost", ".internal")):
                raise ValueError from None
        else:
            if not addr.is_global or addr.is_multicast:
                raise ValueError
    except ValueError:
        raise APIError("Use a public HTTP(S) URL without credentials.") from None
    return value


def read_file(path, limit):
    if not path.is_file():
        raise APIError("Specify a readable regular file.")
    with path.open("rb") as file:
        data = file.read(limit + 1)
    if not data or len(data) > limit:
        raise APIError(f"File must contain 1 to {limit} bytes.")
    return data


def form(path, limit, fields=()):
    boundary = uuid.uuid4().hex
    # The provider uses the suffix as a format hint; do not send the local filename.
    suffix = path.suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,12}", suffix):
        suffix = ".bin"
    media = IMAGE_TYPES.get(suffix) or mimetypes.guess_type("input" + suffix)[0] or "application/octet-stream"
    prefix = b"".join(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields
    )
    prefix += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input{suffix}"\r\n'
               f'Content-Type: {media}\r\n\r\n').encode()
    return prefix + read_file(path, limit) + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def search(client, args):
    query = bounded_text(args.query, 128, "Query")
    if not 1 <= args.count <= 50:
        raise APIError("--count must be between 1 and 50.")
    result = client.request("/v1/tools/search", {"query": query, "count": args.count, "need_content": args.content})
    if not isinstance(result.get("results"), list):
        raise APIError("Missing search results array.", "bad_response")
    return {"empty": not result["results"], "results": result["results"]}


def fetch(client, args):
    result = client.request("/v1/tools/fetch", {"url": public_url(args.url)})
    if not isinstance(result.get("content"), str) or not result["content"].strip():
        raise APIError("No readable page content was returned.", "empty_content")
    return {"url": args.url, "title": result.get("title"), "content": result["content"]}


def ocr(client, args):
    result = client.request("/v1/tools/ocr", multipart=form(args.file, 100 * MIB, (("purpose", args.purpose),)))
    pages = result.get("pages")
    if not isinstance(pages, list) or not pages:
        raise APIError("OCR returned no pages.", "empty_ocr")
    return {**result, "complete": all(page.get("finish_reason") == "stop" for page in pages)}


def asr(client, args):
    result = client.request("/v1/tools/asr", multipart=form(args.file, 8 * MIB))
    if not isinstance(result.get("text"), str):
        raise APIError("ASR returned no transcript field.", "bad_response")
    return {**result, "empty": not result["text"].strip()}


def tts(client, args):
    path = args.output.expanduser()
    if path.suffix.lower() != ".wav":
        raise APIError("--output must end in .wav.")
    if os.path.lexists(path):
        raise APIError("The output already exists. Choose a new file.")
    if not path.parent.is_dir():
        raise APIError("The output directory must already exist.")
    text = args.text if args.text is not None else args.text_file.read_text(encoding="utf-8")
    if not text.strip() or len(text.encode("utf-8")) > 64 * 1024:
        raise APIError("Provide non-empty UTF-8 text no larger than 64 KiB.")
    payload = {"text": text, "voice_id": args.voice, "format": "pcm", "filter_markdown": not args.keep_markdown}
    if len(json.dumps(payload, ensure_ascii=False).encode()) > 64 * 1024:
        raise APIError("The encoded TTS request exceeds 64 KiB.")
    pcm = client.request("/v1/tools/tts", payload, audio=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temp = Path(file.name)
        try:
            with wave.open(file, "wb") as output:
                output.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                output.writeframes(pcm)
            file.flush()
        except Exception:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.link(temp, path)  # Publish the complete WAV without overwriting an existing file.
    finally:
        temp.unlink(missing_ok=True)
    return {"path": str(path.resolve()), "voice": args.voice, "duration_seconds": round(len(pcm) / 48000, 3),
            "sample_rate_hz": 24000, "channels": 1, "sample_bits": 16}


def summarize_chat(result):
    blocks = result.get("content")
    if not isinstance(blocks, list):
        raise APIError("Missing Messages content blocks.", "bad_response")
    text = []
    citations = []
    calls = []
    tool_results = []
    for block in blocks:
        kind = block.get("type")
        if kind == "text":
            text.append(block.get("text", ""))
            citations.extend({k: item.get(k) for k in ("url", "title", "cited_text")}
                             for item in block.get("citations", []))
        elif kind == "server_tool_use":
            calls.append({k: block.get(k) for k in ("id", "name", "kind", "input")})
        elif kind in ("web_search_tool_result", "web_fetch_tool_result"):
            content = block.get("content")
            entries = content if isinstance(content, list) else [content] if isinstance(content, dict) else []
            tool_results.append({
                "tool_use_id": block.get("tool_use_id"),
                "kind": block.get("kind"),
                "entries": [{k: item[k] for k in ("type", "error_code", "url", "title", "snippet", "image_url")
                             if k in item} for item in entries],
            })
    stop = result.get("stop_reason")
    return {
        "status": "refused" if stop == "refusal" else "complete" if stop == "end_turn" else "incomplete",
        "answer": "" if stop == "refusal" else "".join(text),
        "stop_reason": stop, "title": result.get("title"), "citations": citations,
        "tool_calls": calls, "tool_results": tool_results, "usage": result.get("usage"),
    }


def message(client, args, content, beta=False):
    if not 1 <= args.max_tokens <= 8192:
        raise APIError("--max-tokens must be between 1 and 8192.")
    thinking = args.thinking or getattr(args, "web", "off") == "deep"
    payload = {"model": MODEL, "max_tokens": args.max_tokens,
               "thinking": {"type": "enabled" if thinking else "disabled"},
               "messages": [{"role": "user", "content": content}]}
    web = getattr(args, "web", "off")
    if web in TOOLS:
        payload["tools"] = [{"type": TOOLS[web], "name": TOOLS[web]}]
    if args.safety:
        payload["safety_check"] = {"level": "high"}
    if args.title:
        payload["title"] = {"enabled": True}
    if args.reminder:
        payload["messages"].insert(0, {"role": "latest_reminder", "content": args.reminder})
    return summarize_chat(client.request("/anthropic/v1/messages", payload, messages=True, beta=beta))


def chat(client, args):
    bounded_text(args.prompt, 100_000, "Prompt")
    if args.web == "image" and args.image is None:
        raise APIError("--web image requires --image.")
    if args.url and args.web != "read":
        raise APIError("--url is for --web read.")
    prompt = args.prompt
    if args.web == "read":
        if not args.url:
            raise APIError("--web read requires --url.")
        prompt = public_url(args.url) + "\n" + prompt
    if args.image is None:
        return message(client, args, prompt)
    media = IMAGE_TYPES.get(args.image.suffix.lower())
    if not media:
        raise APIError("Use a PNG, JPEG, WebP, or GIF image.")
    picture = base64.b64encode(read_file(args.image, 16 * MIB)).decode("ascii")
    return message(client, args, [
        {"type": "image", "source": {"type": "base64", "media_type": media, "data": picture}},
        {"type": "text", "text": prompt},
    ])


def ask_file(client, args):
    bounded_text(args.prompt, 100_000, "Prompt")
    if not 1 <= args.max_tokens <= 8192:
        raise APIError("--max-tokens must be between 1 and 8192.")
    mode = args.purpose
    if mode == "auto":
        mode = "user_data" if args.file.suffix.lower() in {
            ".txt", ".md", ".csv", ".json", ".xlsx", ".xls", ".epub", ".mobi",
            ".py", ".js", ".ts", ".java", ".go", ".rs", ".html", ".xml",
        } else "text_recognition"
    if args.file.suffix.lower() in IMAGE_TYPES and mode == "user_data":
        raise APIError("For image pixels use chat --image; for image text use ask-file --purpose text_recognition.")
    size_limit = (32 if mode == "user_data" else 100) * MIB
    fields = (("purpose", mode), ("expires_after[anchor]", "created_at"), ("expires_after[seconds]", "3600"))
    uploaded = client.request("/files", multipart=form(args.file, size_limit, fields))
    file_id = uploaded.get("id", "")
    if not isinstance(file_id, str) or not FILE_ID.fullmatch(file_id):
        raise APIError("Upload returned no usable file ID. Check DeepSeek Files for an orphaned upload.", "bad_file_id")
    result = None
    try:
        result = message(client, args, [
            {"type": "document", "source": {"type": "file", "file_id": file_id}},
            {"type": "text", "text": args.prompt},
        ], beta=True)
    except APIError as error:
        result = error
    finally:
        try:
            response = client.request("/files/" + file_id, method="DELETE")
            deleted = response.get("deleted") is True
            cleanup = {"deleted": deleted, **({} if deleted else {"file_id": file_id})}
        except APIError as error:
            cleanup = {"deleted": False, "file_id": file_id, "error": error.payload}
    if isinstance(result, APIError):
        result.payload["cleanup"] = cleanup
        raise result
    return {**result, "purpose": mode, "cleanup": cleanup}


def chat_options(parser):
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--safety", action="store_true", help="Enable DeepSeek safety_check: high")
    parser.add_argument("--title", action="store_true")
    parser.add_argument("--reminder", help="User-provided date,weekday,location,platform,language")
    parser.add_argument("--max-tokens", type=int, default=1500)


def cli_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=180, help="Network timeout in seconds (default: 180)")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="Check whether a key is configured without calling DeepSeek")
    status.set_defaults(action=lambda _: {"configured": bool(load_key()), "verified": False})
    sub.add_parser("verify-key", help="Verify credentials with the official model catalog").set_defaults(action=verify_key)
    sub.add_parser("voices", help="List official voice options without a key").set_defaults(
        action=lambda _: {"voices": VOICES})
    sub.add_parser("setup", help="Set a key from hidden input in your own terminal").set_defaults(action=setup)
    command = sub.add_parser("search", help="Return raw web results")
    command.add_argument("query")
    command.add_argument("--count", type=int, default=5)
    command.add_argument("--content", action="store_true")
    command.set_defaults(action=search)
    command = sub.add_parser("fetch", help="Return Markdown from a public URL")
    command.add_argument("url")
    command.set_defaults(action=fetch)
    command = sub.add_parser("ocr", help="Extract per-page text")
    command.add_argument("file", type=Path)
    command.add_argument("--purpose", choices=("text_recognition", "rich_layout_recognition"), default="text_recognition")
    command.set_defaults(action=ocr)
    command = sub.add_parser("asr", help="Transcribe PCM WAV or Ogg Opus")
    command.add_argument("file", type=Path)
    command.set_defaults(action=asr)
    command = sub.add_parser("tts", help="Write a 24 kHz mono WAV")
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--text-file", type=Path)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--voice", choices=tuple(voice["id"] for voice in VOICES), required=True)
    command.add_argument("--keep-markdown", action="store_true")
    command.set_defaults(action=tts)
    command = sub.add_parser("chat", help="Ask Flash, optionally with built-in web tools or an image")
    chat_options(command)
    command.add_argument("--web", choices=("off", *TOOLS), default="off")
    command.add_argument("--url", help="Public URL for --web read")
    command.add_argument("--image", type=Path)
    command.set_defaults(action=chat)
    command = sub.add_parser("ask-file", help="Upload one file, ask Flash, then delete the upload")
    chat_options(command)
    command.add_argument("file", type=Path)
    command.add_argument("--purpose", choices=("auto", "user_data", "text_recognition", "rich_layout_recognition"), default="auto")
    command.set_defaults(action=ask_file)
    return parser


def main():
    args = cli_parser().parse_args()
    key = None
    try:
        if args.command in ("setup", "status", "voices"):
            result = args.action(args)
        else:
            if not 1 <= args.timeout <= 600:
                raise APIError("--timeout must be between 1 and 600.")
            key = load_key()
            result = args.action(Client(key, args.timeout), args)
        print(json.dumps({"ok": True, "operation": args.command, **result}, ensure_ascii=False))
        return 0
    except (APIError, OSError, UnicodeError) as error:
        detail = error.payload if isinstance(error, APIError) else {"code": "local_io", "message": str(error)}
        rendered = json.dumps({"ok": False, "operation": args.command, "error": detail}, ensure_ascii=False)
        print(rendered.replace(key, "[REDACTED]") if key else rendered, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
