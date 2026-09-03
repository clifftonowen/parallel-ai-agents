#!/bin/sh
# Take ownership of the mounted volume, then drop to an unprivileged user.
#
# The container starts as root for exactly this: Fly attaches a volume owned by
# root, so a process that was never root cannot write to it, and the database,
# the generated artifacts and the signing key all live there.
#
# Everything after the exec runs as `app`. That matters more here than in a
# typical web service, because this image renders model-written HTML in a
# headless browser and hands model-written Markdown to pandoc and a LaTeX
# engine. None of that should be able to touch the image as root.
set -e

mkdir -p /data/output /data/tmp

# Best effort. If the volume is already owned correctly, or the filesystem does
# not support the change, that is not a reason to refuse to boot.
chown -R app:app /data 2>/dev/null || true

exec gosu app "$@"
