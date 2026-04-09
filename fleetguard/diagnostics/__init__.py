"""Diagnostic reports for failed scenarios.

A report is assembled from facts in the database (context.py) into a fixed
markdown layout (template.py). Optionally an LLM writes the narrative parts
(summary, likely cause, next steps) from the same facts (llm.py), and a guard
checks that narrative against the facts before it is used (guard.py). Evidence
tables, the event timeline and the repro command always come from data.
"""
