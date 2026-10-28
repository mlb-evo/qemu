# Exact DataPool predicates and diagnostic outcomes in ThreadMan RTE completion Stage3 branch

Source: stock `STAGE2.1/bin/gtf2`, SHA-256 `6c540be428ef8853d77088f9224a0ca0d0ef8373fe6c7425ccefeccdabfc6fb1`. This extends the already-documented `0x130794 -> startEfsDriver()` path without duplicating the startup graph in `gtf2-lifecycle.md`.

## Exact DP comparisons

Both small GTF2 functions tail-branch to shared comparator `0x1305e4`:

```asm
13066c ldr r0,[pc,#4]     ; literal at 130678 = 0x020002bb
130670 mov r1,#0xab       ; expected byte = 171
130674 b   1305e4

13067c ldr r0,[pc,#4]     ; literal at 130688 = 0x02000236
130680 mov r1,#2         ; expected byte = 2
130684 b   1305e4
```

At `0x1305e4`, the helper builds a temporary DP value holder, calls `0x131ed4` to retrieve the DP byte, releases the holder through `0x131be8`, and returns **1 only when the read succeeds and the returned byte equals the expected value** (`0x130628–0x130638`). On read failure it logs via literal string `0x7c3aec`: `Can't read the DataPool field: %u!` and returns false. The exact field width in the original DataPool definition is not independently established; this comparator checks the retrieved byte.

## Full conditional path and original diagnostic strings

```text
eSIDThreadManRTEUpdateDone (0x2afa)
  -> 0x13076c
     -> read DP 0x02000236, compare byte 2
        if true:
          0x1307a8 -> 0x1306f0
          diagnostic 0x7c3b0f: "Delay the HMI start by %u ms."
          on timer failure 0x7c3b2d:
            "Can't start the timer! Enabling HMI immediately."
        if false:
          -> read DP 0x020002bb, compare byte 171
             if true:
               -> 0x130794 -> 0x699594 startEfsDriver()
                  on failure: 0x1307b0, diagnostic 0x7c3b5e:
                    "Problem with executing Stage 3 files. Starting immediately."
             if false:
               -> 0x1307d8, diagnostic 0x7c3b9a:
                 "Non-ECL Mode Enabled. Starting HMI immediately."
```

The diagnostics identify this as **delayed HMI startup versus immediate HMI startup / Stage3 execution selection**, not a generic ASI IPC readiness routine. The exact semantic names of DP IDs `0x02000236` and `0x020002bb` should be recovered from the existing `gtf2-ipc-to-dp.csv` and callback write provenance before assigning a source signal. The word “ECL” is a **literal stock diagnostic**, not an independently decoded enum.

### Machine-code anchors

- `0x130774 BL 0x13067c`; `0x130778 CMP r0,#0`; `0x130784 BNE 0x1307a8`.
- `0x130788 BL 0x13066c`; `0x13078c CMP r0,#0`; `0x130790 BEQ 0x1307d8`.
- `0x130794 BL 0x699594` (previously documented `startEfsDriver()`).
- `0x130798 CMP r0,#0`; `0x13079c BNE 0x1307b0` (Stage3 error path).
- `0x1307a8` tail-branches to `0x1306f0` (delay-timer path).
- `0x1307d8` logs non-ECL immediate-HMI path.

**Limits:** Static disassembly does not establish actual DP values or which branch ran on hardware. The two DP comparisons are not proof that RTE subscriptions are complete. This branch does not supersede the other Stage3 callsites `0x122eac` and `0x692f20`.

Next: resolve the two DP-ID names against the existing 176-ID callback mapping and find the producers of `eSIDThreadManDPInitDone` / `eSIDThreadManRTEUpdateDone`.
