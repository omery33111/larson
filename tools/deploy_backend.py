"""
Ship the backend to Elastic Beanstalk.

**Built with `zipfile` and never with PowerShell's `Compress-Archive`**, which writes `\\` as
the path separator inside the archive. That produced a deploy where every file was named
literally `assets\\index-*.js`, the entry point returned 200 and everything it pointed at
returned 404 - a site serving a shell with no application in it, and every status along the
way green.

**The path is derived from this file's location, not written out.** While these lived
in a scratch folder a hardcoded absolute path was harmless; in the repo it would make the
script useless in any clone but one machine's.
"""

import pathlib
import os
import subprocess
import sys
import zipfile
from datetime import datetime

ROOT = str(pathlib.Path(__file__).resolve().parent.parent / "back-end")
BUCKET = "elasticbeanstalk-eu-central-1-904233086909"
APP, ENV = "larson", "larson-api"

SKIP_DIRS = {".venv", "__pycache__", "media", "staticfiles", ".git", "node_modules"}
SKIP_FILES = {".env", ".env.production", "db.sqlite3"}


def build(path):
    written = 0

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for folder, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for name in files:
                if name in SKIP_FILES or name.endswith((".pyc", ".sqlite3")):
                    continue

                full = os.path.join(folder, name)
                # Forward slashes, always - that is the whole point of using zipfile.
                inside = os.path.relpath(full, ROOT).replace("\\", "/")
                bundle.write(full, inside)
                written += 1

    return written


def run(*args):
    done = subprocess.run(args, capture_output = True, text = True)
    if done.returncode:
        print(done.stdout, done.stderr)
        sys.exit(f"failed: {' '.join(args[:3])}")
    return done.stdout.strip()


def main():
    label = "v-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    local = os.path.join(os.environ["TEMP"], label + ".zip")

    print("building  ", end = "", flush = True)
    print("%d files -> %s" % (build(local), local))

    # A sanity check on the thing that went wrong last time, before it leaves the machine.
    with zipfile.ZipFile(local) as bundle:
        names = bundle.namelist()
    assert not any("\\" in n for n in names), "backslashes in the archive"
    assert "project/settings.py" in names and "Procfile" in names, "missing core files"
    print("checked    separators are '/', Procfile and settings are in")

    key = f"{APP}/{label}.zip"
    run("aws", "s3", "cp", local, f"s3://{BUCKET}/{key}")
    print("uploaded  ", key)

    run("aws", "elasticbeanstalk", "create-application-version",
        "--application-name", APP, "--version-label", label,
        "--source-bundle", f"S3Bucket={BUCKET},S3Key={key}",
        "--description", label)
    print("version    created")

    run("aws", "elasticbeanstalk", "update-environment",
        "--environment-name", ENV, "--version-label", label)
    print("deploying  %s -> %s" % (label, ENV))
    print("\n  LABEL=%s" % label)


main()
