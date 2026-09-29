# MemoryD + Secure MCP Tunnel workstation integration

Status: tracking design for implementation.

GitHub Issues are currently disabled on `joshyorko/work-jatt`, so this branch/PR carries the workstation tracking packet until Issues are enabled.

## Outcome

Turn Work-JATT into a reproducible agent workstation that includes MemoryD and OpenAI Secure MCP Tunnel as first-class optional services.

A fresh Work-JATT environment should be able to run Codex, Review/OMP, Claude, Josh Room, or another agent while sharing a predictable local MemoryD surface.

The workstation must also treat its Kubernetes/devcontainer storage as disposable: persistence across an ordinary container restart/rebuild is useful, but it is **not** a guarantee that memory survives workspace/PVC destruction.

## Dependencies

- joshyorko/codex-memoryd#245 — Homebrew/release distribution
- joshyorko/codex-memoryd#246 — safe satellite bootstrap/drain semantics
- joshyorko/codex-memoryd#247 — first-class OpenAI Secure MCP Tunnel integration
- joshyorko/codex-memoryd#233 — lineage-safe live observation writeback
- joshyorko/codex-memoryd#241 — native OMP integration

## Architecture boundary

Work-JATT owns workstation/environment UX.

It must not implement its own:

- MemoryD storage semantics;
- bundle parser/import rules;
- lineage/confidence policy;
- tunnel protocol;
- evidence ranking;
- multi-instance replication model.

It consumes supported CLIs and exposes a small ergonomic workstation surface.

```text
Work-JATT
├── Review / OMP
├── Codex
├── Claude / other agents
├── Josh Room
├── codex-memoryd
├── tunnel-client
├── just
└── environment/config glue
```

## Install

Add a dedicated memory/tool setup script:

```text
.devcontainer/scripts/install-memory-tools.sh
```

Install through supported distributions:

```bash
brew install just
brew install joshyorko/tools/codex-memoryd
brew install openai/tools/tunnel-client
```

Do not build MemoryD from source as the normal Work-JATT path after MemoryD #245 lands.

Do not vendor or rebuild tunnel-client.

Until #245 is published, any source-build fallback must be explicitly development-only and removed from the normal path once the release exists.

## Runtime layout

Use the persistent Work-JATT home for local runtime state:

```text
~/.codex-memoryd/
~/.config/tunnel-client/
~/.config/work-jatt/
```

This protects ordinary restart/rebuild flows because Work-JATT already mounts `/home/vscode` into a persistent devcontainer volume.

Documentation must explicitly state that destroying the backing Kubernetes workspace/PVC can still destroy this local state.

The local Work-JATT MemoryD must not be called canonical merely because its home volume survives an ordinary container rebuild.

## Memory modes

Support an explicit workstation mode:

```text
WORK_JATT_MEMORY_MODE=off|local|satellite|direct
```

- `off`: no MemoryD lifecycle management.
- `local`: local MemoryD only; operator accepts local durability.
- `satellite`: local MemoryD plus a configured canonical handoff target.
- `direct`: agents target a persistent canonical MemoryD rather than owning meaningful local memory state.

Do not infer `canonical` from volume persistence.

## Just UX

Add a root `justfile` with a small stable surface.

### Memory

```bash
just memory-init
just memory-up
just memory-status
just memory-logs
just memory-restart
just memory-down
just memory-doctor
```

### Satellite

```bash
just memory-bootstrap
just memory-drain
just memory-drain-status
```

### Tunnel

```bash
just tunnel-setup
just tunnel-up
just tunnel-status
just tunnel-ui
just tunnel-down
```

### Client setup/status

Thin wrappers may include:

```bash
just memory-codex-setup
just memory-codex-status
just memory-omp-status
```

The Justfile delegates semantics to `codex-memoryd` and `tunnel-client`.

Work-JATT must not parse MemoryD SQLite or reimplement bundle/tunnel behavior in shell.

## Startup behavior

### postCreate

- install `just`, MemoryD, and tunnel-client;
- initialize MemoryD when the selected mode requires local state;
- do not require OpenAI tunnel credentials for workstation creation;
- preserve existing Review/Josh Room bootstrap behavior.

### postStart

- ensure local MemoryD is healthy when enabled;
- do not automatically establish the OpenAI tunnel unless explicitly configured;
- do not make an optional MemoryD/tunnel failure prevent the base workstation from starting unless marked required.

Optional:

```text
WORK_JATT_TUNNEL_ENABLED=1
```

may opt a workstation into automatic tunnel startup once a valid profile and secret reference exist.

## Secrets

Never put OpenAI keys, canonical MemoryD credentials, or private bundle material in git or `devcontainer.json`.

Use persistent-home-owned config, environment injection, or mounted secret files.

Possible layout:

