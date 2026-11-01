# M2 hardware-session and completed-index checks

2026-11-01. Design evidence only. [Generated schema](schemas/m2-sessions.schema.json), [semantic checker/request parser](../tools/m2_session_contracts.py), and [synthetic cases](../tools/test_m2_session_contracts.py) do not open serial devices or enable Pi commands in the assembler.

The session names its identity, manifest hash, board, adapter, Windows COM port, fixed serial settings and both image IDs. Its contents cannot supply commands, timeout overrides or a new baud rate. Hardware reports bind the session ID and setup, exact manifest and image identities. Actual fresh-capture checks remain the runner's responsibility.

The proposed request parser defaults Pi verification to image inspection. Hardware requires both an explicit method and session path; image inspection forbids a session path. Unknown, duplicate and abbreviated options fail. This parser exists only to check the proposed syntax; the Rust executable does not support these options yet.

The schema-2 completed-report index carries method, local absolute input/report paths, both hashes and the CLI outcome containing the exact bound report. It permits a failed CLI result to retain a passed guest report only with an error diagnostic; it cannot promote a failed report to success. M1 schema-1 indexes remain unchanged.

Two review passes: structural/positive and syntax cases first; method/session/manifest mismatches, changed report bytes, altered CLI result copies, unsafe paths and false success second. All 11 test methods pass. Together with the input and output suites there are 40 M2 synthetic contract tests. These are not hardware or build executions and are never inserted into the runtime run list.

Limits and remaining work: this index contract covers completed verification reports, not build outcomes or preflight/report-publication recovery records. Those failure envelopes need definition before the runtime publisher/importer is extended. Paths here are lexical checks, not stable opened-file identity proof. Session fields and operator declarations do not authenticate a board or prevent fabricated logs. Runtime must bind real files/logs and trusted recipes, preserve exact input bytes, and implement bounded serial/process ownership. The source/licence package, final asset lock and hardware inventory also remain open.

Reproduce with design dependencies available:

```text
python tools/m2_output_contracts.py
python tools/m2_session_contracts.py
python tools/test_m2_session_contracts.py -v
```
