"""MBQL-001 — shared Ask / query / command compile.

STT-ready: later I9 must call ``compile_ask``. Do not build speech here.
"""
from __future__ import annotations

from memorybox.mbql.compile import compile_ask
from memorybox.mbql.verbs import COMMANDS, VERB_IDS, match_command

__all__ = ["COMMANDS", "VERB_IDS", "compile_ask", "match_command"]
