"""Talk to the Telegram Bot API and remember who pressed Start.

The repository is public, so the list of chats is stored encrypted
(bot/state/subscribers.enc). The key is derived from the bot token, which
lives only in the repository's secrets.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.request

STATE_PATH = os.path.join("bot", "state", "subscribers.enc")


class TelegramError(RuntimeError):
    def __init__(self, code: int, description: str, retry_after: int = 0):
        super().__init__(f"Telegram {code}: {description}")
        self.code, self.description, self.retry_after = code, description, retry_after


def call(token: str, method: str, **params):
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(params).encode()
    for attempt in range(3):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                answer = json.load(resp)
        except urllib.error.HTTPError as exc:
            try:
                answer = json.load(exc)
            except Exception:  # not JSON: a gateway error
                answer = {"ok": False, "error_code": exc.code, "description": str(exc)}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == 2:
                raise TelegramError(0, f"network: {exc}")
            time.sleep(3)
            continue
        if answer.get("ok"):
            return answer.get("result")
        retry = int((answer.get("parameters") or {}).get("retry_after") or 0)
        if answer.get("error_code") == 429 and attempt < 2:
            time.sleep(min(retry or 2, 30))
            continue
        raise TelegramError(int(answer.get("error_code") or 0),
                            str(answer.get("description") or "unknown error"), retry)
    raise TelegramError(0, "no answer")


# --------------------------------------------------------------------------
# Encrypted state (HMAC-SHA256 as a stream cipher, then HMAC as the seal)
# --------------------------------------------------------------------------

def _keys(token: str) -> tuple[bytes, bytes]:
    master = hashlib.sha256(b"tender-bot/state/v1|" + token.encode()).digest()
    return (hmac.new(master, b"enc", hashlib.sha256).digest(),
            hmac.new(master, b"mac", hashlib.sha256).digest())


def _stream(key: bytes, nonce: bytes, size: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < size:
        out += hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:size])


def seal(obj, token: str) -> str:
    data = json.dumps(obj, separators=(",", ":")).encode()
    nonce = secrets.token_bytes(16)
    enc_key, mac_key = _keys(token)
    cipher = bytes(a ^ b for a, b in zip(data, _stream(enc_key, nonce, len(data))))
    tag = hmac.new(mac_key, nonce + cipher, hashlib.sha256).digest()
    return base64.b64encode(nonce + cipher + tag).decode()


def unseal(text: str, token: str):
    try:
        raw = base64.b64decode(text.strip())
        nonce, cipher, tag = raw[:16], raw[16:-32], raw[-32:]
        enc_key, mac_key = _keys(token)
        if not hmac.compare_digest(tag, hmac.new(mac_key, nonce + cipher, hashlib.sha256).digest()):
            return None
        data = bytes(a ^ b for a, b in zip(cipher, _stream(enc_key, nonce, len(cipher))))
        return json.loads(data)
    except Exception:
        return None


def load_state(token: str, path: str = STATE_PATH) -> dict:
    state = None
    try:
        with open(path, encoding="utf-8") as fh:
            state = unseal(fh.read(), token)
        if state is None:
            print("! The saved list of chats could not be opened (was the bot token changed?). "
                  "Starting a new list: everyone needs to press Start again.")
    except FileNotFoundError:
        pass
    state = state or {}
    state.setdefault("subs", [])
    state.setdefault("offset", 0)
    return state


def save_state(state: dict, token: str, path: str = STATE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(seal(state, token) + "\n")


# --------------------------------------------------------------------------
# Bot behaviour
# --------------------------------------------------------------------------

def _keyboard(chat_id: int, app_url: str | None, label: str):
    if not app_url:
        return None
    # a Mini App button only works in a private chat; groups and channels get a link
    button = ({"text": label, "web_app": {"url": app_url}} if int(chat_id) > 0
              else {"text": label, "url": app_url})
    return {"inline_keyboard": [[button]]}


def send(token: str, chat_id: int, text: str, app_url: str | None, label: str) -> None:
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
              "link_preview_options": {"is_disabled": True}}
    markup = _keyboard(chat_id, app_url, label)
    if markup:
        params["reply_markup"] = markup
    call(token, "sendMessage", **params)


def extra_chats() -> list[int]:
    """Optional fixed recipients from the TELEGRAM_CHAT_ID secret (comma separated)."""
    out = []
    for part in (os.environ.get("TELEGRAM_CHAT_ID") or "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.append(int(part))
    return out


def sync_inbox(token: str, state: dict) -> tuple[list[int], list[int], list[int]]:
    """Read new messages. Returns (joined, left, others) chat ids."""
    joined: list[int] = []
    left: list[int] = []
    others: list[int] = []
    updates = call(token, "getUpdates", offset=state.get("offset", 0), timeout=0,
                   allowed_updates=["message", "my_chat_member"])
    subs = set(state["subs"])
    for upd in updates or []:
        state["offset"] = max(state.get("offset", 0), upd["update_id"] + 1)
        member = upd.get("my_chat_member")
        if member:
            chat = member["chat"]["id"]
            if member.get("new_chat_member", {}).get("status") in ("kicked", "left"):
                subs.discard(chat)
            continue
        msg = upd.get("message") or {}
        chat = (msg.get("chat") or {}).get("id")
        if chat is None:
            continue
        text = (msg.get("text") or "").strip().lower()
        private = (msg.get("chat") or {}).get("type") == "private"
        if text.startswith("/stop"):
            subs.discard(chat)
            left.append(chat)
        elif text.startswith("/start"):
            subs.add(chat)
            joined.append(chat)
        elif not private:
            continue  # ordinary chatter in a group is none of the bot's business
        elif chat in subs:
            others.append(chat)
        else:
            subs.add(chat)  # in a private chat any first message counts as joining
            joined.append(chat)
    state["subs"] = sorted(subs)
    # someone who joined and left within the same hour gets one answer, not two
    joined = [c for c in dict.fromkeys(joined) if c in subs]
    left = [c for c in dict.fromkeys(left) if c not in subs]
    others = [c for c in dict.fromkeys(others) if c in subs and c not in joined]
    return joined, left, others


def broadcast(token: str, state: dict, text: str, app_url: str | None, label: str) -> int:
    sent = 0
    for chat in list(dict.fromkeys(state["subs"] + extra_chats())):
        try:
            send(token, chat, text, app_url, label)
            sent += 1
        except TelegramError as exc:
            gone = exc.code == 403 or "chat not found" in exc.description.lower()
            if gone and chat in state["subs"]:
                state["subs"].remove(chat)
            print(f"! could not message one chat: {exc.description}")
        time.sleep(0.05)
    return sent


def setup(token: str, app_url: str | None, texts) -> None:
    """Menu button, description and command list. Safe to repeat."""
    call(token, "setMyCommands",
         commands=[{"command": c, "description": d} for c, d in texts.COMMANDS])
    call(token, "setMyDescription", description=texts.DESCRIPTION)
    call(token, "setMyShortDescription", short_description=texts.SHORT_DESCRIPTION)
    if app_url:
        call(token, "setChatMenuButton",
             menu_button={"type": "web_app", "text": texts.MENU, "web_app": {"url": app_url}})
