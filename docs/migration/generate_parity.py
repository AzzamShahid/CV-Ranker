"""Compatibility entry point: regenerate the authoritative completion register."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('generate_completion_register.py')),
                   run_name='__main__')
