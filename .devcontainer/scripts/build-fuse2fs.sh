#!/usr/bin/env bash
set -euo pipefail

if command -v fuse2fs >/dev/null 2>&1; then
  exit 0
fi

if [ "$(id -u)" -eq 0 ]; then
  as_root() {
    "$@"
  }
elif command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  as_root() {
    sudo -n "$@"
  }
else
  echo 'ERROR: building fuse2fs requires root or passwordless sudo for vscode.' >&2
  exit 1
fi

echo '==> Building fuse2fs for Wolfi'
as_root apk add --no-cache build-base git pkgconf fuse3-dev linux-headers autoconf automake libtool

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

git clone --depth 1 https://github.com/tytso/e2fsprogs.git "${tmp}/e2fsprogs"
mkdir -p "${tmp}/e2fsprogs/build"
cd "${tmp}/e2fsprogs/build"
../configure
make -j"$(nproc)"
as_root install -m 0755 ./misc/fuse2fs /usr/local/bin/fuse2fs
