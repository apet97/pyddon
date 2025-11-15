# Docker Hardening Notes

This add-on image now follows Clockify marketplace security expectations:

1. **Pinned Base Image** – Uses `python:3.11.8-slim-bookworm` for predictable CVE tracking and reproducible builds.
2. **Multi-Stage Build** – Compiles dependencies in an isolated builder image and copies only wheels + source into the runtime layer to keep the final image small and auditable.
3. **Non-Root Runtime User** – Creates and runs as the dedicated `clockify` user to prevent privilege escalation inside containers.
4. **Minimal Runtime Footprint** – Build-essential packages are confined to the builder layer; the runtime layer only contains Python and the add-on code.
5. **Deterministic Dependency Installs** – Dependencies are pre-built into wheels and installed with `pip --no-cache-dir`, ensuring no mutable state or cached artifacts remain in the image.

Run `docker build --pull --rm -t clockify-python-addon .` after each dependency/security update to pick up the latest patched base layers.
