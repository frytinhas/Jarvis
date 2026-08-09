"""Best-effort detached writer for Jarvis profile notes."""
from __future__ import annotations

import argparse
from pathlib import Path

from jarvis.config import load_config
from jarvis.llm.client import LlamaClient
from jarvis.memory.notes import ProfileNotesStore
from jarvis.memory.store import ConversationLogStore


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--notes", type=Path, required=True)
    options = parser.parse_args(arguments)
    try:
        config = load_config()
        settings = config.settings
        store = ConversationLogStore(options.database.parent)
        if store.database_path != options.database.expanduser().resolve(strict=False):
            return
        transcript = store.transcript_for_summary(options.conversation)
        if not transcript:
            return
        with LlamaClient(
            config.advanced.llm_base_url, config.advanced.llm_model, config.advanced.llm_api_key,
            timeout=settings.llm_request_timeout_seconds, thinking_budget_tokens=0,
        ) as llm:
            ProfileNotesStore(options.notes).merge_session(
                llm, transcript, max_size_mb=settings.notes_max_size_mb,
                context_size=settings.context_size,
            )
    except Exception:
        return


if __name__ == "__main__":
    main()
