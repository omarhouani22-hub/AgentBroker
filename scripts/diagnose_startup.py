"""Read-only diagnostics for Render startup. Never print credentials."""
import importlib
import os
import time
import sys
from pathlib import Path

# Running `python scripts/diagnose_startup.py` puts scripts/, not the repo root, on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    started = time.monotonic()
    print('AgentBroker startup diagnostic: begin', flush=True)
    for name in ('flask', 'memory', 'hr_toolkit', 'app'):
        step = time.monotonic()
        try:
            importlib.import_module(name)
        except Exception as exc:
            print(f'{name}: FAILED ({type(exc).__name__}) after {time.monotonic()-step:.2f}s', flush=True)
            raise
        print(f'{name}: OK in {time.monotonic()-step:.2f}s', flush=True)
    print(f'total import time: {time.monotonic()-started:.2f}s', flush=True)
    print(f'PORT configured: {bool(os.getenv("PORT"))}', flush=True)
    print('Diagnostic complete; imports may execute module initialization; no explicit network calls or writes are made by the diagnostic.', flush=True)


if __name__ == '__main__':
    main()
