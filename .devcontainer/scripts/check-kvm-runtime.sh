#!/usr/bin/env bash
set -euo pipefail

# Advisory: keep the IDE and Review's automatic Apptainer fallback available.
# Device permissions and runtime registration do not prove that a VM can boot.
printf '\n=== KVM / krun availability ===\n'
printf 'Review runtime preference: %s (auto, krun, or apptainer)\n' "${REVIEW_RUNTIME:-auto}"
if [ ! -c /dev/kvm ]; then
  echo 'WARNING: /dev/kvm is missing or is not a character device. Verify host KVM/nested virtualization and rebuild with Devsy Docker runArgs --device=/dev/kvm.'
elif [ ! -r /dev/kvm ] || [ ! -w /dev/kvm ]; then
  echo 'WARNING: /dev/kvm is not readable/writable. Check the device group and id output; rebuild with the Wolfi KVM group setup, then reconnect Devsy so sessions inherit the group. Do not chmod the host device.'
  ls -ln /dev/kvm
  id
else
  echo '/dev/kvm: readable/writable character device'
fi

if ! command -v podman >/dev/null 2>&1; then
  echo 'WARNING: Podman is missing; use the Wolfi image with rootless Podman and crun/libkrun support.'
elif ! podman info >/dev/null 2>&1; then
  echo 'WARNING: Podman is unreachable. Run podman info to diagnose rootless UID/GID mappings, storage, and XDG_RUNTIME_DIR.'
elif runtime="$(podman info --runtime=krun --format '{{.Host.OCIRuntime.Name}}' 2>/dev/null)" && [ "$runtime" = krun ]; then
  echo 'krun: registered with Podman'
else
  echo 'WARNING: krun is unavailable. Rebuild the Wolfi image with crun +LIBKRUN, /usr/bin/krun, and the Podman krun runtime registration.'
fi

echo 'VM launch remains unverified by startup checks. After rebuilding, test Podman/krun and Review with LUNA_FACTORY_ENABLED=1.'
echo 'If device access passes but VM launch fails, inspect rootless supplementary-group retention, host cgroup device policy, and nested KVM support.'
