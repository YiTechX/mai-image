import os
import json
import uuid
import re
import time
import random
import base64
import io
from typing import Optional, Callable, Dict, Any
import requests
from PIL import Image
from dotenv import load_dotenv

load_dotenv()


class AuthenticationError(Exception):
    """Raised when the session cookie is expired or invalid."""
    pass


class RateLimitError(Exception):
    """Raised when hitting server rate limits (HTTP 429)."""
    pass


class MaiImageClient:
    """Hardened client for Microsoft AI Playground (mai-image-2-6) with text2image, edit, and image2image."""

    BASE_URL = "https://playground.microsoft.ai"

    def __init__(
        self,
        cookie: Optional[str] = None,
        model_id: str = "mai-image-2-6",
        min_request_interval: float = 2.5,
        max_retries: int = 3,
    ):
        self.cookie = cookie or os.getenv("MAI_COOKIE")
        if not self.cookie:
            raise AuthenticationError(
                "Authentication cookie not found. Please set MAI_COOKIE in .env or pass it to MaiImageClient."
            )
        self.model_id = model_id
        self.min_request_interval = min_request_interval
        self.max_retries = max_retries
        self._last_request_time = 0.0
        self._is_warmed_up = False

        self.session = requests.Session()
        self.session.headers.update({
            "accept": "*/*",
            "accept-language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "content-type": "application/json",
            "cookie": self.cookie,
            "origin": self.BASE_URL,
            "referer": f"{self.BASE_URL}/chat?model={self.model_id}",
            "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
        })

    def _apply_rate_limit(self, extra_jitter: float = 0.0) -> None:
        """Applies randomized jitter delay to simulate human pacing and prevent bot detection."""
        elapsed = time.time() - self._last_request_time
        target_interval = self.min_request_interval + random.uniform(0.6, 2.2) + extra_jitter
        if elapsed < target_interval:
            sleep_duration = target_interval - elapsed
            time.sleep(sleep_duration)
        self._last_request_time = time.time()

    def warmup(self, on_status: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """
        Simulates authentic browser navigation:
        1. Navigates to the chat page via standard document GET request with Chrome headers.
        2. Simulates normal page load and reading duration.
        3. Fetches past conversations and session state as the frontend does.
        """
        if on_status:
            on_status("Visiting website landing page (simulating real browser visit)...")

        nav_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }

        target_page = f"{self.BASE_URL}/chat?model={self.model_id}"
        try:
            resp = self.session.get(target_page, headers=nav_headers, timeout=20)
            if resp.status_code in (401, 403):
                raise AuthenticationError(f"Access denied on page visit (HTTP {resp.status_code}). Cookie expired.")
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to visit page: {e}") from None

        # Human reading / rendering pause
        time.sleep(random.uniform(1.2, 2.4))

        if on_status:
            on_status("Checking active session & conversation state...")

        session_info = self.validate_session()
        self._is_warmed_up = True
        return session_info

    def _safe_post(
        self,
        url: str,
        json_data: dict,
        extra_headers: Optional[dict] = None,
        stream: bool = False,
        timeout: int = 30,
    ) -> requests.Response:
        """Executes POST requests with rate limiting, circuit breakers, and exponential backoff."""
        self._apply_rate_limit()

        headers = extra_headers or {}
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.post(url, json=json_data, headers=headers, stream=stream, timeout=timeout)

                # Circuit breaker on authentication failure
                if response.status_code in (401, 403):
                    raise AuthenticationError(
                        f"Access rejected (HTTP {response.status_code}). Your session cookie has likely expired. "
                        "Please update MAI_COOKIE in your .env file."
                    )

                # Rate limit handling (HTTP 429)
                if response.status_code == 429:
                    if attempt < self.max_retries:
                        backoff = (2 ** attempt) * 5 + random.uniform(1.0, 3.0)
                        time.sleep(backoff)
                        continue
                    raise RateLimitError("Rate limit exceeded (HTTP 429). Please pause and try again later.")

                # Temporary server errors (500, 502, 503, 504)
                if response.status_code >= 500:
                    if attempt < self.max_retries:
                        time.sleep(2 * attempt)
                        continue
                    raise RuntimeError(f"Server error (HTTP {response.status_code}).")

                return response

            except requests.RequestException as e:
                if attempt == self.max_retries:
                    raise RuntimeError(f"Network request failed: {e}") from None
                time.sleep(2.0 * attempt)

        raise RuntimeError("Request failed after maximum retry attempts.")

    def validate_session(self) -> Dict[str, Any]:
        """Pre-flight check to verify if the session cookie is valid and active."""
        self._apply_rate_limit()
        url = f"{self.BASE_URL}/api/trpc/conversations.list?batch=1&input=%7B%220%22%3A%7B%22limit%22%3A1%7D%7D"
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                raise AuthenticationError(
                    f"Session validation failed (HTTP {resp.status_code}). Please refresh MAI_COOKIE in .env."
                )
            data = resp.json()
            items = data[0]["result"]["data"]["items"]
            user_id = items[0].get("userId", "authenticated_user") if items else "authenticated_user"
            return {"valid": True, "user_id": user_id}
        except (requests.RequestException, KeyError, IndexError) as err:
            raise AuthenticationError(f"Unable to validate session credentials: {err}") from None

    def create_conversation(self, title: str = "New Chat") -> str:
        """Creates a new conversation and returns the conversation ID."""
        url = f"{self.BASE_URL}/api/trpc/conversations.create?batch=1"
        payload = {"0": {"title": title, "modelId": self.model_id}}
        headers = {"x-requested-with": "XMLHttpRequest"}

        response = self._safe_post(url, json_data=payload, extra_headers=headers, timeout=20)
        data = response.json()
        try:
            return data[0]["result"]["data"]["id"]
        except (KeyError, IndexError) as err:
            raise RuntimeError("Unexpected response structure while creating conversation.") from err

    def _encode_reference_image(self, image_path: str) -> Dict[str, str]:
        """Reads, resizes, and base64-encodes a reference image for upload."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Reference image not found: {image_path}")

        filename = os.path.basename(image_path)
        with Image.open(image_path) as im:
            im_format = im.format or "JPEG"
            im_rgb = im.convert("RGB")
            # Downscale if exceeding 1024x1024 for speed & reliability
            im_rgb.thumbnail((1024, 1024))
            buf = io.BytesIO()
            im_rgb.save(buf, format="JPEG", quality=85)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

        return {
            "imageBase64": b64_str,
            "imageMimeType": "image/jpeg",
            "imageFileName": filename,
        }

    def add_prompt(
        self,
        conversation_id: str,
        prompt: str,
        source_message_id: Optional[str] = None,
        last_message_id: Optional[str] = None,
        reference_image: Optional[str] = None,
    ) -> str:
        """Adds a prompt (text, edit, or image2image reference) and returns pendingModelMessageId."""
        time.sleep(random.uniform(0.8, 1.8))
        headers = {"x-requested-with": "XMLHttpRequest"}

        if reference_image:
            url = f"{self.BASE_URL}/api/trpc/conversations.addImagePromptAndInitResponse?batch=1"
            img_data = self._encode_reference_image(reference_image)
            item: Dict[str, Any] = {
                "conversationId": conversation_id,
                "text": prompt,
                "modelId": self.model_id,
                "lastMessageId": last_message_id,
                "images": [img_data],
            }
        else:
            url = f"{self.BASE_URL}/api/trpc/conversations.addPromptAndInitResponse?batch=1"
            item = {
                "conversationId": conversation_id,
                "text": prompt,
                "modelId": self.model_id,
                "lastMessageId": last_message_id,
            }
            if source_message_id:
                item["sourceMessageId"] = source_message_id

        payload = {"0": item}
        response = self._safe_post(url, json_data=payload, extra_headers=headers, timeout=60)
        data = response.json()
        try:
            return data[0]["result"]["data"]["modelMessage"]["id"]
        except (KeyError, IndexError) as err:
            raise RuntimeError(f"Unexpected response structure: {data}") from err

    def generate_stream(
        self,
        conversation_id: str,
        pending_model_message_id: str,
        is_first_message: bool = True,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Streams generation progress and extracts the resulting image artifact URL."""
        url = f"{self.BASE_URL}/api/chat/stream"
        payload = {
            "conversationId": conversation_id,
            "modelId": self.model_id,
            "pendingModelMessageId": pending_model_message_id,
            "isFirstMessage": is_first_message,
            "userLocation": {"timezone": "Europe/Istanbul"},
        }

        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        headers = {
            "traceparent": f"00-{trace_id}-{span_id}-01",
            "priority": "u=1, i",
        }

        response = self._safe_post(url, json_data=payload, extra_headers=headers, stream=True, timeout=120)

        image_url = None
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if line.startswith("data:"):
                raw_data = line[5:].strip()
                if raw_data == "[DONE]":
                    break
                try:
                    chunk = json.loads(raw_data)
                    if "error" in chunk:
                        raise RuntimeError(f"Stream generation error: {chunk['error']}")

                    images = chunk.get("images", [])
                    for img in images:
                        if "image_url" in img and "url" in img["image_url"]:
                            image_url = img["image_url"]["url"]

                    if on_status:
                        on_status("Rendering image...")
                except json.JSONDecodeError:
                    continue

        if not image_url:
            raise RuntimeError("Image URL was not returned in the stream response.")

        return image_url

    def download_image(self, relative_or_full_url: str, save_path: str) -> str:
        """Downloads the image artifact with rate safety to the local filesystem."""
        self._apply_rate_limit()
        url = (
            relative_or_full_url
            if relative_or_full_url.startswith("http")
            else f"{self.BASE_URL}{relative_or_full_url}"
        )
        response = self.session.get(url, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download image (HTTP {response.status_code})")

        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(response.content)

        return os.path.abspath(save_path)

    def generate(
        self,
        prompt: str,
        output_file: Optional[str] = None,
        conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        reference_image: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, str]:
        """
        Executes full generation pipeline (text2img, edit, or image2img with reference).
        Supports aspect_ratio: '16:9', '9:16', '4:3', '3:4', '1:1'.
        Returns: {"saved_path": str, "conversation_id": str, "message_id": str}
        """
        if aspect_ratio:
            ar_str = aspect_ratio.strip()
            if ar_str not in prompt:
                prompt = f"{prompt.rstrip()} {ar_str}"

        if not self._is_warmed_up:
            self.warmup(on_status=on_status)

        is_first = conversation_id is None
        if not conversation_id:
            if on_status:
                on_status("Creating session...")
            conversation_id = self.create_conversation(title=prompt[:30])

        if on_status:
            if reference_image:
                on_status(f"Uploading reference image ({os.path.basename(reference_image)}) & submitting prompt...")
            elif source_message_id:
                on_status("Submitting edit prompt...")
            else:
                on_status("Submitting prompt...")

        pending_id = self.add_prompt(
            conversation_id=conversation_id,
            prompt=prompt,
            source_message_id=source_message_id,
            last_message_id=source_message_id,
            reference_image=reference_image,
        )

        if on_status:
            on_status("Generating image...")

        artifact_url = self.generate_stream(
            conversation_id=conversation_id,
            pending_model_message_id=pending_id,
            is_first_message=is_first,
            on_status=on_status,
        )

        if not output_file:
            sanitized = re.sub(r'[\\/*?:"<>| ]', "_", prompt[:25]).strip("_")
            timestamp = uuid.uuid4().hex[:6]
            output_file = os.path.join("outputs", f"{sanitized}_{timestamp}.png")

        if on_status:
            on_status(f"Saving to {output_file}...")

        saved_path = self.download_image(artifact_url, output_file)

        return {
            "saved_path": saved_path,
            "conversation_id": conversation_id,
            "message_id": pending_id,
        }
