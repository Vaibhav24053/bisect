import os
import time


def pytest_sessionstart(session):
    time.sleep(float(os.environ.get("SIM_BUILD_SECS", "0")))
