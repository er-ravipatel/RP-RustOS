"""Create initial proposals once; refuses to overwrite an existing progress register."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROWS = [
('kernel','Kernel and exceptions','Integrate startup and diagnose kernel faults','BSP, HAL, build foundation','Enter kernel; establish exception diagnostics; initialize selected services','Startup banner and deliberate fault report are reproducible','Entry conditions, exception levels, panic policy'),
('mm','Memory management','Allocate memory and isolate address spaces','Board memory map, kernel exception handling','Discover usable memory; allocate pages; create mappings; reclaim ownership','Allocation exhaustion and invalid mappings fail without corrupting owned memory','Physical allocator, address layout, page tables, heap policy'),
('sched','Task scheduling','Run multiple tasks with correct saved execution state','Memory, timer, exception handling','Create task; mark runnable; switch context; wait or exit; reclaim resources','Multiple tasks make progress and preserve stack and register state','Preemption, fairness, task states, multicore scope'),
('fs','Filesystem','Offer consistent file access and eventual persistence','Memory; block driver for persistent backend','Resolve path; check access; operate on file; return result; release handle','Read and write behavior is repeatable; persistent files survive reboot when enabled','Path rules, handle ownership, filesystem format, recovery policy'),
('ipc','Interprocess communication','Exchange data between isolated tasks','Scheduler, memory, syscall ABI','Create endpoint; send or wait; transfer data; wake receiver; close endpoint','Blocking, peer termination, and queue exhaustion have defined outcomes','Message ownership, buffer limits, endpoint permissions'),
('syscall','Syscall boundary and executable loading','Allow controlled requests from user programs','Memory isolation, scheduler, executable loader design','Enter kernel; decode request; validate pointers; dispatch; return structured result','Invalid calls and pointers cannot corrupt kernel state; a user program exits cleanly','Calling convention, executable format, ABI versioning, error codes'),
('hal','Hardware abstraction','Separate portable services from device-specific operations','Kernel service needs and board constraints','Request hardware operation; validate contract; invoke implementation; report result','Service code uses documented contracts with ownership and error rules','Trait boundaries, static or dynamic dispatch, interrupt-safe access'),
('bsp','Pi Zero 2 W board support','Describe board resources and establish boot assumptions','Firmware contract and chosen target','Receive firmware handoff; discover resources; initialize early devices; hand off to kernel','Board setup and resource map support repeatable startup on identified hardware','Firmware inputs, UART choice, addresses, memory discovery'),
('block','Block storage driver','Read and write storage using bounded device requests','BSP, HAL, timing and synchronization','Validate request; submit transfer; await completion; return data or error','Known blocks round-trip correctly; invalid bounds and timeouts return errors','Controller choice, sector size, DMA policy, timeout recovery'),
('console','Console driver','Provide serial output and interactive input','BSP, HAL','Initialize serial device; transmit bytes; receive input; report device errors','Boot text and interactive input work using documented wiring and settings','UART selection, buffering, polling versus interrupts, line endings'),
('gpio','GPIO driver','Control supported pins with explicit ownership','BSP pin map, HAL','Acquire pin; select supported function; read or write; release pin','Selected pin behavior is measured and conflicting ownership is rejected','Pin numbering, permitted functions, electrical setup documentation'),
('timer','Timer driver','Supply timekeeping and timer events','BSP clock information, HAL, interrupts','Read counter; configure deadline; receive interrupt; acknowledge; notify scheduler','Monotonic reads and periodic events pass a documented measurement procedure','Clock source, units, wrap handling, interrupt acknowledgment'),
('init','Init process','Start and supervise the first user environment','User execution, syscall ABI, console','Launch init; prepare environment; start shell; wait for child; handle termination','Init starts in user mode and shell termination follows a documented policy','Startup resources, restart behavior, fatal failure handling'),
('shell','Interactive shell','Parse commands and launch supported programs','Console input, init, syscall ABI, program loading','Read line; parse command; resolve program; launch; wait; display result','Valid commands execute; malformed input and failed launches preserve the prompt','Grammar, built-ins, path lookup, signals and job-control scope'),
('utils','Command-line utilities','Provide a deliberately small useful command set','Shell, filesystem, syscall ABI','Parse arguments; call supported services; emit output; return exit status','Each selected utility has input, output, error, and exit-status examples','Initial command list, argument conventions, shared utility support'),
('crt','C runtime startup','Start and terminate C user programs correctly','Loader, syscall ABI, memory, C toolchain selection','Load image; initialize runtime state; call main; report exit; release process','A minimal C program receives documented startup state and returns an exit code','C ABI, target triple, argument layout, global initialization'),
('libc','C library subset','Implement the C interfaces required by selected programs','C startup, syscall ABI, allocator, filesystem','Application calls supported API; translate to kernel request; return result or error','Selected APIs pass defined success and failure cases; unsupported APIs are listed','Supported functions, errno model, allocation and I/O semantics'),
('micropython','MicroPython integration','Run a bounded interpreter port and examples','Memory, console, filesystem, runtime interface decisions','Start interpreter; configure heap; read script; execute; report exception; clean up','A documented script runs and interpreter exceptions do not corrupt kernel state','Port baseline, garbage collector roots, modules, memory budget'),
('image-builder','Build foundation and image builder','Produce inspectable kernel artifacts and reproducible boot media','Toolchain, linker layout, BSP firmware contract','Validate inputs; build kernel; inspect artifact; assemble image; report output','Fresh checkout produces documented artifacts; board image boots at first-boot gate','Host support, pinned versions, firmware sourcing, image layout'),
('packager','Program and asset packaging','Package programs with compatible metadata and runtime assets','Executable format, filesystem, runtime requirements','Collect artifacts; validate metadata; detect conflicts; assemble package; inspect output','Package contents and compatibility can be inspected; invalid inputs are rejected','Manifest format, ABI identification, versioning, integrity requirements'),
]


def main():
    if (ROOT / 'progress.json').exists():
        raise SystemExit('Baseline already exists; update specifications and progress register directly.')
    target = ROOT / 'features'
    target.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    features = []
    catalog = ['# Feature specification catalog', '', 'All specifications are initial proposals, not reviewed or implemented behavior. Requirement IDs remain stable as details are refined.', '', '| Feature | Goal |', '| --- | --- |']
    for slug, name, goal, deps, flow, acceptance, decisions in ROWS:
        req = slug.upper()
        steps = flow.split('; ')
        lines = ['flowchart TD']
        for i, step in enumerate(steps):
            lines.append(f'  S{i}["{step}"]')
            if i:
                lines.append(f'  S{i-1} --> S{i}')
        lines += ['  S0 -. invalid request or unavailable prerequisite .-> Error["Report failure without partial ownership leaks"]']
        diagram = '\n'.join(lines)
        text = f'''# {name}

**Status:** initial proposal; requirements, analysis, design, and documentation in progress. Review, implementation, and verification have not started.

## Goal and scope

{goal}. Deliver only the behavior required by the current milestone before extending coverage. See the [system architecture](../architecture.md) and [delivery plan](../plan.md).

## Initial requirements

- **{req}-001:** {goal} through an explicitly documented interface.
- **{req}-002:** Define invalid inputs, unavailable resources, and failure results before implementation.
- **{req}-003:** Supply a repeatable procedure demonstrating: {acceptance[0].lower() + acceptance[1:]}.

These requirements need refinement and review; they are not an approved baseline. Specify concrete limits and observable outputs during analysis.

## Analysis and dependencies

Prerequisites: {deps}.

Compare the smallest implementation that satisfies the milestone with more capable alternatives. Record constraints, the selected approach, and deferred behavior. Dependency interfaces must be agreed before integration; a dependency listed here is not implemented.

## Proposed design

Proposed responsibilities follow this order: {flow.lower()}. Before design completion, define interface signatures, input and output types, resource ownership, lifetime, concurrency assumptions, and errors. Keep board assumptions at the hardware boundary.

## Workflow

```mermaid
{diagram}
```

The failure edge is illustrative. Expand it into operation-specific failure and cleanup paths before design approval. Add sequence or lifecycle diagrams when the final interface makes cross-component interactions or state transitions concrete.

## Failure analysis

Identify invalid requests, missing prerequisites, resource exhaustion, and interrupted operations. Define which resources have been acquired at each step, how they are released, and whether the caller retries, receives an error, or triggers a kernel diagnostic. Kernel-fatal faults need an explicit panic policy rather than an assumption of recovery.

## Acceptance and verification

- {acceptance}.
- Exercise invalid input and unavailable-resource behavior defined by {req}-002.
- Record toolchain, target or board, exact procedure, expected output, actual result, and evidence reference.

No verification has run. Distinguish host tests, cross-compilation checks, and hardware evidence; one does not substitute automatically for another.

## Open decisions

{decisions}. Decide and document alternatives and rationale before claiming design completion.

## Review record

Pending. Record reviewer, date, specification revision, findings, dispositions, and outcome here. No approval is implied by this proposal.

## Next action

Refine {req}-001 through {req}-003 into reviewable behavior and limits; resolve the milestone-critical open decisions.
'''
        (target / f'{slug}.md').write_text(text, encoding='utf-8')
        catalog.append(f'| [{name}]({slug}.md) | {goal} |')
        path = f'docs/features/{slug}.md'
        stages = {}
        for stage in ('requirements', 'analysis', 'design', 'review', 'documentation', 'implementation', 'verification'):
            underway = stage in ('requirements', 'analysis', 'design', 'documentation')
            stages[stage] = {'status': 'in_progress' if underway else 'not_started', 'evidence': [path + ' (initial proposal; not approved)'] if underway else []}
        features.append({'id': req, 'name': name, 'spec': path, 'updated_at': timestamp, 'stages': stages, 'blockers': [], 'next_action': f'Refine {req}-001 through {req}-003 and resolve: {decisions}.'})
    (target / 'README.md').write_text('\n'.join(catalog) + '\n', encoding='utf-8')
    (ROOT / 'progress.json').write_text(json.dumps({'updated_at': timestamp, 'features': features}, indent=2) + '\n', encoding='utf-8')
    print(f'Created {len(features)} initial feature specifications and progress records.')


if __name__ == '__main__':
    main()
