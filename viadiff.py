import argparse

from vialib import ViaDiff

parser = argparse.ArgumentParser(
    description="Diff between two or more via.com XML responses."
)

parser.add_argument(
    "base_filename", metavar="base_filename.xml", type=str,
    help="Base filename"
)

parser.add_argument(
    "filenames", metavar="filename.xml", type=str, nargs="+",
    help="Additional filenames"
)

args = parser.parse_args()

diffs = ViaDiff.compare_files(args.base_filename, *args.filenames)
for filename, diffs in diffs.items():
    print(filename)
    for v in diffs:
        for vv in v:
            print(vv)
            print()
