#!/usr/bin/env python3
"""Require a CTest JUnit report to contain only executed, passing tests."""

import argparse
import sys
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="CTest --output-junit XML report")
    args = parser.parse_args()

    try:
        root = ET.parse(args.report).getroot()
    except (OSError, ET.ParseError) as error:
        parser.error("cannot read CTest report: {}".format(error))

    testcases = root.findall(".//testcase")
    skipped = []
    failed = []
    for testcase in testcases:
        name = testcase.get("name", "<unnamed>")
        if testcase.find("skipped") is not None:
            skipped.append(name)
        if (testcase.find("failure") is not None or
                testcase.find("error") is not None):
            failed.append(name)

    print("CTest report: {} executed, {} skipped, {} failed".format(
        len(testcases), len(skipped), len(failed)))

    if not testcases:
        print("error: CTest selected no tests", file=sys.stderr)
        return 1
    if skipped:
        print("error: skipped tests: {}".format(", ".join(skipped)),
              file=sys.stderr)
    if failed:
        print("error: failed tests: {}".format(", ".join(failed)),
              file=sys.stderr)
    return 1 if skipped or failed else 0


if __name__ == "__main__":
    sys.exit(main())
