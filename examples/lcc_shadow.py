"""Run native ranking inside the opt-in LCC shadow consumer integration."""
import argparse
import json
from pathlib import Path

from lcc_engine import ContextEngine
from lcc.relevance.compactor import RelevanceCompactionRequest, compact_context, report_to_dict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--objective', required=True)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    engine = ContextEngine(args.checkpoint,device='cpu',max_len=8192)
    result = compact_context(RelevanceCompactionRequest(
        text=args.input.read_text(),question=args.objective,provider='specialist',client=engine))
    print(json.dumps(dict(compacted_text=result.compacted_text,report=report_to_dict(result.report)),
                     ensure_ascii=False,allow_nan=False))


if __name__ == '__main__':
    main()
