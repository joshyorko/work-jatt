const vscode = require('vscode');
const { spawn } = require('node:child_process');
const { existsSync } = require('node:fs');
const path = require('node:path');

function validateToken(value) {
    if (!value.trim()) return 'Enter the Headroom proxy token.';
    if (/[\r\n]/.test(value) || value.startsWith('!')) return 'Enter a single token, without line breaks or a leading !.';
    return undefined;
}

function applyToken(script, token) {
    return new Promise((resolve, reject) => {
        // The secret goes over stdin, never command arguments, terminal history,
        // workspace settings, or an output channel. The helper writes private configs.
        const child = spawn('/bin/bash', [script, '--prompt'], {
            stdio: ['pipe', 'ignore', 'ignore'],
            timeout: 30000,
        });
        child.once('error', () => reject(new Error('Headroom setup failed.')));
        child.once('close', code => code === 0 ? resolve() : reject(new Error('Headroom setup failed.')));
        child.stdin.on('error', () => {}); // An early child exit is reported by close/error.
        child.stdin.end(`${token}\n`);
    });
}

async function activate(context) {
    let pending;
    async function configure(prompt = false) {
        if (pending) return pending;
        pending = (async () => {
            // This extension runs in the remote extension host. Never configure
            // a workstation merely because it opened a checkout of this repo.
            if (!vscode.workspace.isTrusted || !vscode.env.remoteName) return;
            const folder = vscode.workspace.workspaceFolders?.find(candidate =>
                existsSync(path.join(candidate.uri.fsPath, '.devcontainer/scripts/configure-headroom.sh')));
            const endpoint = process.env.HEADROOM_BASE_URL;
            if (!folder || !endpoint) return;
            const key = `headroom.proxyToken:${endpoint}`;
            try {
                let token = prompt ? undefined : await context.secrets.get(key);
                const prompted = !token;
                if (prompted) {
                    token = await vscode.window.showInputBox({
                        title: 'Headroom Proxy Token',
                        prompt: `Enter the proxy token for ${endpoint}. VS Code will save it securely and configure this container.`,
                        password: true,
                        ignoreFocusOut: true,
                        validateInput: validateToken,
                    });
                    if (token === undefined) return;
                    if (validateToken(token)) return;
                    await context.secrets.store(key, token);
                }
                await applyToken(path.join(folder.uri.fsPath, '.devcontainer/scripts/configure-headroom.sh'), token);
                if (prompted) {
                    vscode.window.showInformationMessage('Headroom token saved and applied. Restart Codex and Review sessions to use it.');
                }
            } catch {
                // Never forward subprocess output or secret-store errors to UI/logs.
                vscode.window.showErrorMessage('Could not configure Headroom. Run Headroom: Update Proxy Token to try again.');
            }
        })();
        try { await pending; } finally { pending = undefined; }
    }
    context.subscriptions.push(vscode.commands.registerCommand('workJatt.updateHeadroomToken', () => configure(true)));
    await configure();
}

module.exports = { activate };
