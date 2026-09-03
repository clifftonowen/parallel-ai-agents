# The pipeline backend: FastAPI, and the subprocess it spawns to do the work.
#
# Web and worker are the same image on purpose. run_manager spawns
# benchmark_profile.py with subprocess.Popen against the local filesystem, and
# the live process handle and SSE queues live in the web process's memory
# (run_state.RunState). Splitting them needs a real queue, not a second
# Dockerfile.
#
# Every external binary has to be on PATH. On Linux pdf_agent._resolve_tool
# degrades to a bare shutil.which, and a missing binary is *caught* by the
# orchestrators, which drop that artifact and let the run report success. An
# image missing pandoc therefore produces runs that quietly contain no PDFs,
# which is why the server probes for all of them at startup and says what it
# found.

# Pinned by digest, not by tag. python:3.11-slim moves, so an unpinned tag
# means the image you deploy is not the image you tested. Bump this
# deliberately rather than discovering a base change through a failed run.
FROM python@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534 AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# ffmpeg   video assembly, and the audio probe the segment encoder uses
# pandoc   every PDF
# fonts    xelatex and Chromium both render nothing useful without them
# curl/ca  fetching tectonic below
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        pandoc \
        curl \
        ca-certificates \
        gosu \
        fonts-dejavu-core \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# tectonic rather than texlive: ~35MB against 1.3GB, and it is already first in
# the engine list that pandoc will accept after xelatex and lualatex. It fetches
# LaTeX packages on demand, so the bundle is warmed at build time below --
# otherwise the first PDF in production blocks on a cold download.
ARG TECTONIC_VERSION=0.15.0
# The digest of the tarball this image was built and tested against. The
# project publishes no SHA256SUMS, so this was computed from the download
# rather than checked against an independent source: it cannot tell you the
# release was good, but it does mean a later substitution, a tampered mirror or
# a MITM fails the build instead of shipping quietly.
ARG TECTONIC_SHA256=dfb82876f2986862996e564fa507a9e576e0c1e3bee63c2c1bd677c2543e6407
RUN curl -fsSL -o /tmp/tectonic.tar.gz \
      "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    && echo "${TECTONIC_SHA256}  /tmp/tectonic.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic \
    && rm /tmp/tectonic.tar.gz \
    && chmod +x /usr/local/bin/tectonic \
    && tectonic --version

WORKDIR /app

# Dependencies before source, so editing a .py does not reinstall the world.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Kept adjacent to the pip install on purpose: requirements.txt warns that a
# pip/browser version skew shows up as "Executable doesn't exist" halfway
# through a run, which is a miserable thing to debug in production.
#
# Installed to a shared path rather than the default under /root, because the
# process that actually launches Chromium runs as `app` and cannot read root's
# home. That failure looks identical to the version skew above.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright

# Warm the tectonic bundle so the first production PDF does not pay for it.
# Best effort: a network hiccup here should not fail the build, it should just
# cost the first PDF what it would have cost anyway.
RUN printf 'hello' > /tmp/warm.tex \
    && (tectonic -X compile /tmp/warm.tex --outdir /tmp || true) \
    && rm -rf /tmp/warm.tex /tmp/warm.pdf

COPY . .

# Runtime state lives on the mounted volume, not the image layer. The signing
# key follows DB_PATH automatically (signing.py), but SIGNING_SECRET should be
# set anyway: without it every container mints its own key and every media and
# SSE grant issued by the previous one breaks on deploy.
ENV STUDY_BENCH_DB=/data/study_bench.db \
    OUTPUT_ROOT=/data/output \
    TMPDIR=/data/tmp \
    PORT=8080

# An unprivileged user to run as. This image renders model-written HTML in a
# headless browser and feeds model-written Markdown to pandoc and a LaTeX
# engine, so the process doing that should not be root.
#
# /app is owned by it because MoviePy writes its temp files into the subprocess
# cwd, which is /app, not into TMPDIR. There is a 6MB TEMP_MPY file in the
# development checkout right now that proves it.
#
# Ownership rather than 0777: the previous version made everything
# world-writable, which grants far more than the one process that needs it.
RUN useradd --system --create-home --uid 10001 app \
    && mkdir -p /data/output /data/tmp \
    && chown -R app:app /data /app

EXPOSE 8080

# --workers 1 is not a default, it is a requirement. run_manager.runs is a
# process-local dict, so a second worker 404s on its peer's runs, and the
# concurrent-run limit is counted in that same dict, so N workers would mean N
# times the spend cap.
#
# Not `python api_server.py`: that path sets reload=True, and the reloader
# would both duplicate that state and restart on the app's own writes to
# output/.
# Starts as root only long enough to take ownership of the mounted volume,
# which Fly attaches root-owned, then execs as `app`.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT} --workers 1"]
