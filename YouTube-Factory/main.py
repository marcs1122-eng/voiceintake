#!/usr/bin/env python3
"""YouTube AI Factory - Main Entry Point.

Usage:
    # Produce a video for a specific channel:
    python main.py produce --channel dark_verdict --topic "The Zodiac Killer Case"

    # Produce for all channels:
    python main.py produce-all --topics '{"dark_verdict": "The Zodiac Killer", "trailer_trash": "Sharks vs Robots"}'

    # Get topic suggestions:
    python main.py suggest --channel trailer_trash --count 10

    # List configured channels:
    python main.py channels

    # Dry run (validate config without producing):
    python main.py validate
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import load_channels, load_api_keys, get_channel_ids
from core.events import EventBus
from agents.orchestrator import MasterOrchestrator
from utils.logger import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="YouTube AI Factory - Automated Video Production Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--log-file", default=None,
        help="Write logs to file in addition to stdout",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ── produce: single channel ──
    produce_parser = subparsers.add_parser("produce", help="Produce a video for one channel")
    produce_parser.add_argument("--channel", "-c", required=True, help="Channel ID from config")
    produce_parser.add_argument("--topic", "-t", required=True, help="Video topic/subject")
    produce_parser.add_argument(
        "--auto-publish", action="store_true",
        help="Publish immediately instead of scheduling",
    )

    # ── produce-all: all channels ──
    all_parser = subparsers.add_parser("produce-all", help="Produce videos for multiple channels")
    all_parser.add_argument(
        "--topics", required=True,
        help='JSON mapping of channel_id to topic, e.g. \'{"dark_verdict": "Topic"}\'',
    )
    all_parser.add_argument(
        "--max-concurrent", type=int, default=2,
        help="Max channels to process simultaneously (default: 2)",
    )

    # ── suggest: get topic ideas ──
    suggest_parser = subparsers.add_parser("suggest", help="Get topic suggestions for a channel")
    suggest_parser.add_argument("--channel", "-c", required=True, help="Channel ID")
    suggest_parser.add_argument("--count", "-n", type=int, default=5, help="Number of suggestions")

    # ── channels: list channels ──
    subparsers.add_parser("channels", help="List all configured channels")

    # ── validate: check config ──
    subparsers.add_parser("validate", help="Validate configuration files")

    return parser.parse_args()


async def cmd_produce(args: argparse.Namespace) -> None:
    """Produce a single video."""
    channels = load_channels()
    api_keys = load_api_keys()
    event_bus = EventBus()

    orchestrator = MasterOrchestrator(
        config={"channels": channels, "defaults": channels.get(args.channel, {})},
        event_bus=event_bus,
    )

    result = await orchestrator.produce(
        channel_id=args.channel,
        topic=args.topic,
        api_keys=api_keys,
        auto_publish=args.auto_publish,
    )

    print("\n" + "=" * 60)
    print("PRODUCTION RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))


async def cmd_produce_all(args: argparse.Namespace) -> None:
    """Produce videos for all specified channels."""
    channels = load_channels()
    api_keys = load_api_keys()
    event_bus = EventBus()
    topics = json.loads(args.topics)

    orchestrator = MasterOrchestrator(
        config={"channels": channels},
        event_bus=event_bus,
    )

    results = await orchestrator.produce_all(
        topics=topics,
        api_keys=api_keys,
        max_concurrent=args.max_concurrent,
    )

    print("\n" + "=" * 60)
    print("ALL PRODUCTION RESULTS")
    print("=" * 60)
    for result in results:
        print(json.dumps(result, indent=2, default=str))
        print("-" * 40)


async def cmd_suggest(args: argparse.Namespace) -> None:
    """Get topic suggestions."""
    channels = load_channels()
    api_keys = load_api_keys()
    event_bus = EventBus()

    orchestrator = MasterOrchestrator(
        config={"channels": channels},
        event_bus=event_bus,
    )

    suggestions = await orchestrator.suggest_topics(
        channel_id=args.channel,
        count=args.count,
        api_keys=api_keys,
    )

    print(f"\nTopic suggestions for '{args.channel}':")
    print("-" * 40)
    for i, s in enumerate(suggestions, 1):
        print(f"{i}. {s.get('topic', 'N/A')}")
        print(f"   Angle: {s.get('angle', 'N/A')}")
        print(f"   Demand: {s.get('estimated_demand', 'N/A')}")
        print()


def cmd_channels() -> None:
    """List configured channels."""
    channel_ids = get_channel_ids()
    channels = load_channels()

    print("\nConfigured Channels:")
    print("=" * 60)
    for cid in channel_ids:
        cfg = channels[cid]
        print(f"\n  [{cid}]")
        print(f"  Name:     {cfg.get('name', 'N/A')}")
        print(f"  Tagline:  {cfg.get('tagline', 'N/A')}")
        print(f"  Niche:    {cfg.get('niche', 'N/A')}")
        print(f"  Tone:     {cfg.get('tone', 'N/A')}")

        schedule = cfg.get("schedule", {})
        lf = schedule.get("long_form", {})
        print(f"  Schedule: {', '.join(lf.get('days', []))} at {lf.get('time', 'N/A')}")

        dist = cfg.get("distribution", {})
        platforms = [p for p in ["youtube", "tiktok", "instagram_reels"] if dist.get(p)]
        print(f"  Platforms: {', '.join(platforms)}")

    print(f"\nTotal: {len(channel_ids)} channel(s)\n")


def cmd_validate() -> None:
    """Validate configuration."""
    errors = []

    try:
        channels = load_channels()
        print(f"[OK] channels.yaml - {len(channels)} channel(s) loaded")
    except Exception as e:
        errors.append(f"channels.yaml: {e}")
        print(f"[FAIL] channels.yaml: {e}")

    try:
        api_keys = load_api_keys()
        configured = [k for k, v in api_keys.items() if isinstance(v, dict) and any(
            val and not val.startswith("XXXX") for val in v.values()
        )]
        print(f"[OK] api_keys.yaml - {len(configured)} provider(s) configured")
    except FileNotFoundError:
        print("[WARN] api_keys.yaml not found - copy from api_keys.yaml.example")
    except Exception as e:
        errors.append(f"api_keys.yaml: {e}")
        print(f"[FAIL] api_keys.yaml: {e}")

    # Validate each channel config
    if not errors:
        for cid, cfg in channels.items():
            required_keys = ["name", "niche", "tone", "content", "voice", "visuals", "seo", "schedule"]
            missing = [k for k in required_keys if k not in cfg]
            if missing:
                print(f"[WARN] Channel '{cid}' missing keys: {', '.join(missing)}")
            else:
                print(f"[OK] Channel '{cid}' configuration complete")

    if errors:
        print(f"\n{len(errors)} error(s) found. Fix them before running production.")
        sys.exit(1)
    else:
        print("\nAll validations passed!")


def main() -> None:
    args = parse_args()

    if not args.command:
        parse_args.__wrapped__ = None  # type: ignore
        print("No command specified. Use --help for usage.")
        sys.exit(1)

    setup_logging(level=args.log_level, log_file=args.log_file)

    if args.command == "channels":
        cmd_channels()
    elif args.command == "validate":
        cmd_validate()
    elif args.command == "produce":
        asyncio.run(cmd_produce(args))
    elif args.command == "produce-all":
        asyncio.run(cmd_produce_all(args))
    elif args.command == "suggest":
        asyncio.run(cmd_suggest(args))
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
