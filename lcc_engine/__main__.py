"""JSON input/output for offline shadow scoring; no implicit artifact downloads."""
import argparse
import json
import sys
from . import ContextEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--max-len', type=int, default=8192)
    args = parser.parse_args()
    packet = json.load(sys.stdin)
    result = ContextEngine(args.checkpoint,device=args.device,max_len=args.max_len).rank_context(
        packet['objective'],packet['blocks'])
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__ == '__main__':
    main()
