"""Stand-ins for Claude and the outside world, so tests run offline."""

from collections import defaultdict


class FakeAI:
    """Returns scripted answers per step name, and records every call."""

    def __init__(self, answers=None):
        self.answers = defaultdict(list)
        self.calls = []
        for task, value in (answers or {}).items():
            self.queue(task, value)

    def queue(self, task, *values):
        self.answers[task].extend(values)

    def _next(self, task, system, content):
        self.calls.append({"task": task, "system": system, "content": content})
        if not self.answers[task]:
            raise AssertionError(f"no scripted answer for {task}")
        value = self.answers[task].pop(0)
        if isinstance(value, Exception):
            raise value
        return value(content) if callable(value) else value

    def ask_json(self, task, system, content, schema, **_):
        return self._next(task, system, content)

    def research(self, task, system, prompt, **_):
        return self._next(task, system, prompt)

    def tasks(self):
        return [c["task"] for c in self.calls]
