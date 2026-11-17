"""Dedicated assessment worker. `--once` is a deterministic restart test boundary."""
import argparse
from .runner import worker_loop

parser=argparse.ArgumentParser()
parser.add_argument('--once',action='store_true',help='Process at most one queued job and exit')
args=parser.parse_args()
worker_loop(once=args.once)
