# Microsoft AI Playground Image Generator & Editor (mai-image-2-6-flash)

A hardened, lightweight CLI tool and Python client for generating and editing images via Microsoft AI Playground (`mai-image-2-6-flash`).

---

## Security & Anti-Detection Safeguards

The client includes built-in safeguards to prevent account flagging and rate violations:

1. **Realistic Browser Navigation (Warmup)**: Visits `https://playground.microsoft.ai/chat?model=...` via authentic Chrome document `GET` navigation before API calls, complete with standard browser headers (`sec-fetch-dest: document`, `sec-fetch-mode: navigate`, etc.) and natural page-reading pauses.
2. **Pre-flight Session Validation**: Verifies authentication status before submitting generation workloads to prevent dirty states and repeated failures.
3. **Human-like Rate Pacing (Jitter)**: Enforces randomized delays between consecutive requests (2.5s – 4.5s) and simulated human typing pauses to mitigate bot heuristics and avoid burst traffic.
4. **Circuit Breakers**: Immediately halts requests on authorization failures (`HTTP 401/403`) to protect the account from repetitive invalid attempts.
5. **Exponential Backoff**: Handles rate limits (`HTTP 429`) and server drops with randomized exponential backoff retries.
6. **Credential Protection**: Redacts sensitive session cookies in stack traces and logs, and excludes local credentials via `.gitignore`.

---

## Installation

Ensure Python 3.10+ is installed, then install dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

Set your session cookie in `.env` in the project root:

```env
MAI_COOKIE="MSCC=cid=...; AppServiceAuthSession=..."
```

---

## Usage

### 1. Verify Session Health
Check if your credentials are valid without triggering image generation:

```bash
python cli.py --check
```

### 2. Generate a New Image (Default: mai-image-2-6)
```bash
python cli.py "a futuristic golden mechanical bird with crystal feathers" -o outputs/bird.png
```

You can also specify the faster flash model using `-m` or `--model`:
```bash
python cli.py "a cute cat" -m mai-image-2-6-flash
```

### 3. Generate with a Reference Image (Image-to-Image)
Pass `-i` or `--image` to provide a local reference image:

```bash
python cli.py "make this cat into a watercolor painting, soft pastel aesthetic" -i outputs/output_cat.png -o outputs/watercolor_cat.png
```

In interactive mode, you can also use `@path/to/image.png <prompt>`.

### 4. Edit an Existing Image
Pass the `--cid` (Conversation ID) and `--mid` (Message ID) from a previous generation:

```bash
python cli.py "make the house wooden with snow on the roof" --cid <CONVERSATION_ID> --mid <MESSAGE_ID>
```

### 5. Interactive Multi-Turn Mode
Run the tool interactively:

```bash
python cli.py
```

* **First prompt**: Generates the base image and preserves the conversation session.
* **Subsequent prompts**: Iteratively edit and refine the current image within the active session.
* **Type `new`**: Resets the session to generate a completely new image.
* **Type `exit` or `q`**: Quits the application.

---

## Python API Usage

```python
from mai_client import MaiImageClient

client = MaiImageClient(min_request_interval=3.0)

# 1. Validate session
status = client.validate_session()
print("Connected as:", status["user_id"])

# 2. Generate base image
res1 = client.generate("a white sports car in a studio", output_file="outputs/white_car.png")

# 3. Edit image
res2 = client.generate(
    prompt="make this car bright red with black racing stripes",
    output_file="outputs/red_car.png",
    conversation_id=res1["conversation_id"],
    source_message_id=res1["message_id"],
)
```
