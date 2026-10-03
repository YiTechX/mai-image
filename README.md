<div align="center">

# 🎨 MAI-IMAGE

**An Advanced, Hardened Python Client & CLI for Microsoft AI Playground (`mai-image-2-6` & `mai-image-2-6-flash`)**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/YiTechX/mai-image)
[![Model](https://img.shields.io/badge/default%20model-mai--image--2--6-purple.svg)](https://playground.microsoft.ai/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

*Generate, edit, and transform images using state-of-the-art Microsoft AI models directly from your terminal or Python scripts.*

---

</div>

## 📑 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [How It Works (Reverse-Engineered Protocol)](#-how-it-works-reverse-engineered-protocol)
- [Installation](#-installation)
- [Authentication & Configuration](#-authentication--configuration)
  - [Extracting Your Session Cookie](#extracting-your-session-cookie)
  - [Configuring `.env`](#configuring-env)
- [Command-Line Interface (CLI)](#-command-line-interface-cli)
  - [Command Reference](#command-reference)
  - [1. Single-Prompt Generation](#1-single-prompt-generation)
  - [2. Model Selection (Full vs. Flash)](#2-model-selection-full-vs-flash)
  - [3. Reference Image (Image-to-Image)](#3-reference-image-image-to-image)
  - [4. Multi-Turn Image Editing](#4-multi-turn-image-editing)
  - [5. Interactive Terminal Session](#5-interactive-terminal-session)
  - [6. Session Verification Check](#6-session-verification-check)
- [Python SDK Reference](#-python-sdk-reference)
  - [Basic Text-to-Image](#basic-text-to-image)
  - [Image-to-Image (Reference Image)](#image-to-image-reference-image)
  - [Multi-Turn Image Editing](#multi-turn-image-editing)
  - [Custom Configuration & Callbacks](#custom-configuration--callbacks)
- [Anti-Bot & Security Safeguards](#-anti-bot--security-safeguards)
- [Troubleshooting & FAQ](#-troubleshooting--faq)
- [Disclaimer](#-disclaimer)

---

## 🌟 Overview

**`mai-image`** is an unofficial, production-grade Python client and command-line interface engineered to interface with Microsoft AI Playground's cutting-edge image models:
- **`mai-image-2-6`**: High-fidelity, ultra-detailed photorealistic and artistic rendering (Default).
- **`mai-image-2-6-flash`**: High-speed, low-latency generation optimized for rapid prototyping.

By reverse-engineering the underlying tRPC communication flow and chunked Server-Sent Events (SSE) streaming protocols, `mai-image` allows you to bypass the web UI entirely and integrate image generation directly into automated scripts, pipelines, and interactive terminal workflows.

---

## ✨ Key Features

- **🎯 Native Text-to-Image**: Full support for both `mai-image-2-6` and `mai-image-2-6-flash`.
- **🖼️ Image-to-Image (Reference Image)**: Upload local reference images to guide generation style, composition, and character consistency.
- **🔄 Iterative Multi-Turn Editing**: Seamlessly refine, recolor, and modify previously generated images across conversation turns.
- **🌐 Authentic Browser Simulation (Warmup)**: Mimics authentic Chrome document navigation (`GET /chat?model=...`), complete with browser headers, page-reading pauses, and typing delays.
- **🛡️ Hardened Anti-Bot Evasion**: Randomized request jitter (2.5s – 4.5s), circuit breakers on HTTP 401/403, and exponential backoff retry on HTTP 429 rate limits.
- **💻 Rich Interactive CLI**: Beautiful terminal user interface powered by `rich`, featuring live spinners, status tracking, automatic image viewer launching, and `@image` shortcuts.
- **🔒 Zero-Credential Exposure**: Sensitive session cookies are protected via `.env`, redacted in logs, and strictly excluded via `.gitignore`.

---

## 🔬 How It Works (Reverse-Engineered Protocol)

When an image is requested through the browser on `playground.microsoft.ai`, the web application follows a discrete 5-step lifecycle. `mai-image` faithfully reproduces this exact flow:

```
[1. Browser Warmup]  ──> GET /chat?model=mai-image-2-6 (Simulates human document visit)
                              │
[2. Conversation]    ──> POST /api/trpc/conversations.create?batch=1 (Creates session ID)
                              │
[3. Prompt Init]     ──> POST /api/trpc/conversations.addPromptAndInitResponse (or addImagePrompt...)
                              │
[4. Stream Compute]  ──> POST /api/chat/stream (SSE EventSource stream with W3C traceparent)
                              │
[5. Artifact Fetch]  ──> GET /api/artifacts/{user}/{conv_id}/{message_id}/{hash}.png
```

1. **Browser Warmup**: Dispatches a full Chrome document navigation GET request with `sec-fetch-dest: document` and `sec-fetch-mode: navigate` to warm up the session.
2. **Session Creation**: Triggers `conversations.create` to generate a dedicated server-side `conversationId`.
3. **Prompt Initialization**: Dispatches `conversations.addPromptAndInitResponse` (for text/edits) or `conversations.addImagePromptAndInitResponse` (for reference images) to register the prompt and obtain a `pendingModelMessageId`.
4. **SSE Event Streaming**: Opens an HTTP stream to `/api/chat/stream`, listening for chunked delta events until the relative image artifact URL is emitted.
5. **Artifact Download**: Downloads the binary PNG payload from `/api/artifacts/...` and persists it directly to disk.

---

## 📦 Installation

### Prerequisites
- Python **3.10** or higher
- `pip` package manager

### 1. Clone the Repository
```bash
git clone https://github.com/YiTechX/mai-image.git
cd mai-image
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- `requests`: HTTP session management and streaming.
- `pillow`: Image processing, resizing, and base64 optimization for reference images.
- `rich`: Terminal UI formatting, panels, prompts, and spinners.
- `python-dotenv`: Environment variable loader.

---

## 🔑 Authentication & Configuration

Microsoft AI Playground requires an authenticated session cookie. `mai-image` uses this cookie to authorize requests on your behalf.

### Extracting Your Session Cookie

1. Open your browser (Google Chrome, Edge, Brave, or Firefox).
2. Navigate to [https://playground.microsoft.ai/](https://playground.microsoft.ai/) and sign in with your Microsoft account.
3. Open **Developer Tools** by pressing `F12` (or right-click anywhere and select **Inspect**).
4. Navigate to the **Network** tab.
5. In the Playground, select any model and send a simple message or prompt (e.g., `a cat`).
6. In the Network tab list, look for any request to `addPromptAndInitResponse` or `conversations.list`.
7. Click on the request, go to the **Headers** tab, and locate the **`Cookie`** header.
8. Right-click the cookie value and copy it. It will contain strings such as:
   ```text
   MSCC=cid=...; AppServiceAuthSession=...
   ```

### Configuring `.env`

Create a `.env` file in the root directory (you can copy `.env.example`):

```bash
cp .env.example .env
```

Paste your cookie string inside `.env`:

```env
MAI_COOKIE="MSCC=cid=...; AppServiceAuthSession=..."
```

> ⚠️ **Security Notice:** Never commit your `.env` file to Git. The included `.gitignore` strictly excludes `.env` and all secret files by default.

---

## 💻 Command-Line Interface (CLI)

`mai-image` includes a feature-rich, interactive CLI located in `cli.py`.

### Command Reference

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `prompt` | - | Image generation prompt string | Interactive Mode |
| `--model` | `-m` | Model ID (`mai-image-2-6` or `mai-image-2-6-flash`) | `mai-image-2-6` |
| `--aspect` | `-ar` | Aspect ratio (`16:9`, `9:16`, `4:3`, `3:4`, `1:1`) | `None` |
| `--image` | `-i` | Path to local reference image (Image-to-Image) | `None` |
| `--output` | `-o` | Custom output file destination | `outputs/{slug}_{hash}.png` |
| `--cid` | - | Conversation ID for edit / continuation | `None` |
| `--mid` | - | Source Message ID for edit / continuation | `None` |
| `--open` | - | Automatically opens generated image in default viewer | `False` |
| `--check` | - | Validates session credentials without generating | `False` |
| `--help` | `-h` | Displays help message and command summary | - |

---

### 1. Single-Prompt Generation

Generate an image with a single command:

```bash
python cli.py "a majestic golden eagle perched on a mountain summit, photorealistic 8k"
```

Save to a specific path:
```bash
python cli.py "modern minimalist architectural villa with swimming pool" -o outputs/villa.png
```

Automatically open the image in your system viewer upon completion:
```bash
python cli.py "cyberpunk samurai cat in neon alleyway" --open
```

---

### 2. Model Selection (Full vs. Flash)

By default, the CLI uses the full **`mai-image-2-6`** model for maximum quality. You can switch to the high-speed **`mai-image-2-6-flash`** model with `-m`:

```bash
python cli.py "an abstract geometric sculpture" -m mai-image-2-6-flash
```

---

### 3. Aspect Ratio Selection

Choose your preferred aspect ratio (`16:9`, `9:16`, `4:3`, `3:4`, `1:1`) using `-ar` or `--aspect`:

```bash
# Cinematic widescreen (16:9)
python cli.py "cinematic drone shot over misty fjords at sunrise" -ar 16:9

# Mobile wallpaper / Portrait (9:16)
python cli.py "cyberpunk anime girl in rain under neon umbrella" -ar 9:16
```

---

### 4. Reference Image (Image-to-Image)

Provide a local image to serve as a stylistic or compositional reference:

```bash
python cli.py "transform this character into a soft pastel watercolor painting" -i outputs/my_character.png -o outputs/watercolor_version.png
```

*The client automatically optimizes, resizes, and base64-encodes the reference image before uploading.*

---

### 5. Multi-Turn Image Editing

To edit an existing image, pass the `--cid` (Conversation ID) and `--mid` (Message ID) returned by a previous generation:

```bash
python cli.py "make the car bright red with black racing stripes" --cid 1654f463-ccdf-4aec-9473-dc05049608d7 --mid 6fc6b846-9ea5-4ecd-8016-88a01690bcfb
```

---

### 6. Interactive Terminal Session

Start an interactive multi-turn session by running `cli.py` without arguments:

```bash
python cli.py
```

Features in Interactive Mode:
- **First Prompt**: Creates the base image and preserves session state.
- **Follow-up Prompts**: Automatically edits the active image while preserving character and composition.
- **Reference Image Shortcut**: Prefix your prompt with `@path/to/image.png` (e.g., `@outputs/photo.png make this an anime drawing`).
- **Reset Session**: Type `new` or `reset` to start a fresh conversation.
- **Exit**: Type `exit`, `q`, or press `Ctrl+C`.

---

### 7. Session Verification Check

Test if your authentication cookie is still valid without consuming generation quotas:

```bash
python cli.py --check
```

Example Output:
```text
┌───────────────────────────────────────────────────────┐
│ Microsoft AI Playground CLI (Secure & Rate-Protected) │
└───────────────────────────────────────────────────────┘
Simulating browser visit & verifying session...
Session active: your_account@example.com
Credentials are valid and ready.
```

---

## 🐍 Python SDK Reference

The `MaiImageClient` class in `mai_client.py` can be imported directly into your own Python applications.

### Basic Text-to-Image

```python
from mai_client import MaiImageClient

# Initializes client using MAI_COOKIE from .env
client = MaiImageClient(model_id="mai-image-2-6")

# Generate image (with optional aspect ratio: "16:9", "9:16", "4:3", "3:4", "1:1")
result = client.generate(
    prompt="a tranquil Japanese zen garden at dawn, 4k digital art",
    aspect_ratio="16:9"
)

print("Saved file:", result["saved_path"])
print("Conversation ID:", result["conversation_id"])
print("Message ID:", result["message_id"])
```

---

### Image-to-Image (Reference Image)

```python
from mai_client import MaiImageClient

client = MaiImageClient()

result = client.generate(
    prompt="recreate this scene as an oil painting with heavy impasto strokes",
    reference_image="inputs/landscape.jpg",
    output_file="outputs/oil_landscape.png"
)

print("Saved to:", result["saved_path"])
```

---

### Multi-Turn Image Editing

```python
from mai_client import MaiImageClient

client = MaiImageClient()

# 1. Generate base image
base = client.generate(
    prompt="a white sports coupe parked inside a minimalist modern studio",
    output_file="outputs/car_white.png"
)

# 2. Modify specific attributes in the existing conversation
edited = client.generate(
    prompt="change the car paint to metallic crimson red with dual racing stripes",
    conversation_id=base["conversation_id"],
    source_message_id=base["message_id"],
    output_file="outputs/car_red.png"
)

print("Successfully edited image:", edited["saved_path"])
```

---

### Custom Configuration & Callbacks

```python
from mai_client import MaiImageClient

def on_status_update(message: str):
    print(f"[STATUS] {message}")

client = MaiImageClient(
    cookie="MSCC=...; AppServiceAuthSession=...",
    model_id="mai-image-2-6",
    min_request_interval=3.0,  # Minimum delay between requests (seconds)
    max_retries=4              # Maximum retry attempts on transient network drops
)

# Manual session warmup
session_info = client.warmup()
print("Connected as:", session_info["user_id"])

# Generation with live callback
result = client.generate(
    prompt="cyberpunk cityscape with neon holograms and flying vehicles",
    on_status=on_status_update
)
```

---

## 🛡️ Anti-Bot & Security Safeguards

To prevent automated bot detection, IP rate limiting, and account flags, `mai-image` incorporates comprehensive defensive engineering:

| Mechanism | Description | Benefit |
|-----------|-------------|---------|
| **Browser Warmup** | Issues full Chrome HTML navigation GET requests before API operations. | Establishes a natural browser entry footprint in server logs. |
| **Human Rate Jitter** | Enforces randomized delays (2.5s – 4.5s) between consecutive calls. | Smooths out burst traffic that triggers heuristic bot filters. |
| **Typing Simulation** | Introduces 0.8s – 1.8s delays prior to prompt submission. | Simulates natural human composition and input timing. |
| **Circuit Breakers** | Halts execution immediately upon receiving `HTTP 401` or `403`. | Prevents spamming an invalid session and avoids account blacklisting. |
| **Exponential Backoff** | Catches `HTTP 429` (Rate Limited) and backs off exponentially (5s, 15s...). | Recovers smoothly from temporary server throttling. |
| **Credential Redaction** | Strips cookies and authentication headers from logs and exceptions. | Eliminates accidental token leakage in stack traces and terminals. |

---

## ❓ Troubleshooting & FAQ

### `AuthenticationError: Session validation failed (HTTP 401/403)`
- **Cause**: Your `AppServiceAuthSession` cookie has expired or you signed out from the browser.
- **Solution**: Open `playground.microsoft.ai` in your browser, copy your new `Cookie` header from DevTools, and update `MAI_COOKIE` in your `.env` file. Run `python cli.py --check` to verify.

### `RateLimitError: Rate limit exceeded (HTTP 429)`
- **Cause**: You have submitted too many requests in a short period of time.
- **Solution**: The client will automatically retry with exponential backoff. If it still fails, wait a few minutes before submitting new requests.

### `Image URL was not returned in the stream response`
- **Cause**: The prompt may have triggered Microsoft AI's safety/content moderation filter.
- **Solution**: Adjust the wording of your prompt to comply with Microsoft's Responsible AI policies.

### Where are my images saved?
- By default, all generated images are saved to the `./outputs/` folder with sanitized filenames and random hashes. You can specify a custom output path using the `-o` / `--output` flag.

---

## ⚖️ Disclaimer

This project is an **unofficial, educational reverse-engineering implementation** and is not affiliated with, sponsored by, or endorsed by Microsoft Corporation. 

- This tool is intended solely for personal research, educational purposes, and prototyping.
- Users are responsible for adhering to [Microsoft's Terms of Service](https://www.microsoft.com/en-us/legal/terms-of-use) and Responsible AI policies.
- Do not use this tool for high-volume automated scraping or abusive activities.

---

<div align="center">
Developed with care by <a href="https://github.com/YiTechX">YiTechX</a>
</div>