```text
~/.config/work-jatt/tunnel.env
~/.config/work-jatt/memory.env
```

Generated secret files are owner-readable only.

Prefer `env:` / `file:` references supported by the underlying tools.

Status/runtime checks never print raw secrets.

## Satellite destroy safety

`just memory-drain` is a real safety operation, not an alias for `codex-memoryd down`.

Once MemoryD #246 is available it should:

1. ask MemoryD for current satellite/drain status;
2. generate/preview the required handoff;
3. invoke the configured transfer/apply path;
4. return the canonical destination receipt to the satellite;
5. rerun satellite status;
6. print `SAFE TO DESTROY` only when MemoryD itself reports that state.

If unresolved conflicts, pending continuity state, failed transfer, stale receipt/generation, or local changes remain:

- exit non-zero;
- print the blocker;
- do not claim safe destruction.

A successfully written/uploaded bundle is not proof that the canonical destination accepted it.

## Initial transfer boundary

Do not invent a new synchronization protocol in Work-JATT.

For the first satellite slice, use MemoryD #225/#226 + #246 semantics:

```text
local satellite
  → portable bundle
  → configured secure transfer step
  → destination preview/apply
  → destination receipt
  → satellite acknowledge
```

A future online MemoryD transport can replace artifact movement without changing the workstation UX or destruction-safety contract.

## Secure MCP Tunnel

Consume the official OpenAI client:

```bash
brew install openai/tools/tunnel-client
```

Use MemoryD #247's generated/profile integration when available.

Tunnel startup is opt-in because it requires external credentials and establishes connectivity to OpenAI.

```text
ChatGPT / Work / hosted Codex
             ↓
     Secure MCP Tunnel
             ↓
       tunnel-client
             ↓
  Work-JATT MemoryD stdio
```

Do not expose MemoryD publicly merely to support ChatGPT.

## Client-specific paths

Use the best integration per client:

```text
Codex        → native/direct MemoryD provider where configured
Review/OMP   → native MemoryBackend from MemoryD #241 when available
Claude/etc.  → MCP/HTTP as appropriate
ChatGPT      → MCP through Secure MCP Tunnel
```

Do not force every client through Tunnel or MCP just because Work-JATT includes them.

## Runtime check

Extend the existing runtime check to report:

- `just`;
- `codex-memoryd` binary/version;
- selected Work-JATT memory mode;
- local MemoryD health when enabled;
- canonical target configured/not-configured without secret output;
- `tunnel-client` binary/version;
- tunnel configured/running/healthy/ready/not-configured state;
- existing Review runtime status.

A broken optional tunnel must not make the whole workstation unusable unless explicitly required.

## Documentation

Update README to make the environment model obvious:

```text
Work-JATT = disposable/reproducible workstation
MemoryD local = fast local memory
MemoryD canonical = persistent continuity target
Secure MCP Tunnel = optional OpenAI-hosted bridge
```

Document the difference between:

- routine devcontainer rebuild;
- workspace/PVC destruction;
- local MemoryD;
- satellite MemoryD;
- direct canonical mode.

## Acceptance

- [ ] Fresh devcontainer installs all tools from supported distributions.
- [ ] Routine rebuilds preserve local MemoryD state through the existing home volume.
- [ ] Docs do not call that volume canonical/durable against workspace deletion.
- [ ] MemoryD lifecycle is one-command/Just driven.
- [ ] Tunnel lifecycle is one-command/Just driven.
- [ ] No raw credentials enter the repo.
- [ ] `satellite` mode can bootstrap and drain once MemoryD #246 lands.
- [ ] Destroy safety comes from a MemoryD receipt/status, not shell guesswork.
- [ ] Review/Codex/Claude remain usable if MemoryD is down.
- [ ] Tunnel is opt-in.
- [ ] Existing Review/Josh Room setup remains green.
- [ ] Runtime check reports MemoryD/tunnel state without leaking credentials.
- [ ] Work-JATT contains no duplicate MemoryD policy/sync implementation.

## Non-goals

- No new MemoryD storage semantics in Work-JATT.
- No tunnel protocol implementation.
- No generic synchronization/database replication system.
- No requirement that every agent use the same adapter.
- No replacement for MemoryD #241's native OMP MemoryBackend.
- No hosted multi-user MemoryD service.
- No automatic deletion of local MemoryD after drain.
- No automatic `SAFE TO DESTROY` based only on process/container state.

## Definition of done

A fresh Work-JATT behaves like an agent Swiss-Army workstation: MemoryD and tunnel-client are installable and easy to operate, local agents can use the appropriate memory adapter, hosted ChatGPT can optionally reach private local MemoryD through Secure MCP Tunnel, and a satellite workstation can prove that useful memory reached a canonical destination before its Kubernetes workspace/PVC is destroyed.
