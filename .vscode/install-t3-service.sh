#!/usr/bin/env bash
set -euo pipefail

export PATH="${HOME}/.local/bin:${PATH}"
export T3CODE_CHANNEL="${T3CODE_CHANNEL:-nightly}"
unit=t3code.service
cli="${HOME}/.local/bin/t3"
prerequisite='Use the wolfi-systemd devcontainer from https://github.com/joshyorko/work-jatt/issues/5.'

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

diagnostics() {
    systemctl --user show "${unit}" --no-pager \
        --property=ActiveState,SubState,Result,MainPID,ExecMainStatus,NRestarts >&2 || true
}

[[ "$(id -un)" == vscode && "$(id -u)" -ne 0 ]] || \
    fail 'Run this task inside the attached Dev Container as the non-root vscode user.'
[[ "$(cat /proc/1/comm)" == systemd ]] || fail "PID 1 is not systemd. ${prerequisite}"
for command in curl systemctl busctl loginctl flock readlink; do
    command -v "${command}" >/dev/null || fail "Missing ${command}. ${prerequisite}"
done
command -v python3 >/dev/null || fail 'Missing python3. Complete the Work-Jatt devcontainer bootstrap before running this task.'

uid="$(id -u)"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${uid}}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"
[[ -S "${XDG_RUNTIME_DIR}/bus" ]] || fail "The vscode user bus is missing. ${prerequisite}"
systemctl is-active --quiet "user@${uid}.service" || fail "The vscode user manager is unavailable. ${prerequisite}"
systemctl --user is-active --quiet default.target || fail "Cannot reach the vscode user manager. ${prerequisite}"
busctl --user call org.freedesktop.systemd1 /org/freedesktop/systemd1 org.freedesktop.DBus.Peer Ping >/dev/null || \
    fail "Cannot reach systemd through the user bus. ${prerequisite}"
[[ "$(loginctl show-user vscode --property=Linger --value)" == yes ]] || \
    fail "The vscode user manager needs lingering to survive SSH disconnects. ${prerequisite}"
manager_state="$(systemctl is-system-running || true)"
case "${manager_state}" in
    running) ;;
    degraded)
        echo 'WARNING: The system manager is degraded; required user manager and bus are available.' >&2
        systemctl --failed --no-pager --plain >&2 || true
        ;;
    *) fail "The system manager is ${manager_state:-unavailable}. ${prerequisite}" ;;
esac

exec 9>"${XDG_RUNTIME_DIR}/work-jatt-t3-service.lock"
flock -n 9 || fail 'Another T3 service setup is running. Wait for it to finish.'
trap 'diagnostics' ERR

if systemctl --user is-active --quiet sh.brew.t3code-cli-main.service; then
    fail 'The retired Homebrew T3 service is still running. Finish active work, then run brew services stop t3code-cli-main and brew uninstall t3code-cli-main before retrying.'
fi

case "$(readlink -f -- "${cli}" 2>/dev/null || true)" in
    */Cellar/t3code-cli-main/*|*/opt/t3code-cli-main/*)
        fail 'The user t3 launcher still points to the retired Homebrew package. Remove that link after stopping its service, then rerun this task.'
        ;;
esac

if [[ ! -x "${cli}" ]]; then
    echo "==> Installing the official T3 ${T3CODE_CHANNEL} CLI"
    installer="$(mktemp "${TMPDIR:-/tmp}/work-jatt-t3-install.XXXXXX")"
    trap 'rm -f -- "${installer}"' EXIT
    curl --fail --silent --show-error --location --output "${installer}" https://t3.codes/install.sh
    T3CODE_INSTALL_BIN_DIR="${HOME}/.local/bin" sh "${installer}"
else
    echo '==> Keeping the installed upstream T3 CLI version'
fi
[[ -x "${cli}" ]] || fail 'The official installer did not provide ~/.local/bin/t3.'

# The native service reads this persistent file rather than the IDE task environment.
python3 - <<'PYENV'
from pathlib import Path
import os
import re

home = Path(os.environ.get("T3CODE_HOME", str(Path.home() / ".t3")))
home.mkdir(parents=True, exist_ok=True)
path = home / "service.env"
contents = path.read_text() if path.exists() else ""
if not re.search(r"^\s*(?:export\s+)?T3CODE_TELEMETRY_ENABLED\s*=", contents, re.M):
    with path.open("a") as output:
        output.write(("\n" if contents and not contents.endswith("\n") else "") + "T3CODE_TELEMETRY_ENABLED=false\n")
    path.chmod(0o600)
PYENV

echo '==> Installing or repairing the upstream systemd user service'
"${cli}" service install
"${cli}" service status

# Readiness and duplicate-server checks belong to upstream; check the actual unit too.
deadline=$((SECONDS + 30))
while (( SECONDS < deadline )); do
    if systemctl --user is-active --quiet "${unit}"; then
        diagnostics
        echo "PASS: ${unit} is active as vscode; upstream service setup completed."
        exit 0
    fi
    sleep 1
done
diagnostics
fail 'The upstream T3 service did not become active within 30 seconds.'
