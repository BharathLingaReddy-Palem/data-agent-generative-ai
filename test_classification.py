"""Compatibility entry point for the maintained offline regression suite.

Replaces the historical print-based demo. Provider calls are blocked, temporary
storage is used, and any failing assertion returns a nonzero process exit code.
Use --frontend to include the frontend tests, or pass pytest selection arguments.
"""
from run_regression import main

if __name__ == '__main__':
    raise SystemExit(main())
