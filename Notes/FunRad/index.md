---
title: FunRad — Fun Radar Project
---

Design notes, simulations and measurements for FunRad. The list below follows the vault's folder structure and includes every page.

## Pages

- [[FunRad Rev.A Specification]]
- [[Implementation Readiness Suggestions]]
- [[Simulation Closure Checklist]]
- **Frontend/**
  - [[Frontend/Frontend Description|Frontend Description]]
  - [[Frontend/RF Architecture|RF Architecture]]
  - [[Frontend/RF Calculations|RF Calculations]]
  - [[Frontend/FunRad Stages Calculations.ods|Calculation workbook]]
  - **Coupler/**
    - [[Frontend/Coupler/TX Coupler EM Method|TX Coupler EM Method]]
    - [[Frontend/Coupler/Quasi-static 2-D Solver|Quasi-static 2-D Solver]]
    - [[Frontend/Coupler/Coupler Simulation Catalogue|Coupler Simulation Catalogue]]
  - **Coupon/**
    - [[Frontend/Coupon/index|PCB coupon overview]]
    - [[Frontend/Coupon/01_PCB_ONLY_RESULTS|01 — PCB-only model]]
    - [[Frontend/Coupon/02_MODAL_PORT_CHECK|02 — PCB modal-port control]]
    - [[Frontend/Coupon/03_CONNECTOR_GEOMETRY|03 — Simplified connector geometry]]
    - [[Frontend/Coupon/04_COAX_RESULTS|04 — Connector-inclusive control]]
    - [[Frontend/Coupon/05_L2_CUTOUT_RESULTS|05 — Initial L2 cutouts]]
    - [[Frontend/Coupon/06_L2_CUTOUT_FLATNESS_SWEEP|06 — Cutout geometry search]]
    - [[Frontend/Coupon/07_BROADBAND_CHECK|07 — Broadband verification]]
    - [[Frontend/Coupon/08_MESH_REFINEMENT|08 — Mesh refinement]]
    - [[Frontend/Coupon/09_L3_CUTOUT_RESULTS|09 — L3 cutout experiment]]
    - [[Frontend/Coupon/10_DIELECTRIC_SENSITIVITY|10 — Dielectric sensitivity]]
- **Antenna/**
  - [[Antenna/Antenna Rev.A|Antenna Rev.A]]
  - [[Antenna/Antenna Rev.A S11 parameters|Antenna Rev.A S11 parameters]]
  - [[Antenna/Antenna Rev.A Directivity|Antenna Rev.A Directivity]]
- **Generated/**
  - [[Generated/FunRad Rev.A Results|FunRad Rev.A Results]]
- **Excalidraw/**
  - [[Excalidraw/FunRadBlockDiagram.excalidraw|FunRad block diagram]]
  - [[Excalidraw/TxPathWithDAC.excalidraw|TX path with DAC]]
  - [[Excalidraw/TxPathWithPLL.excalidraw|TX path with PLL]]

## Assets

- `images/` — shared plots and illustrations.
- `Claude outputs/` — supporting drawings and screenshots.
