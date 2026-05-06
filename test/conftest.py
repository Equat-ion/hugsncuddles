import os
import pytest

INTEGRATION_ENV_KEYS = [
    "E2B_API_KEY",
    "GITHUB_APP_ID",
    "GITHUB_APP_PRIVATE_KEY",
    "GITHUB_INSTALLATION_ID",
]

def has_env(*keys: str) -> bool:
    return all(os.environ.get(k) for k in keys)

def pytest_addoption(parser):
    parser.addoption("--run-integration", action="store_true", help="run integration tests")

def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        if not has_env(*INTEGRATION_ENV_KEYS):
            missing = [k for k in INTEGRATION_ENV_KEYS if not os.environ.get(k)]
            skip = pytest.mark.skip(reason=f"missing env vars: {missing}")
            for item in items:
                if "integration" in item.keywords:
                    item.add_marker(skip)
        return
    skip = pytest.mark.skip(reason="integration tests disabled (use --run-integration)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)