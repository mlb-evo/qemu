# Local FPK1 tools

This tooling remains local and is not intended for upstream QEMU contribution.

- `ui/`: Qt windows and controls. Run `python3 tools/fpk1/view_frames.py` from
  the repository root, or `PYTHONPATH=tools/fpk1 python3 -m ui`.
- `hmi/`: runtime inputs, coding, wire metadata, presets, BAP sessions and
  scanout capture. It has no Qt or research dependency. Native window embedding
  belongs to `ui/`.
- `kss_peer.py` and `gss_ipc_frames.py`: shared KSS transport and framing.
- `tests/`: runtime and UI regression tests.
- `research/hmi/`: firmware inspectors, oracle checks and experimental runs.
  Research scripts can import `hmi/` and `ui/`; those packages must never
  import research scripts or test helpers.

Run the HMI/UI tests with:

```sh
PYTHONPATH=tools/fpk1 QT_QPA_PLATFORM=offscreen python3 -B -m unittest discover -s tools/fpk1/tests
```

`test_ui_dependencies.py` also starts the interface and exercises its input
runtime in a fresh process with research and analysis imports blocked.

Generated/private artifacts belong in `build_fpk1/research-artifacts/`;
VM run logs may remain in `build_fpk1/runs/`.
