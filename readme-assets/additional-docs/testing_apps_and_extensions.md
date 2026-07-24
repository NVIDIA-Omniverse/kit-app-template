# Testing Applications and Extensions

From the perspective of the Omniverse Kit SDK, everything is an extension — including the `.kit` files that define applications. The `test` tool (`repo_test`) reflects this: it validates that your applications start up and shut down cleanly, and it runs the automated tests defined within your extensions. Each extension template provided by the `kit-app-template` repository ships with sample tests that you can expand to grow your coverage.

This document covers running tests, understanding what is tested, and adding your own tests.

---

## Prerequisites: Build Before You Test

The test tool runs against the contents of the `_build` directory, so a successful build must precede any test run. If you have changed source since your last build, rebuild first.

**Linux:**
```bash
./repo.sh build
```
**Windows:**
```powershell
.\repo.bat build
```

> **Note:** Tests run against a specific build configuration. By default the tooling builds and tests the `release` configuration. If you build `debug`, pass the matching `--config debug` flag when testing.

---

## Running Tests

### Run the Default Test Suite

Running `test` with no arguments executes the repository's default test suite (`alltests`). The tool discovers every test-enabled extension in the build, launches each within the Kit test harness, and reports the aggregated results.

**Linux:**
```bash
./repo.sh test
```
**Windows:**
```powershell
.\repo.bat test
```

For each test-enabled extension — and each application `.kit` file — the tool starts a dedicated Kit process, loads the extension along with its test dependencies, runs the tests, and verifies a clean shutdown.

### Listing Tests Without Running Them

Use `--list` (`-l`) to enumerate the tests that would run without executing them. This is useful for confirming that a newly added extension or test is being discovered.

**Linux:**
```bash
./repo.sh test --list
```
**Windows:**
```powershell
.\repo.bat test --list
```

### Running a Subset of Tests

Use `--filter-files` (`-f`) to narrow a run to specific test files, modules, classes, or individual tests. This shortens the feedback loop while iterating on a single extension.

**Linux:**
```bash
./repo.sh test -f my_company.my_extension
```
**Windows:**
```powershell
.\repo.bat test -f my_company.my_extension
```

> **Note:** The accepted `--filter-files` format depends on the underlying test executor. For the Python (`omni.kit.test` / `unittest`) tests used by the extension templates, you may specify modules, classes, or individual tests. Run `./repo.sh test -h` for the full description.

### Selecting a Build Configuration

By default the test tool targets the `release` configuration. To test a `debug` build, pass `--config` (`-c`). The configuration must match the one you built.

**Linux:**
```bash
./repo.sh test --config debug
```
**Windows:**
```powershell
.\repo.bat test --config debug
```

### Other Useful Options

| Option | Purpose |
|--------|---------|
| `-s, --suite` | Select which test suite(s) to run (default: `alltests`). |
| `-f, --filter-files` | Run only tests matching a file/module/class/test pattern. |
| `-l, --list` | List the discovered tests and exit without running them. |
| `-c, --config` | Test the `release` (default) or `debug` build configuration. |
| `-p, --from-package` | Test an application package instead of the local build (see *Testing a Packaged Application* below). |
| `-e, --extra-arg` | Pass an additional argument through to the test process. Repeatable. |
| `--coverage` | Produce a Python code-coverage report after the run (for supported suite types). |
| `--generate-report` | Run the configured report-generation command, if one is set, after all tests complete. |

For the complete, authoritative list of options, run:

**Linux:**
```bash
./repo.sh test -h
```
**Windows:**
```powershell
.\repo.bat test -h
```

---

## What Gets Tested

### Application Startup and Shutdown

Every application `.kit` file is validated to confirm it can start up and shut down without error. This catches broken dependencies and misconfiguration early — a large portion of application health is covered simply by verifying that the fully assembled set of extensions loads cleanly.

An application declares how it should be launched during testing through a `[[test]]` table in its `.kit` file. For example, the Kit Base Editor template includes:

```toml
[[test]]
args = [
    "--/app/file/ignoreUnsavedOnExit=true"
]
```

The `args` are passed to the Kit process when the application is tested. Templates that provide a setup extension go further, adding explicit startup tests — for example, verifying that a required setting is enabled:

