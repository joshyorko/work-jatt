#!/usr/bin/env bash
set +x
set -euo pipefail

export PATH="${HOME}/.local/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

require_environment() {
  local variable_name="$1"

  if [ -n "${!variable_name:-}" ]; then
    printf '%-36s %s\n' "${variable_name}:" "${!variable_name}"
  else
    echo "ERROR: required devcontainer environment variable is missing: ${variable_name}" >&2
    return 2
  fi
}

require_command() {
  local command_name="$1"

  if command -v "${command_name}" >/dev/null 2>&1; then
    printf '%-12s %s\n' "${command_name}:" "$(command -v "${command_name}")"
  else
    echo "ERROR: required Review runtime command is missing: ${command_name}" >&2
    return 1
  fi
}

printf '\n=== Dev container environment ===\n'
for variable_name in \
  DEV_CONTAINERS_SKIP_GCOMPAT_INSTALL \
  HOMEBREW_NO_ANALYTICS \
  REVIEW_UPSTREAM_REF \
  BLUEFIN_REVIEW_INHERIT_OMP_CONFIG \
  HEADROOM_BASE_URL \
  LUNA_FACTORY_ENABLED \
  LUNA_FACTORY_CAPACITY; do
  require_environment "${variable_name}"
done

report_headroom_configuration() {
  local models_file="${HOME}/.omp/profiles/review/agent/models.yml"
  local codex_file="${CODEX_HOME:-${HOME}/.codex}/config.toml"

  if [ ! -f "${models_file}" ] || [ ! -f "${codex_file}" ]; then
    echo 'Headroom authentication is not configured; VS Code will prompt after connecting.'
    return 0
  fi

  local codex_token omp_token
  if ! codex_token="$(yq -p toml -r '.model_providers.headroom.http_headers."X-Headroom-Proxy-Token" // ""' "${codex_file}" 2>/dev/null)" ||
     ! omp_token="$(yq -r '.providers."openai-codex".headers."X-Headroom-Proxy-Token" // ""' "${models_file}" 2>/dev/null)"; then
    echo 'ERROR: cannot parse Headroom configuration.' >&2
    return 1
  fi
  if [ -n "${codex_token}" ] && [ "${codex_token}" = "${omp_token}" ] &&
     HEADROOM_BASE_URL="${HEADROOM_BASE_URL}" yq -e \
       '.providers."openai-codex".baseUrl == strenv(HEADROOM_BASE_URL)' \
       "${models_file}" >/dev/null 2>&1 &&
     HEADROOM_BASE_URL="${HEADROOM_BASE_URL}" yq -p toml -e \
       '.model_provider == "headroom" and .model_providers.headroom.base_url == strenv(HEADROOM_BASE_URL) and .model_providers.headroom.requires_openai_auth == true' \
       "${codex_file}" >/dev/null 2>&1; then
    echo 'Headroom headers: configured for Codex and Review OMP (connectivity not tested).'
  else
    echo 'Headroom configuration needs setup; use Headroom: Update Proxy Token in the VS Code Command Palette.'
  fi
}

require_managed_codex() {
  local launcher="${HOME}/.local/bin/codex"
  local managed="${CODEX_HOME:-${HOME}/.codex}/packages/standalone/current/bin/codex"
  if [ ! -x "${managed}" ] || [ ! -x "${launcher}" ] ||
     [ "$(readlink -f -- "${launcher}")" != "$(readlink -f -- "${managed}")" ]; then
    echo 'ERROR: Codex standalone installation is missing; rerun the devcontainer bootstrap.' >&2
    return 1
  fi
  "${launcher}" --version
}

printf '\n=== Review source ===\n'
git -C "${HOME}/src/review" log -1 --oneline
printf '\n=== Installed Review package ===\n'
brew list --versions joshyorko/review-dev/bluefin-review-dev
printf '\n=== Review runtime ===\n'
require_command gh
require_command apptainer
require_command squashfuse
require_command gocryptfs
require_command fuse2fs
require_command bluefin
require_command yq
require_command python3
require_managed_codex
report_headroom_configuration
printf '\n'
if [ -e /dev/fuse ]; then
  echo '/dev/fuse: READY'
else
  echo 'WARNING: /dev/fuse is missing'
fi
if [ -e /dev/kvm ]; then
  echo '/dev/kvm: READY'
else
  echo 'WARNING: /dev/kvm is missing'
fi
printf '\nReview runtime check complete.\n'
echo 'Next: gh auth login'
echo 'Review source: ~/src/review (upstream/main)'
echo 'Run: bluefin review projectbluefin/review'
