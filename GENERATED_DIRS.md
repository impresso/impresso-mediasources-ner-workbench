# Generated Directories

Project-generated local directory roots that should not be committed use the `*.d/` suffix.

This keeps workbench state easy to find from inside the repository while making it clear that these roots are local artifacts, not source files.

Default generated roots:

- `staging.d/`: staged datasets and generated state reports
- `hf.d/`: Hugging Face cache (`HF_HOME`)
- `mlm.d/`: downloaded, sampled, and tokenized MLM data
- `models.d/`: local model checkpoints and evaluation outputs
- `cache.d/`: sampler/runtime cache files
- `release-work.d/`: private intermediate release assembly workspace
- `audit.d/`: local full-trace audit/provenance storage

Tracked source directories such as `data/`, `docs/`, `hf_dataset/`, `hf_model/`, and `resources/` keep their existing names. Some subpaths below `data/` are ignored because they are local curation artifacts, but the directory root itself is part of the workbench structure.

Committed dataset prerelease snapshots live under `data/prereleases/<dataset-version>/`, and committed final release snapshots live under `data/releases/<dataset-version>/`. They do not use the `*.d/` suffix because they are shared source artifacts, not generated local roots. See `docs/data_lifecycle.md` and `RELEASE_MANAGEMENT_PLAN.md`.

Standard tool/runtime directories that are not controlled by this project, such as `.venv/`, `.pytest_cache/`, and `__pycache__/`, remain ignored exceptions.

Older generated roots such as `.hf/`, `.cache/`, `data/mlm/`, and `models/` are still ignored for compatibility with earlier local checkouts, but new defaults and documentation should use the `*.d/` names.
