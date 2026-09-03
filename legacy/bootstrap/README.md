# Legacy AI Development Bootstrap

This directory contains the earlier optional installer for Cursor, Chatbox,
OpenClaw, and local proxy configuration. It is retained for compatibility
but is not required by `llm-integrity-checker`.

The legacy installer reads `.env` only for the current process and no longer
writes API credentials to machine-wide environment variables. Review the
script before using it on a new machine.
