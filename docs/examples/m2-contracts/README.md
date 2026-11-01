# Synthetic M2 input fixtures

These JSON records exercise parsed-data contracts only. They are not installed profiles, downloadable asset inventories, licence determinations, or usable build inputs. The all-ones commit, all-zero asset hashes and one-byte lengths are deliberate placeholders. Do not download their URLs.

[profile.json](profile.json) binds the exact bytes of [firmware-lock.json](firmware-lock.json). All non-licence assets use a synthetic licence relationship to exercise validation; this does not establish the real DTB's licence. The actual research candidate remains [separate](../../evidence/m2-firmware-candidate.json).

Generate the schema with `python tools/m2_input_contracts.py` from the repository root; run `python tools/test_m2_input_contracts.py -v` with the optional design dependencies installed. These scripts do not build or boot RustOS.
