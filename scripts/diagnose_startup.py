"""Read-only diagnostics for Render startup. Never print credentials."""
import importlib
import os
import time


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
    print('Diagnostic complete; no network requests or database writes performed by this script.', flush=True)


if __name__ == '__main__':
    main()
