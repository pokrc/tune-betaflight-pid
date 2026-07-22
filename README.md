# POK_RC Betaflight PID Tuning Skill

This repository contains a Codex skill that accepts Betaflight Blackbox `.bbl` logs and produces an evidence-based PID/filter CLI candidate.

## Install

Copy the `tune-betaflight-pid` directory into your Codex skills directory, then invoke it with:

```text
Use $tune-betaflight-pid to analyze this Betaflight .bbl and produce a staged CLI.
```

The analyzer needs Python with NumPy and an external `blackbox_decode` executable. For a decoded CSV, the decoder is not needed.

## License and attribution

Licensed under [PolyForm Noncommercial 1.0.0](LICENSE.md). Commercial use is prohibited without separate written permission. Redistributed copies and generated share-mode outputs must retain the notice in [NOTICE.md](NOTICE.md). The distributed skill has `attribution.json` set to `emit_notice: true`.

This project is independent of Betaflight and Blackbox Tools; see the bundled references for tuning safety gates.
