"""
Asks the user a question in the terminal, with a timeout. If they don't
respond in time, returns None so the caller can skip gracefully instead of
hanging the whole run waiting for someone who stepped away.
"""
import threading


def ask_user(prompt: str, timeout_seconds: int = 120) -> str | None:
    print("\n" + "=" * 60)
    print("NEEDS YOUR INPUT — the script paused, waiting for you to type here.")
    print(f"(No response within {timeout_seconds}s skips this application.)")
    print("=" * 60)

    answer_holder = {}

    def _read():
        try:
            answer_holder["value"] = input(f"{prompt}\n> ").strip()
        except Exception:
            answer_holder["value"] = None

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        print("\n(No response in time — skipping this application.)")
        return None

    value = answer_holder.get("value")
    return value if value else None
