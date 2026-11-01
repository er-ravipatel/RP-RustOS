---
description: Windows host build, cancellation-test and dashboard-listener constraints
applyTo: "{tools/**,docs/dashboard/**}"
---

Use the project's `DashboardServer` class for localhost dashboard servers: Windows `SO_REUSEADDR` can allow multiple live listeners on one port, while `SO_EXCLUSIVEADDRUSE` rejects the duplicate; before refreshing port 8765, identify every listener by executable and this project's server command, then stop only those confirmed project processes. Finish Cargo compilation before running CLI acceptance on Windows, because an executing `rustos.exe` cannot be replaced by a concurrent Cargo build. For real console cancellation tests, reuse the private hidden-console helper and its console-client ownership check rather than signalling the user's terminal. See the [M1 acceptance record](../../docs/m1-acceptance.md) for the procedures and limits; these are automatic host-workflow instructions rather than a separate opt-in skill.

After a server refresh, compare actual HTTP run classifications with `load_indexes()` from the current source before claiming the latest importer is active; a correct PID and current planning JSON alone do not establish that its Python code was reloaded.
