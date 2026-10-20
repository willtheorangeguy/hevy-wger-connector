"""Run deterministic tests using the sibling wger harness and isolated accounts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wger-harness", type=Path, default=ROOT.parent / "wger-addon-harness")
    parser.add_argument("--keep-users", action="store_true", help="Keep this run's dedicated accounts for inspection")
    args = parser.parse_args()
    harness = args.wger_harness.resolve()
    if not (harness / "harness.py").is_file():
        parser.error("A wger-addon-harness checkout is required; set --wger-harness")
    run([sys.executable, str(harness / "harness.py"), "up"])
    runtime, reports = ROOT / "runtime", ROOT / "reports"
    runtime.mkdir(exist_ok=True)
    reports.mkdir(exist_ok=True)
    runtime.chmod(0o777)
    reports.chmod(0o777)
    run_id = uuid.uuid4().hex[:12]
    users = [f"hevy_connector_it_{run_id}_{i}" for i in range(3)]
    setup = '''
import json, secrets
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from wger.exercises.models import Exercise
accounts=[]
for name in USER_NAMES:
    user=User.objects.create_user(username=name,password=secrets.token_urlsafe(24))
    accounts.append({'username':name,'token':Token.objects.get_or_create(user=user)[0].key})
print('CONNECTOR_TEST_JSON='+json.dumps({'accounts':accounts,'exercise_ids':list(Exercise.objects.order_by('pk').values_list('pk',flat=True)[:4])}))
'''.replace("USER_NAMES", repr(users))
    command = ["docker", "compose", "-f", str(harness / "compose.yaml"), "exec", "-T", "web",
               "python3", "manage.py", "shell", "-c", "exec(__import__('sys').stdin.read())"]
    result = run(command, input=setup, text=True, capture_output=True)
    line = next(line for line in result.stdout.splitlines() if line.startswith("CONNECTOR_TEST_JSON="))
    credentials = runtime / "test-credentials.json"
    credentials.write_text(line.split("=", 1)[1], encoding="utf-8")
    compose = ["docker", "compose", "-f", "compose.test.yaml"]
    try:
        run(compose + ["build", "test"])
        run(compose + ["up", "-d", "--wait", "mock-hevy"])
        run(compose + ["run", "--rm", "test"])
    finally:
        # Only the separate test project is stopped; the user's wger stays up.
        subprocess.run(compose + ["down"], cwd=ROOT, check=False)
        if not args.keep_users:
            cleanup = "from django.contrib.auth.models import User\nUser.objects.filter(username__in=" + repr(users) + ").delete()"
            run(command, input=cleanup, text=True, capture_output=True)
            credentials.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"Test harness failed (exit {error.returncode}); see reports/junit.xml", file=sys.stderr)
        sys.exit(1)
