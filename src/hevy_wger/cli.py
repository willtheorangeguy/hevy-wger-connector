import argparse
from datetime import datetime, timezone
import json
import random
import signal
import sys
import threading
from .config import Config
from .engine import Engine
from .graph import stamp
from .state import State


def emit(value, as_json=True):
    # JSON is also the human-readable default: useful from docker compose logs.
    print(json.dumps(value, indent=None if not as_json else 2, ensure_ascii=True), flush=True)


def parser():
    root = argparse.ArgumentParser(description="Import Hevy strength workouts and routines into wger")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ["check", "preview", "sync", "watch", "status", "reconcile"]:
        sub = commands.add_parser(name)
        sub.add_argument("--json", action="store_true")
        if name == "sync":
            sub.add_argument("--full", action="store_true", help="Reconcile all source workouts and managed objects")
        if name == "status":
            sub.add_argument("--health", action="store_true")
        if name == "reconcile":
            sub.add_argument("--retry-uncommitted", metavar="KEY",
                help="Authorize retry only after verifying the original non-UUID create cannot still be executing")
    mapping = commands.add_parser("mappings").add_subparsers(dest="mapping_command", required=True)
    for name in ["list", "suggest", "set"]:
        sub = mapping.add_parser(name)
        sub.add_argument("--json", action="store_true")
        if name == "set":
            sub.add_argument("hevy_id")
            sub.add_argument("wger_id", type=int)
    return root


def main():
    args = parser().parse_args()
    state, engine = None, None
    try:
        config = Config.load()
        state = State(config.data_dir)
        if args.command == "status":
            report = state.report()
            if args.health:
                recent = report["last_attempt"] and (datetime.now(timezone.utc)-stamp(report["last_attempt"])).total_seconds() < config.interval*2+120
                return 0 if recent and not report["last_error"] else 1
            emit(report, args.json)
            return 0
        engine = Engine(config, state)
        if args.command == "sync":
            report = engine.sync(args.full)
            emit(report, args.json)
            return 2 if any(report["counts"].get(k) for k in ["blocked", "failed", "conflict", "uncertain"]) else 0
        if args.command == "watch":
            stop = threading.Event()
            for sig in [signal.SIGINT, signal.SIGTERM]:
                signal.signal(sig, lambda *_: stop.set())
            while not stop.is_set():
                try:
                    emit({"event": "sync", **engine.sync()}, False)
                except Exception as error:
                    emit({"event": "sync_failed", "error": str(error)}, False)
                stop.wait(config.interval + random.uniform(1, 30))
            return 0
        with state.lock():
            if args.command == "check":
                emit(engine.check(), args.json)
            elif args.command == "preview":
                emit({"plan": engine.preview(), "destination_writes": 0}, args.json)
            elif args.command == "reconcile":
                engine.check()
                emit(engine.writer.reconcile(args.retry_uncommitted), args.json)
            elif args.command == "mappings":
                if args.mapping_command == "list":
                    emit(engine.mappings(), args.json)
                elif args.mapping_command == "suggest":
                    engine.check()
                    engine.discover()
                    emit(engine.suggest(), args.json)
                else:
                    engine.check()
                    if not state.get("exercise_templates"):
                        engine.discover()
                    if args.hevy_id not in state.get("exercise_templates", {}):
                        raise ValueError("Unknown Hevy exercise ID; run preview to refresh the exercise catalog")
                    if engine.wger.detail("exercise", args.wger_id) is None:
                        raise ValueError("Unknown wger exercise ID")
                    state.map(args.hevy_id, args.wger_id)
                    emit({"hevy_id": args.hevy_id, "wger_id": args.wger_id, "approved": True}, args.json)
        return 0
    except Exception as error:
        emit({"error": str(error)}, False)
        return 1
    finally:
        if engine:
            engine.close()
        if state:
            state.close()


if __name__ == "__main__":
    sys.exit(main())
