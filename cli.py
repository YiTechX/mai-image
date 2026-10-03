import sys
import os
import argparse
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from mai_client import MaiImageClient, AuthenticationError, RateLimitError

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=True)

def open_image(path: str) -> None:
    """Opens the generated image using the default system viewer."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception as err:
        console.print(f"[yellow]Warning: Could not open image automatically: {err}[/yellow]")

def generate_with_progress(
    client: MaiImageClient,
    prompt_text: str,
    output_path: str = None,
    conversation_id: str = None,
    source_message_id: str = None,
    reference_image: str = None,
    auto_open: bool = False,
):
    result = None
    if reference_image:
        action_label = f"Generating with reference ({os.path.basename(reference_image)})"
    elif source_message_id:
        action_label = "Editing active image"
    else:
        action_label = "Generating image"

    try:
        with console.status(f"[cyan]{action_label}...[/cyan]", spinner="dots") as status:
            def update_status(message: str):
                status.update(f"[cyan]{message}[/cyan]")

            result = client.generate(
                prompt=prompt_text,
                output_file=output_path,
                conversation_id=conversation_id,
                source_message_id=source_message_id,
                reference_image=reference_image,
                on_status=update_status,
            )
    except AuthenticationError as auth_err:
        console.print(f"\n[bold red]Authentication Error:[/bold red] {auth_err}")
        return None
    except RateLimitError as rate_err:
        console.print(f"\n[bold yellow]Rate Limit Protection:[/bold yellow] {rate_err}")
        return None
    except Exception as err:
        console.print(f"\n[bold red]Error:[/bold red] {err}")
        return None

    if result:
        console.print(f"[bold green]Success.[/bold green]")
        console.print(f"File saved: [bold white]{result['saved_path']}[/bold white]")
        console.print(f"[dim]Conversation: {result['conversation_id']} | Message: {result['message_id']}[/dim]\n")
        if auto_open:
            open_image(result['saved_path'])

    return result

def main():
    parser = argparse.ArgumentParser(
        description="CLI tool for Microsoft AI Playground (mai-image-2-6) generation, editing, and reference image."
    )
    parser.add_argument("prompt", nargs="?", default=None, help="Prompt text.")
    parser.add_argument("-m", "--model", default="mai-image-2-6", help="Model ID (default: mai-image-2-6, or mai-image-2-6-flash).")
    parser.add_argument("-i", "--image", default=None, help="Path to reference image (Image-to-Image).")
    parser.add_argument("-o", "--output", default=None, help="Output file path.")
    parser.add_argument("--cid", default=None, help="Conversation ID (for edit/continuation).")
    parser.add_argument("--mid", default=None, help="Source message ID (for edit/continuation).")
    parser.add_argument("--open", action="store_true", help="Automatically open image after generation.")
    parser.add_argument("--check", action="store_true", help="Verify session credentials without generating.")
    args = parser.parse_args()

    console.print(Panel(f"[bold cyan]Microsoft AI Playground CLI ({args.model})[/bold cyan]", border_style="blue", expand=False))

    try:
        client = MaiImageClient(model_id=args.model)
    except Exception as err:
        console.print(f"[bold red]Initialization Error:[/bold red] {err}")
        sys.exit(1)

    # Browser session warmup and verification
    with console.status("[dim]Simulating browser visit & verifying session...[/dim]", spinner="dots") as status:
        try:
            session_data = client.warmup()
            console.print(f"[green]Session active:[/green] [dim]{session_data.get('user_id')}[/dim]")
        except AuthenticationError as e:
            console.print(f"[bold red]Warning:[/bold red] {e}")
            if args.check:
                sys.exit(1)

    if args.check:
        console.print("[bold green]Credentials are valid and ready.[/bold green]")
        return

    if args.prompt:
        generate_with_progress(
            client=client,
            prompt_text=args.prompt,
            output_path=args.output,
            conversation_id=args.cid,
            source_message_id=args.mid,
            reference_image=args.image,
            auto_open=args.open,
        )
        return

    # Interactive session
    console.print("[dim]Commands: 'new' (reset), 'exit' / 'q' (quit).[/dim]")
    console.print("[dim]Tip: Prefix prompt with '@image_path prompt' to use a reference image.[/dim]\n")

    current_conv_id = None
    current_msg_id = None

    while True:
        try:
            status_tag = f"[bold green][Active Edit: {current_conv_id[:8]}...][/bold green] " if current_conv_id else ""
            user_input = Prompt.ask(f"{status_tag}[bold]Prompt[/bold]")
            if not user_input or user_input.strip().lower() in ("q", "quit", "exit"):
                console.print("[dim]Exiting.[/dim]")
                break

            clean_input = user_input.strip()
            if clean_input.lower() in ("new", "/new", "reset"):
                current_conv_id = None
                current_msg_id = None
                console.print("[cyan]Conversation reset. Next prompt will start a new image.[/cyan]\n")
                continue

            # Check if input starts with @image_path
            ref_img = None
            if clean_input.startswith("@"):
                parts = clean_input[1:].split(" ", 1)
                ref_img = parts[0]
                clean_input = parts[1] if len(parts) > 1 else "enhance and recreate this image"

            res = generate_with_progress(
                client=client,
                prompt_text=clean_input,
                conversation_id=current_conv_id,
                source_message_id=current_msg_id,
                reference_image=ref_img,
                auto_open=True,
            )
            if res:
                current_conv_id = res["conversation_id"]
                current_msg_id = res["message_id"]

            console.print("─" * 40)
        except KeyboardInterrupt:
            console.print("\n[dim]Process interrupted. Exiting.[/dim]")
            break

if __name__ == "__main__":
    main()
