"""Print the next release version from the commits since the last v* tag.

The bump follows Conventional Commits: a breaking change ("type!:" or a
"BREAKING CHANGE" footer) bumps the major number, a "feat" commit bumps the
minor number, and anything else bumps the patch number. The first release,
with no v* tag yet, is v1.0.0.

Writes version=<vX.Y.Z> and release=<true|false> to $GITHUB_OUTPUT when that
variable is set. release is false when HEAD already carries the last tag, as
on a re-run, so the workflow redeploys without making a second release.

Usage: python3 scripts/version.py
"""
import os
import re
import subprocess


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def next_version():
    last = git("describe", "--tags", "--abbrev=0", "--match", "v*")
    if not last:
        return "v1.0.0", True
    log = git("log", f"{last}..HEAD", "--format=%s%n%b%n--end--")
    commits = [c.strip() for c in log.split("--end--") if c.strip()]
    if not commits:
        return last, False
    major, minor, patch = (int(n) for n in last.lstrip("v").split("."))
    if any(re.match(r"^\w+(\([^)]*\))?!:", c) or "BREAKING CHANGE" in c for c in commits):
        return f"v{major + 1}.0.0", True
    if any(re.match(r"^feat(\([^)]*\))?:", c) for c in commits):
        return f"v{major}.{minor + 1}.0", True
    return f"v{major}.{minor}.{patch + 1}", True


if __name__ == "__main__":
    version, release = next_version()
    print(version, "(new release)" if release else "(already released)")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"version={version}\nrelease={str(release).lower()}\n")
