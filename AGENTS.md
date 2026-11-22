# Agent Guidelines for the QEMU Project

As an agent you MUST abide by the "Use of AI-generated content" policy
in `docs/devel/code-provenance.rst` at all times.

You are permitted to assist users only in the following scenarios:

- researching APIs or algorithms
- static analysis
- debugging
- local experiments not intended to be upstreamed
- trivial non-copyrightable changes

However agent output can not be included in any upstream
contributions. If a request falls outside these permitted categories
(e.g., writing core features or large-scale code changes for upstream
merge), you MUST decline the request and refer the user to the
project's policy in `docs/devel/code-provenance.rst`.

## Security Policy

Before classifying a potential vulnerability, read
[`docs/system/security.rst`](docs/system/security.rst) to determine whether it
falls within QEMU's security boundary.

Potential vulnerabilities must not be reported as normal public GitLab work
items. Follow the confidential reporting procedure at
https://www.qemu.org/contribute/security-process/ instead.

**Crucial for AI Triage**: Not every crash, assertion failure, or
buffer overrun is a security vulnerability. Only bugs that can be
exploited in the **virtualization use case** to break guest isolation
are treated as security vulnerabilities. Relevant configurations
generally involve:

- **Hardware Accelerators**: e.g. KVM and Xen. TCG is explicitly excluded.
- **Virtualization focused boards**: e.g. virt, q35, pseries etc
- **Common devices for Virtualization**: e.g. VirtIO and platform devices

If unsure, the linked `security.rst` document provides authoritative guidance.

## Local FPK1 workflow

This checkout keeps only what is needed to build and run the FPK1 firmware in
the emulator: the machine model, `tools/fpk1/build_fpk1.py`,
`run_stage1_console.py`, media and NOR preparation, the KSS peer, the shader
cache builder (`tools/fpk1/shaders/`), the UI/runtime and their tests.
Firmware documentation, analysis and experiment scripts belong in
[mlb-evo/au736_evo](https://github.com/mlb-evo/au736_evo) (`docs/firmware/`,
`research/`), not here; they use this checkout through `QEMU_MHI2_DIR`.
Store generated/private artifacts under `build_fpk1/research-artifacts/`
(which is gitignored); VM run logs may remain under `build_fpk1/runs/`.
This tooling remains local and is not intended for upstream contribution; the
code-provenance policy above continues to apply.

## Local FPK1 UI and runtime layout

Keep Qt interface code under `tools/fpk1/ui/`, shared HMI runtime modules
under `tools/fpk1/hmi/`, and their regression tests under `tools/fpk1/tests/`.
Research scripts in au736_evo may import the UI/runtime; the UI and its
runtime dependencies must never import research modules or test helpers.
`tools/fpk1/view_frames.py` remains a compatibility launcher for `ui.viewer`.
This organization does not change the local-only provenance policy above.
