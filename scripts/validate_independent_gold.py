"""Validate externally authored, independently reviewed JSONL benchmark labels."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from evaluation.independent_gold import validate_gold_jsonl


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('file',type=Path)
    p.add_argument('--output',type=Path,default=None)
    args=p.parse_args(argv)
    try:
        report=validate_gold_jsonl(args.file)
    except (OSError,ValueError) as exc:
        print(f'FAILED: {type(exc).__name__}: {exc}',file=sys.stderr)
        return 1
    encoded=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding='utf-8')
    print(encoded)
    return 0


if __name__=='__main__':raise SystemExit(main())
