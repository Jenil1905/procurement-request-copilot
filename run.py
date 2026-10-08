"""One-command runner fallback: python run.py

Creates venv if needed, installs dependencies, verifies mock API and Web App,
and launches both services printing the URL.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
IS_WINDOWS = sys.platform.startswith("win")
VENV_PYTHON = VENV_DIR / ("Scripts" if IS_WINDOWS else "bin") / ("python.exe" if IS_WINDOWS else "python")
REQUIREMENTS_FILE = ROOT / "requirements.txt"


def ensure_environment() -> Path:
    """Ensures .venv exists and dependencies are installed."""
    if not VENV_DIR.exists() or not VENV_PYTHON.exists():
        print(f"Creating virtual environment in {VENV_DIR} ...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=ROOT)

    # Ensure .env exists
    env_file = ROOT / ".env"
    env_example = ROOT / ".env.example"
    if not env_file.exists() and env_example.exists():
        print("Creating .env from .env.example ...")
        shutil.copyfile(env_example, env_file)

    # Install requirements
    if REQUIREMENTS_FILE.exists():
        print("Checking/installing dependencies from requirements.txt ...")
        subprocess.check_call(
            [str(VENV_PYTHON), "-m", "pip", "install", "--quiet", "-r", str(REQUIREMENTS_FILE)],
            cwd=ROOT,
        )

    return VENV_PYTHON


def main() -> None:
    python_bin = ensure_environment()
    print("Launching AI Procurement Copilot stack ...")
    run_local_script = ROOT / "run_local.py"
    try:
        subprocess.check_call([str(python_bin), str(run_local_script)], cwd=ROOT)
    except KeyboardInterrupt:
        print("\nCopilot shutdown complete.")


if __name__ == "__main__":
    main()
