from inert.config import load_config


def render_harness(tests: list[str], test_seconds: int | None = None) -> str:
    if not tests:
        raise ValueError("At least one test is required.")
    seconds = test_seconds if test_seconds is not None else load_config()["sandbox"]["test_seconds"]
    return f"""import signal

TESTS = {tests!r}

class _Timeout(Exception):
    pass

def _handler(signum, frame):
    raise _Timeout()

def main():
    passed = 0
    try:
        import solution
        namespace = dict(vars(solution))
    except BaseException:
        print(f"RESULT: 0/{{len(TESTS)}}")
        return
    signal.signal(signal.SIGALRM, _handler)
    for test in TESTS:
        try:
            signal.alarm({seconds})
            exec(test, dict(namespace))
            passed += 1
        except BaseException:
            pass
        finally:
            signal.alarm(0)
    print(f"RESULT: {{passed}}/{{len(TESTS)}}")

if __name__ == "__main__":
    main()
"""
