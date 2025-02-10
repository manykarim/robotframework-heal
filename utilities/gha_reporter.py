from robot.api import ExecutionResult, ResultVisitor
from pytablewriter import MarkdownTableWriter
import sys


class SuitesWithTestsVisitor(ResultVisitor):
    def __init__(self):
        self.suites_with_tests = []

    def start_suite(self, suite):
        if suite.tests:
            self.suites_with_tests.append(suite)


def main():
    output_file = sys.argv[1]
    markdown_file = sys.argv[2]

    f = open(markdown_file, "w")

    result = ExecutionResult(output_file)

    # Write PieChart as Markdown
    stats = result.statistics
    f.write("```mermaid\n")
    f.write(
        "%%{init: {'theme': 'base', 'themeVariables': { 'pie1': '#00FF00', 'pie2': '#FF0000', 'pie3': '#FFFF00'}}}%%\n"
    )
    f.write("pie title Test Status\n")
    f.write(f'    "Passed" : {stats.total.passed}\n')
    f.write(f'    "Failed" : {stats.total.failed}\n')
    f.write(f'    "Skipped" : {stats.total.skipped}\n')
    f.write("```\n")

    # Get all suites with Tests
    suite_visitor = SuitesWithTestsVisitor()
    result.visit(suite_visitor)
    suites_with_tests = suite_visitor.suites_with_tests

    suite_results = []
    for suite in suites_with_tests:
        suite_results.append(
            [
                suite.name,
                suite.statistics.passed,
                suite.statistics.failed,
                suite.statistics.skipped,
                suite.statistics.total,
                suite.elapsed_time.total_seconds(),
            ]
        )

    # Write Table with Results for each Suite as Markdown
    table_columns = [
        "Test Suite",
        "Passed ✅",
        "Failed ❌",
        "Skipped 🛑",
        "Total",
        "Elapsed Time ⏱️",
    ]
    writer = MarkdownTableWriter(
        table_name="Test Suite Status",
        headers=table_columns,
        value_matrix=suite_results,
    )
    writer.stream = f
    writer.write_table()
    f.write("\n")
    status_emoji = {
        "PASS": "✅PASS",
        "FAIL": "❌FAIL",
        "SKIP": "🛑SKIP",
        "NOT RUN": "NOT RUN",
        "NOT SET": "❓NOT SET",
    }
    for suite in suites_with_tests:
        tests_in_suite = []
        for test in suite.tests:
            tests_in_suite.append(
                [
                    test.name,
                    status_emoji.get(test.status, "unknown"),
                    test.elapsed_time.total_seconds(),
                ]
            )

        # Write Table with Results for each Test Case for a Suite as Markdown
        table_columns = ["Test Case", "Status", "Elapsed Time ⏱️"]
        writer = MarkdownTableWriter(
            table_name=suite.name, headers=table_columns, value_matrix=tests_in_suite
        )
        writer.stream = f
        writer.write_table()
        f.write("\n")


if __name__ == "__main__":
    main()