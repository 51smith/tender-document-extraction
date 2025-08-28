"""Performance test runner with automated scenarios."""

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import httpx


@dataclass
class PerformanceTestConfig:
    """Configuration for performance tests."""

    test_name: str
    users: int
    spawn_rate: float
    run_time: str  # e.g., "60s", "5m"
    user_class: str = "WebsiteUser"
    host: str = "http://localhost:8001"
    expected_failure_rate: float = 0.05  # 5%
    expected_avg_response_time: float = 5000  # 5 seconds


class PerformanceTestRunner:
    """Runs automated performance tests with different scenarios."""

    def __init__(self, results_dir: Path = None):
        if results_dir is None:
            results_dir = Path(__file__).parent / "reports"

        self.results_dir = results_dir
        self.results_dir.mkdir(exist_ok=True)

    async def run_test_suite(self) -> Dict[str, Dict]:
        """Run complete performance test suite."""
        test_configs = [
            PerformanceTestConfig(
                test_name="baseline_load",
                users=10,
                spawn_rate=2,
                run_time="120s",
                expected_avg_response_time=3000,
            ),
            PerformanceTestConfig(
                test_name="moderate_load",
                users=25,
                spawn_rate=5,
                run_time="180s",
                expected_avg_response_time=5000,
            ),
            PerformanceTestConfig(
                test_name="high_load",
                users=50,
                spawn_rate=10,
                run_time="300s",
                expected_avg_response_time=8000,
                expected_failure_rate=0.1,
            ),
            PerformanceTestConfig(
                test_name="stress_test",
                users=100,
                spawn_rate=20,
                run_time="180s",
                user_class="StressTestUser",
                expected_avg_response_time=12000,
                expected_failure_rate=0.15,
            ),
            PerformanceTestConfig(
                test_name="consistency_test",
                users=5,
                spawn_rate=1,
                run_time="300s",
                user_class="ConsistencyTestUser",
                expected_avg_response_time=4000,
                expected_failure_rate=0.02,
            ),
        ]

        results = {}

        # Check if test server is available
        if not await self._check_server_availability():
            raise RuntimeError("Test server is not available")

        for config in test_configs:
            print(f"\nRunning {config.test_name}...")
            result = await self._run_single_test(config)
            results[config.test_name] = result

            # Wait between tests to allow system recovery
            print(f"Waiting for system recovery...")
            await asyncio.sleep(30)

        # Generate summary report
        await self._generate_summary_report(results)

        return results

    async def _run_single_test(self, config: PerformanceTestConfig) -> Dict:
        """Run a single performance test configuration."""
        locust_file = Path(__file__).parent / "locustfile.py"
        results_file = self.results_dir / f"{config.test_name}_results.html"

        # Build locust command
        cmd = [
            "locust",
            "-f",
            str(locust_file),
            "-H",
            config.host,
            "-u",
            str(config.users),
            "-r",
            str(config.spawn_rate),
            "-t",
            config.run_time,
            "--headless",
            "--html",
            str(results_file),
            "--csv",
            str(self.results_dir / config.test_name),
            "--user-class",
            config.user_class,
        ]

        # Run the test
        start_time = time.time()
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()
        end_time = time.time()

        # Parse results
        result = self._parse_test_results(config, stdout, stderr, end_time - start_time)

        # Validate against expectations
        self._validate_test_results(config, result)

        return result

    def _parse_test_results(
        self, config: PerformanceTestConfig, stdout: bytes, stderr: bytes, duration: float
    ) -> Dict:
        """Parse Locust test results."""
        output = stdout.decode("utf-8")

        # Extract key metrics from output
        result = {
            "config": config,
            "duration": duration,
            "success": process.returncode == 0 if "process" in locals() else False,
            "stdout": output,
            "stderr": stderr.decode("utf-8") if stderr else "",
        }

        # Try to parse CSV results if available
        stats_file = self.results_dir / f"{config.test_name}_stats.csv"
        if stats_file.exists():
            result.update(self._parse_csv_results(stats_file))

        return result

    def _parse_csv_results(self, csv_file: Path) -> Dict:
        """Parse Locust CSV results."""
        try:
            with open(csv_file, "r") as f:
                lines = f.readlines()

            if len(lines) < 2:
                return {"error": "No data in CSV file"}

            # Parse stats (simplified)
            stats = {}
            for line in lines[1:]:  # Skip header
                parts = line.strip().split(",")
                if len(parts) >= 10 and parts[0] != "Aggregated":
                    stats[parts[0]] = {
                        "method": parts[1],
                        "name": parts[2],
                        "num_requests": int(parts[3]) if parts[3].isdigit() else 0,
                        "num_failures": int(parts[4]) if parts[4].isdigit() else 0,
                        "avg_response_time": float(parts[7])
                        if parts[7].replace(".", "").isdigit()
                        else 0,
                        "max_response_time": float(parts[9])
                        if parts[9].replace(".", "").isdigit()
                        else 0,
                    }

            return {"parsed_stats": stats}

        except Exception as e:
            return {"parse_error": str(e)}

    def _validate_test_results(self, config: PerformanceTestConfig, result: Dict) -> None:
        """Validate test results against expectations."""
        if not result.get("success", False):
            print(f"⚠️  {config.test_name} did not complete successfully")
            return

        parsed_stats = result.get("parsed_stats", {})

        if parsed_stats:
            # Calculate overall metrics
            total_requests = sum(s.get("num_requests", 0) for s in parsed_stats.values())
            total_failures = sum(s.get("num_failures", 0) for s in parsed_stats.values())

            if total_requests > 0:
                failure_rate = total_failures / total_requests
                avg_response_times = [
                    s.get("avg_response_time", 0)
                    for s in parsed_stats.values()
                    if s.get("avg_response_time", 0) > 0
                ]
                avg_response_time = (
                    sum(avg_response_times) / len(avg_response_times) if avg_response_times else 0
                )

                # Validate metrics
                if failure_rate <= config.expected_failure_rate:
                    print(
                        f"✅ {config.test_name} failure rate: {failure_rate:.2%} (expected ≤ {config.expected_failure_rate:.2%})"
                    )
                else:
                    print(
                        f"❌ {config.test_name} failure rate: {failure_rate:.2%} (expected ≤ {config.expected_failure_rate:.2%})"
                    )

                if avg_response_time <= config.expected_avg_response_time:
                    print(
                        f"✅ {config.test_name} avg response time: {avg_response_time:.0f}ms (expected ≤ {config.expected_avg_response_time:.0f}ms)"
                    )
                else:
                    print(
                        f"❌ {config.test_name} avg response time: {avg_response_time:.0f}ms (expected ≤ {config.expected_avg_response_time:.0f}ms)"
                    )

    async def _check_server_availability(self) -> bool:
        """Check if the test server is available."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8001/health", timeout=10)
                return response.status_code == 200
        except Exception:
            return False

    async def _generate_summary_report(self, results: Dict[str, Dict]) -> None:
        """Generate a summary report of all tests."""
        report_file = self.results_dir / "performance_summary.json"

        summary = {"timestamp": time.time(), "total_tests": len(results), "test_results": results}

        with open(report_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        print(f"\nPerformance test summary saved to: {report_file}")

        # Print summary
        print("\n" + "=" * 60)
        print("PERFORMANCE TEST SUMMARY")
        print("=" * 60)

        for test_name, result in results.items():
            status = "✅ PASSED" if result.get("success", False) else "❌ FAILED"
            print(f"{test_name:20} | {status}")

        print("=" * 60)


async def main():
    """Run performance test suite."""
    runner = PerformanceTestRunner()

    print("Starting automated performance test suite...")
    print("Make sure the test server is running at http://localhost:8001")

    try:
        results = await runner.run_test_suite()
        print("\nPerformance test suite completed successfully!")

        # Check if any tests failed
        failed_tests = [
            name for name, result in results.items() if not result.get("success", False)
        ]
        if failed_tests:
            print(f"\nFailed tests: {failed_tests}")
            return 1
        else:
            print("\nAll performance tests passed!")
            return 0

    except Exception as e:
        print(f"\nPerformance test suite failed: {e}")
        return 1


if __name__ == "__main__":
    import sys

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
