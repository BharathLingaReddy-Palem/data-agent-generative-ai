"""Run the offline regression suite with reliable nonzero failure exit codes."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend', action='store_true', help='Also run Node frontend regression tests.')
    args, pytest_args = parser.parse_known_args(argv)
    # pytest.ini selects tests/; its conftest isolates SQLite and blocks providers.
    command = [sys.executable, '-m', 'pytest', *(pytest_args or ['tests', '-q'])]
    status = subprocess.run(command, cwd=ROOT).returncode
    if status or not args.frontend:
        return status
    node = shutil.which('node')
    if not node:
        print('Node.js is required for --frontend.', file=sys.stderr)
        return 1
    files = sorted((ROOT/'frontend_web'/'tests').glob('*.test.js'))
    if not files:
        print('No frontend tests found.', file=sys.stderr)
        return 1
    return subprocess.run([node, '--test', *map(str, files)], cwd=ROOT/'frontend_web').returncode


if __name__ == '__main__':
    raise SystemExit(main())
