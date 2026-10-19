"""
Ship the built frontend to Amplify, and say what to verify afterwards.

**`zipfile`, never `Compress-Archive`**: PowerShell writes `\\` inside the archive, so
Amplify received one file literally named `assets\\index-*.js`. `index.html` deployed fine
and returned 200; every asset it pointed at returned 404. A shell with no application in it,
and every status along the way green.

**The path is derived from this file's location, not written out.** While these lived
in a scratch folder a hardcoded absolute path was harmless; in the repo it would make the
script useless in any clone but one machine's.
"""

import pathlib
import json
import os
import subprocess
import sys
import urllib.request
import zipfile

DIST = str(pathlib.Path(__file__).resolve().parent.parent / "front-end" / "dist")
APP, BRANCH = "dznz974usudjz", "main"


def run(*args):
    done = subprocess.run(args, capture_output = True, text = True)
    if done.returncode:
        print(done.stdout, done.stderr)
        sys.exit(f"failed: {' '.join(args[:3])}")
    return done.stdout.strip()


def main():
    local = os.path.join(os.environ["TEMP"], "larson-front.zip")
    sizes = {}

    with zipfile.ZipFile(local, "w", zipfile.ZIP_DEFLATED) as bundle:
        for folder, _, files in os.walk(DIST):
            for name in files:
                full = os.path.join(folder, name)
                inside = os.path.relpath(full, DIST).replace("\\", "/")
                bundle.write(full, inside)
                sizes[inside] = os.path.getsize(full)

    with zipfile.ZipFile(local) as bundle:
        names = bundle.namelist()

    assert not any("\\" in n for n in names), "backslashes in the archive"
    assert "index.html" in names, "no entry point"
    print("built      %d files, separators are '/'" % len(names))

    # ------------- AND WHERE IT POINTS, WHICH NOTHING ELSE WOULD TELL US:
    #
    # **`VITE_API_URL` is baked in at build time**, so a build run with the development
    # value deploys a site that loads perfectly and fails on every screen - and no status
    # anywhere goes red. `.env.production` is what keeps this right today; this is what
    # notices the day it stops.
    #
    # Read out of the archive that is about to be uploaded, not out of `dist` - the
    # question is what is in the thing being shipped.
    with zipfile.ZipFile(local) as bundle:
        code = "".join(bundle.read(n).decode("utf-8", "replace") for n in names
                       if n.endswith((".js", ".html")))

    for wrong in ("127.0.0.1", "localhost:8000", "localhost:5173"):
        assert wrong not in code, (
            f"the bundle points at {wrong} - it was built without .env.production, "
            "and every request would go to a developer's machine")

    assert "api.larson.co.il" in code, "the bundle has no production API address in it"
    print("checked    points at api.larson.co.il, no localhost anywhere")

    # The hashed bundle, which is the thing to go and fetch back afterwards.
    js = [n for n in names if n.endswith(".js") and n.startswith("assets/")]
    for n in js:
        print("           %s  %d bytes" % (n, sizes[n]))

    created = json.loads(run("aws", "amplify", "create-deployment",
                             "--app-id", APP, "--branch-name", BRANCH))

    with open(local, "rb") as f:
        request = urllib.request.Request(created["zipUploadUrl"], data = f.read(),
                                         method = "PUT")
        request.add_header("Content-Type", "application/zip")
        urllib.request.urlopen(request)

    print("uploaded   job %s" % created["jobId"])

    run("aws", "amplify", "start-deployment", "--app-id", APP,
        "--branch-name", BRANCH, "--job-id", created["jobId"])

    print("deploying  job %s" % created["jobId"])
    print("\n  VERIFY: curl --compressed https://larson.co.il/%s and grep the new strings"
          % (js[0] if js else "assets/?"))


main()