```python
import carb.settings
from omni.kit.test import AsyncTestCase


class TestAppStartup(AsyncTestCase):
    async def test_l1_app_startup_fsd_enabled(self):
        """Check if Fabric Scene Delegate is enabled at startup"""
        fsd_enabled = carb.settings.get_settings().get("/app/useFabricSceneDelegate")
        self.assertTrue(fsd_enabled)
```

### Extension Tests

While application testing confirms that everything loads, the tests written inside your extensions define the majority of functional coverage. Extensions opt into testing with a `[[test]]` table in their `extension.toml`, which may declare test-only dependencies and extra arguments:

```toml
[[test]]
dependencies = [
    "omni.kit.ui_test",  # UI testing helper, loaded only during tests
]

args = [
]
```

Dependencies listed here are loaded only for the test run — a convenient place to pull in helpers such as `omni.kit.ui_test` without adding them to your extension's runtime dependencies.

---

## Writing Tests

Tests use `omni.kit.test`, Python's standard `unittest` module wrapped to support `async`/`await`. Placing a test class derived from `omni.kit.test.AsyncTestCase` at the root of a module within your extension's `tests/` package makes it auto-discoverable — no registration step is required.

Every extension template includes a `tests/` package with a sample test to build on. For example, the Basic Python extension template provides:

```python
import my_company.my_extension
import omni.kit.test


class Test(omni.kit.test.AsyncTestCaseFailOnLogError):
    async def setUp(self):
        # Runs before each test
        pass

    async def tearDown(self):
        # Runs after each test
        pass

    async def test_hello_public_function(self):
        result = my_company.my_extension.some_public_function(4)
        self.assertEqual(result, 256)
```

> **Tip:** `AsyncTestCaseFailOnLogError` fails the test if any error is written to the log during its execution — a simple way to catch unexpected runtime errors in addition to your explicit assertions.

To add coverage, place additional `test_*.py` modules in the extension's `tests/` package and grow the assertions from there. Because tests are standard `unittest` cases, refer to the [Python `unittest` documentation](https://docs.python.org/3/library/unittest.html) for available assertion methods and patterns.

---

## Test Suites and Configuration

The behavior of the test tool for this repository is configured under `[repo_test]` in the top-level `repo.toml`. The most relevant settings are the default suite and any per-suite exclusions:

```toml
[repo_test]
default_suite = "alltests"

[repo_test.suites."alltests"]
exclude = [
    # Setup extension tests are exercised as part of application testing
    "tests-omni.usd_explorer.setup${shell_ext}",
]
```

- **`default_suite`** determines which suite runs when you invoke `test` without `--suite`.
- **`suites.<name>.exclude`** removes specific test executables from a suite — useful when a set of tests is already covered elsewhere.

Adjust these settings as your project grows to control exactly what the default `./repo.sh test` run covers.

---

## Testing a Packaged Application

In addition to testing the local build, the tool can run the suite against a packaged application archive — useful for validating a package before distribution. Use `--from-package` (`-p`), which by default looks for an archive in `_build/packages`.

**Linux:**
```bash
./repo.sh test --from-package
```
**Windows:**
```powershell
.\repo.bat test --from-package
```

The archive pattern is configurable in `repo.toml`:

```toml
[repo_test]
# When running from a package, find the archive using this pattern:
archive_pattern = "${root}/_build/packages/*.zip"
```

> **Note:** Package testing is intended for the "fat" package type, which already contains the Kit Kernel and all extensions, so no additional download is required to run the tests. See [Packaging An Application](../../docs/packaging_app.md) for how to create a package.

---

## Testing in Continuous Integration

`repo test` is the same entry point used by automated pipelines, so tests you run locally behave consistently in CI. Keeping the sample tests passing — and expanding them as you add functionality — helps ensure your applications and extensions remain buildable, launchable, and correct as the project evolves.

---

## Additional Resources

- [Packaging An Application](../../docs/packaging_app.md)
- [Kit SDK Tooling Guide](kit_app_template_tooling_guide.md)
- [Kit SDK Companion Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html)
- [Python `unittest` documentation](https://docs.python.org/3/library/unittest.html)
