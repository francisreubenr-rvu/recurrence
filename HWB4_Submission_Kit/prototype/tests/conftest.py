import os
import sys
from pathlib import Path

# Offline before anything imports app.server (it builds the app at import time).
os.environ["RECURRENCE_OFFLINE"] = "1"
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("HINDSIGHT_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from recurrence.llm import OfflineLLM  # noqa: E402
from recurrence.memory import FakeMemory  # noqa: E402
from recurrence.seed import seed  # noqa: E402


@pytest.fixture
def seeded_memory():
    mem = FakeMemory()
    seed(mem)
    return mem


@pytest.fixture
def offline_llm():
    return OfflineLLM()
