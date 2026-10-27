from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from typing import Any, Sequence

from .context import ContextBudget, ContextBuilder
from .errors import PersonaMemoryError
from .models import Turn
from .persona import load_persona
from .retrieval import MemoryRetriever
from .store import SQLiteMemoryStore


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def parse_state(value: str) -> dict[str, Any]:
    try:
        state = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid state JSON: {exc.msg}") from exc
    if not isinstance(state, dict):
        raise ValueError("state must be a JSON object")
    return state


def parse_turn(value: str) -> Turn:
    role, separator, content = value.partition(":")
    if not separator or role not in {"user", "assistant"} or not content.strip():
        raise ValueError("turn must use the format user:内容 or assistant:内容")
    return Turn(role, content.strip()).validated()


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="persona-memory",
        description="Manage persona memories and assemble bounded model context.",
    )
    parser.add_argument("--db", default="output/memories.db", help="SQLite database path")
    parser.add_argument(
        "--persona", default="config/persona.json", help="persona JSON file path"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="add an explicit long-term memory")
    add.add_argument("content")
    add.add_argument("--subject", default="global")
    add.add_argument(
        "--category",
        default="other",
        choices=["preference", "profile", "event", "relationship", "project", "other"],
    )
    add.add_argument("--importance", type=float, default=0.5)
    add.add_argument("--confidence", type=float, default=1.0)
    add.add_argument("--source", default="cli")

    list_parser = subparsers.add_parser("list", help="list newest memories")
    list_parser.add_argument("--subject")
    list_parser.add_argument("--limit", type=int, default=100)

    update = subparsers.add_parser("update", help="correct an existing memory")
    update.add_argument("id", type=int)
    update.add_argument("--content")
    update.add_argument("--subject")
    update.add_argument(
        "--category",
        choices=["preference", "profile", "event", "relationship", "project", "other"],
    )
    update.add_argument("--importance", type=float)
    update.add_argument("--confidence", type=float)
    update.add_argument("--source")

    delete = subparsers.add_parser("delete", help="permanently delete a memory")
    delete.add_argument("id", type=int)

    search = subparsers.add_parser("search", help="rank memories related to a query")
    search.add_argument("query")
    search.add_argument("--subject")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--min-score", type=float, default=0.12)

    build = subparsers.add_parser("build", help="build a bounded prompt")
    build.add_argument("message")
    build.add_argument("--subject")
    build.add_argument("--summary", default="")
    build.add_argument("--state", default="{}")
    build.add_argument("--turn", action="append", default=[])
    build.add_argument("--max-chars", type=int, default=6000)
    build.add_argument("--max-memories", type=int, default=5)
    build.add_argument("--max-turns", type=int, default=8)

    subparsers.add_parser("validate", help="validate the persona JSON file")
    subparsers.add_parser("demo", help="run an isolated in-memory example")
    return parser


def run(args: argparse.Namespace) -> int:
    if args.command == "validate":
        persona = load_persona(args.persona)
        print_json({"valid": True, "name": persona.name})
        return 0

    if args.command == "demo":
        persona = load_persona(args.persona)
        with SQLiteMemoryStore(":memory:") as store:
            store.add(
                "喜欢恐怖游戏，但不喜欢频繁跳吓",
                subject="viewer:demo",
                category="preference",
                importance=0.8,
                source="demo",
            )
            store.add(
                "上一场解谜游戏连续两次错过同一个机关",
                subject="global",
                category="event",
                importance=0.7,
                source="demo",
            )
            results = MemoryRetriever(store).search(
                "今晚想玩恐怖游戏，有什么建议？",
                subject="viewer:demo",
            )
            context = ContextBuilder().build(
                persona=persona,
                current_message="今晚想玩恐怖游戏，有什么建议？",
                memories=results,
                turns=[Turn("user", "上次解谜又卡关了"), Turn("assistant", "这次先观察机关联动")],
                summary="本场直播正在讨论游戏安排。",
                state={"scene": "game_selection"},
            )
            print_json(context.metadata() | {"prompt": context.prompt})
        return 0

    with SQLiteMemoryStore(args.db) as store:
        if args.command == "add":
            memory = store.add(
                content=args.content,
                subject=args.subject,
                category=args.category,
                importance=args.importance,
                confidence=args.confidence,
                source=args.source,
            )
            print_json(memory.to_dict())
        elif args.command == "list":
            print_json([item.to_dict() for item in store.list(args.subject, args.limit)])
        elif args.command == "update":
            memory = store.update(
                memory_id=args.id,
                content=args.content,
                subject=args.subject,
                category=args.category,
                importance=args.importance,
                confidence=args.confidence,
                source=args.source,
            )
            print_json(memory.to_dict())
        elif args.command == "delete":
            store.delete(args.id)
            print_json({"deleted": args.id})
        elif args.command == "search":
            results = MemoryRetriever(store).search(
                query=args.query,
                subject=args.subject,
                limit=args.limit,
                min_score=args.min_score,
            )
            print_json(
                [
                    item.memory.to_dict()
                    | {"score": round(item.score, 4), "relevance": round(item.relevance, 4)}
                    for item in results
                ]
            )
        elif args.command == "build":
            persona = load_persona(args.persona)
            results = (
                MemoryRetriever(store).search(
                    query=args.message,
                    subject=args.subject,
                    limit=args.max_memories,
                )
                if args.max_memories > 0
                else []
            )
            context = ContextBuilder(
                ContextBudget(
                    max_chars=args.max_chars,
                    max_memories=args.max_memories,
                    max_turns=args.max_turns,
                )
            ).build(
                persona=persona,
                current_message=args.message,
                memories=results,
                turns=[parse_turn(value) for value in args.turn],
                summary=args.summary,
                state=parse_state(args.state),
            )
            print_json(context.metadata() | {"prompt": context.prompt})
        else:
            raise ValueError(f"unsupported command: {args.command}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (PersonaMemoryError, ValueError, OSError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()
