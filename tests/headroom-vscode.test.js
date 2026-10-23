const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const extension = path.join(__dirname, '../.vscode/headroom/extension.js');

function fixture({ saved, input = 'new-fixture-token', remote = true, trusted = true, fails = false, storeFails = false } = {}) {
    const calls = { prompts: [], stores: [], runs: [], messages: [], commands: {} };
    const vscode = {
        env: { remoteName: remote ? 'ssh-remote' : undefined },
        workspace: { isTrusted: trusted, workspaceFolders: [{ uri: { fsPath: '/workspaces/work jatt' } }] },
        commands: { registerCommand(name, run) { calls.commands[name] = run; return { dispose() {} }; } },
        window: {
            async showInputBox(options) { calls.prompts.push(options); return input ?? undefined; },
            showInformationMessage(message) { calls.messages.push(message); },
            showErrorMessage(message) { calls.messages.push(message); },
        },
    };
    const context = {
        subscriptions: [],
        secrets: {
            async get() { return saved; },
            async store(key, value) {
                if (storeFails) throw new Error('secret storage unavailable');
                calls.stores.push({ key, value }); saved = value;
            },
        },
    };
    function spawn(binary, args, options) {
        const child = new EventEmitter();
        child.stdin = new EventEmitter();
        child.stdin.end = value => {
            calls.runs.push({ binary, args, options, input: value });
            queueMicrotask(() => child.emit('close', fails ? 1 : 0));
        };
        return child;
    }
    const module = { exports: {} };
    vm.runInNewContext(fs.readFileSync(extension, 'utf8'), {
        module, exports: module.exports,
        process: { env: { HEADROOM_BASE_URL: 'http://proxy.test/v1' } },
        require(name) {
            if (name === 'vscode') return vscode;
            if (name === 'node:child_process') return { spawn };
            if (name === 'node:fs') return { existsSync: () => true };
            return require(name);
        },
    }, { filename: extension });
    return { calls, context, activate: () => module.exports.activate(context) };
}

test('first connection prompts with masking, stores in VS Code Secrets and sends only stdin', async () => {
    const { calls, activate } = fixture();
    await activate();
    assert.equal(calls.prompts.length, 1);
    assert.equal(calls.prompts[0].password, true);
    assert.equal(calls.stores[0].value, 'new-fixture-token');
    assert.ok(calls.stores[0].key.includes('http://proxy.test/v1'));
    assert.equal(calls.runs[0].input, 'new-fixture-token\n');
    assert.equal(calls.runs[0].binary, '/bin/bash');
    assert.equal(calls.runs[0].args[0], '/workspaces/work jatt/.devcontainer/scripts/configure-headroom.sh');
    assert.equal(calls.runs[0].args.includes('new-fixture-token'), false);
    assert.equal(JSON.stringify(calls.runs[0].options).includes('new-fixture-token'), false);
    assert.equal(calls.messages.join('').includes('new-fixture-token'), false);
});

test('saved secret is reapplied on connection without another prompt', async () => {
    const { calls, activate } = fixture({ saved: 'saved-fixture-token' });
    await activate();
    assert.equal(calls.prompts.length, 0);
    assert.equal(calls.runs[0].input, 'saved-fixture-token\n');
});

test('update command prompts again and replaces the saved token', async () => {
    const { calls, activate } = fixture({ saved: 'old-fixture-token' });
    await activate();
    await calls.commands['workJatt.updateHeadroomToken']();
    assert.equal(calls.prompts.length, 1);
    assert.equal(calls.stores.at(-1).value, 'new-fixture-token');
    assert.equal(calls.runs.at(-1).input, 'new-fixture-token\n');
});

test('cancel does not overwrite secrets or invoke configuration', async () => {
    const { calls, activate } = fixture({ input: null });
    await activate();
    assert.equal(calls.stores.length, 0);
    assert.equal(calls.runs.length, 0);
});

test('cancelled rotation keeps the saved token and existing client configuration', async () => {
    const { calls, activate } = fixture({ saved: 'old-fixture-token', input: null });
    await activate();
    await calls.commands['workJatt.updateHeadroomToken']();
    assert.equal(calls.runs.length, 1);
    assert.equal(calls.runs[0].input, 'old-fixture-token\n');
    assert.equal(calls.stores.length, 0);
});

test('unavailable VS Code secret storage does not silently write the token elsewhere', async () => {
    const { calls, activate } = fixture({ storeFails: true });
    await activate();
    assert.equal(calls.runs.length, 0);
    assert.ok(calls.messages.join('').includes('Could not configure Headroom'));
    assert.equal(calls.messages.join('').includes('new-fixture-token'), false);
});

test('local and untrusted workspaces never receive the token', async () => {
    for (const options of [{ remote: false }, { trusted: false }]) {
        const { calls, activate } = fixture(options);
        await activate();
        assert.equal(calls.prompts.length, 0);
        assert.equal(calls.runs.length, 0);
    }
});

test('configuration failure reports a safe error and never claims success', async () => {
    const { calls, activate } = fixture({ fails: true });
    await activate();
    assert.ok(calls.messages.join('').includes('Update Proxy Token'));
    assert.equal(calls.messages.join('').includes('saved and applied'), false);
    assert.equal(calls.messages.join('').includes('new-fixture-token'), false);
});

test('input validation rejects empty values, multiline headers and OMP commands', async () => {
    const { calls, activate } = fixture({ input: null });
    await activate();
    const validate = calls.prompts[0].validateInput;
    for (const value of ['', '  ', 'bad\nheader', 'bad\rheader', '!command']) {
        assert.ok(validate(value));
    }
    assert.equal(validate('valid-fixture-token'), undefined);
});
