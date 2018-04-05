from sbp.client.loggers import json_logger
from sbp.table import dispatch
import argparse


def expand_json(infile, outfile):
    with open(infile, 'r') as log_handle:
      with open(outfile, 'w') as output:
        with json_logger.JSONLogIterator(log_handle) as iterator:
          with json_logger.JSONLogger(output) as logger:
            for each in iterator.next():
              logger(each[0], **each[1])

def main():
    parser = argparse.ArgumentParser(
        description="Swift Navigation SBP Log Expander")
    parser.add_argument("log")
    args = parser.parse_args()
    infile = args.log
    outfile = infile.split(".")[0] + ".ex.sbp.json"
    expand_json(infile, outfile)

if __name__ == "__main__":
  main()
