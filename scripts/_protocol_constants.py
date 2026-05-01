"""Auto-generated from agent-readiness-insights-protocol. DO NOT EDIT.

Regenerate via ``python scripts/regen_protocol_constants.py`` whenever
you bump the protocol pin (transitively, via the scanner). CI asserts
``git diff --exit-code`` on this file so a protocol enum addition
without a coordinated bump here is a hard error.
"""
from __future__ import annotations

PILLARS: tuple[str, ...] = ('cognitive_load', 'feedback', 'flow', 'safety')
SEVERITIES: tuple[str, ...] = ('info', 'warn', 'error')
OSS_MATCH_TYPES: tuple[str, ...] = ('file_size', 'path_glob', 'manifest_field', 'regex_in_files', 'command_in_makefile', 'composite')

__all__ = ["PILLARS", "SEVERITIES", "OSS_MATCH_TYPES"]
