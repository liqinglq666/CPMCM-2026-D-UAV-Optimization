# 本程序及代码是在人工智能工具辅助下完成的。
# AI assistance declaration (this entry point and its imported src modules)
# Tool: ChatGPT/Codex.
# Model: GPT-6 Astra (gpt-6-astra).
# Developer: OpenAI.
# Public release date: 2026-09-03.
# Release source: https://developers.openai.com/api/docs/changelog
# Use: code drafting/review, data preparation, scientific plotting, paper editing,
# and consistency checks. Model identity was confirmed by the participants.
# This submission-stage change adds disclosure only; algorithm code is unchanged.
# Original method attribution and seed provenance remain in src and config.

"""Run Q1; see README for official data setup."""

from src.cli import run_question

if __name__ == "__main__":
    run_question("q1")
