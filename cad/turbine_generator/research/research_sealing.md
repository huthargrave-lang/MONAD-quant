# Sealing / bearing / enclosure / hardware research — small submerged turbine-generator prototype

Date: 2026-10-31. Scope: continuous freshwater immersion, 0.3–2 m depth (0.03–0.2 bar gauge), 0–25 °C, silty river
water. Rotor 8 in, 300–650 rpm, torque 0.18–0.72 N·m, thrust 11–46 N (70 N flood), radial < 20 N. Generator ~49 mm Ø x 29 mm
gimbal motor in a dry cartridge; 316 shaft Ø8 or Ø10 mm through a rotary seal (or magnetic coupling). 3-core cable exit.

Tagging: **verified (URL)** = figure read on the cited page/snippet; **typical/assumed** = engineering estimate or
standard-handbook value not re-read online in this session. Prices are retailer list prices at the time of capture, USD unless
stated. Note on method: direct page fetches to bluerobotics.com, robotshop.com, parker.com, skf.com, mcmaster.com, rs-online,
vxb.com, scribd.com etc. were refused by this session's egress proxy; everything below comes from search-engine snippets of
those pages, so dimensions should be re-checked on the live page before cutting metal.

---

## 1. Watertight enclosures for the generator cartridge

### 1.1 Blue Robotics 2" Series (Locking / "flange cap" generation)

| Item | Value | Status |
|---|---|---|
| Tube ID, aluminium 6061-T6 (Type III anodised) | 50.0 ± 0.5 mm | verified (https://bypass.bluerobotics.com/learn/technical-reference/ via search snippet) |
| Tube ID, cast acrylic | 49.5 ± 1.5 mm | verified (same) |
| Flange (cap) OD / nominal ID / piston Ø | 58.0 mm / 50 mm / 50.95 ± 0.05 mm | verified (https://www.robotshop.com/products/bluerobotics-o-ring-flange-50mm-2 , https://uk.robotshop.com/products/bluerobotics-50-mm-2-inch-o-ring-flange) |
| Tube OD / wall | not captured; flange OD 58 mm implies tube OD ≈ 57–58 mm, wall ≈ 3–4 mm | typical/assumed |
| Lengths | 100, 150, 300 mm (no custom lengths) | verified (https://www.robotshop.com/products/bluerobotics-watertight-enclosure-tube-aluminum-50mm-2-x-100mm-39-1000m) |
| Depth rating, aluminium | 950–1000 m | verified (https://www.robotshop.com/products/bluerobotics-watertight-enclosure-tubes-50-mm-2-aluminum-300-mm-118-950m) |
| Depth rating, acrylic | 95–250 m depending on length/listing (100 mm: 225 m; 150 mm: 250 m; 300 mm: 150 m) | verified (https://www.robotshop.com/products/bluerobotics-watertight-enclosure-tubes-50-mm-2-cast-acrylic-plastic-100-mm-39-225-m , https://jp.robotshop.com/en/products/bluerobotics-防水エンクロージャチューブ-50-mm-2-quot-キャストアクリルプラスチック-150-mm-5-9-quot-250-m) |
| Acrylic end-cap thickness BR recommends for 2" | 6 mm / 0.25 in | verified (https://bluerobotics.com/learn/watertight-enclosure-assembly-guide/ snippet) |
| Flange caps (combined flange + end cap, "locking" design): blank BR-100276-999 (63 g); 2× M10 thru BR-100276-002 (59 g); 4× M10 version; 1× M10 + 8× M6 threaded version | — | verified (https://bluerobotics.com/updated-product-2-watertight-enclosure-series/ , https://uk.robotshop.com/products/bluerobotics-end-cap-50-mm-2-inch-aluminum-2x-m10-hole-1000m , https://uk.robotshop.com/products/bluerobotics-end-cap-50-mm-2-inch-aluminum-4x-m10-hole-1000m , https://eu.robotshop.com/products/bluerobotics-end-cap-1x-m10-8x-m6x1-threaded-1000m-50mm-2) |
| Acrylic blank end cap 2" | 500–600 m | verified (https://www.robotshop.com/products/bluerobotics-cast-acrylic-end-cap-blank-no-holes-50-mm-2-inch-500m) |
| O-rings, locking-series 2" flange: 1× face AS568-030, 2× radial AS568-031 (Buna-N 70A; radial changed from -030 to -031 on 2025-02-19) | — | verified (https://bluerobotics.com/store/watertight-enclosures/2-series/spare-o-ring-set/) |
| O-rings, older non-locking 2" flange: 1× face -030, 2× radial -133 (NBR) | — | verified (https://bluerobotics.com/?p=2546 , https://www.robotshop.com/products/bluerobotics-spare-o-ring-set-2-series) |
| Price: 2" acrylic tube 100 mm | $25.00 | verified (https://www.robotshop.com/products/bluerobotics-watertight-enclosure-tubes-50-mm-2-cast-acrylic-plastic-100-mm-39-225-m) |
| Price: 2" aluminium tube 100 mm | ¥8,232 (≈ $55) | verified JPY (https://jp.robotshop.com/en/products/bluerobotics-防水エンクロージャチューブ-50-mm-2-quot-アルミニウム-100-mm-3-9-quot-950m); USD conversion assumed |
| Price: 2" acrylic tube 300 mm | ¥6,084 | verified JPY (https://jp.robotshop.com/en/products/bluerobotics-防水エンクロージャチューブ-50-mm-2-quot-キャストアクリルプラスチック-300-mm-11-8-quot-150-m) |
| Price: 2" flange cap, 2× M10 | $36.00 (US) / £31.38 (UK) | verified (https://www.robotshop.com/es/products/bluerobotics-end-cap-50-mm-2-inch-aluminum-2x-m10-hole-1000m) |
| Price: 2" O-ring flange (non-locking) | $32.00 | verified (https://www.robotshop.com/products/bluerobotics-o-ring-flange-50mm-2) |
| Price: 2" enclosure clamps (non-locking series) | $34.00 | verified (https://www.robotshop.com/products/bluerobotics-watertight-enclosure-clamps-2-inch) |
| Price: 2" spare O-ring set | $2–19 range page | verified (https://bluerobotics.com/store/watertight-enclosures/2-series/spare-o-ring-set/) |
| 2" flange-cap blank price | not found | — |

**Does a 49 mm Ø motor fit the 2" tube?** Only nominally. Aluminium tube ID 50.0 ± 0.5 mm leaves 0.5–1.5 mm diametral
clearance; acrylic 49.5 ± 1.5 mm may be *smaller* than the motor. There is no room for a motor mount, wiring past the motor, or
a bearing housing of any wall thickness, and the flange-cap bore is smaller than the tube ID. **Verdict: the 2" series is not a
practical fit for a 49 mm motor; use the 3" series or a custom housing.** (Verdict is my inference from the verified IDs.)

### 1.2 Blue Robotics 3" Series

| Item | Value | Status |
|---|---|---|
| Acrylic tube ID / OD | 76.2 ± 2.0 mm / 88.9 ± 0.7 mm (wall ≈ 6.35 mm) | verified (https://www.robotshop.com/products/bluerobotics-240-watertight-acrylic-enclosure-tube-3) |
| Aluminium locking tube ID / OD | 80.14 ± 0.2 mm / 86.5 ± 0.3 mm (wall ≈ 3.2 mm) — note: different ID from acrylic, so flanges differ | verified (https://eu.robotshop.com/products/bluerobotics-300-watertight-aluminum-enclosure-tube-3) |
| Acrylic lengths / depth | 150 mm (300 m), 240 mm (200 m, 442 g), 300 mm (150 m, 560 g), 400 mm (125 m, 758 g) | verified (https://eu.robotshop.com/products/bluerobotics-150-watertight-acrylic-enclosure-tube-3 , https://uk.robotshop.com/products/bluerobotics-400-watertight-acrylic-enclosure-tube-3) |
| Aluminium tube depth | 1000 m | verified (https://uk.robotshop.com/products/bluerobotics-400-watertight-aluminum-enclosure-tube-3) |
| Price acrylic 240 mm | $180.00 (US, on-demand); CAD 215.85 | verified (https://www.robotshop.com/products/bluerobotics-240-watertight-acrylic-enclosure-tube-3 , https://ca.robotshop.com/products/bluerobotics-240-watertight-acrylic-enclosure-tube-3) |
| Price acrylic 150 mm | CAD 213.24 | verified (https://ca.robotshop.com/products/bluerobotics-150-watertight-acrylic-enclosure-tube-3) |
| Price acrylic 300 mm / 400 mm | CAD 264.96 / £249.60 | verified (https://ca.robotshop.com/products/bluerobotics-300mm-watertight-acrylic-enclosure-tube-3-inch , https://uk.robotshop.com/products/bluerobotics-400-watertight-acrylic-enclosure-tube-3) |
| End cap, aluminium blank, 1000 m (with 6 screws) | $16.00 | verified (https://www.robotshop.com/products/bluerobotics-end-cap-75-mm-3-inch-aluminum-blank-no-holes-1000m) |
| End cap, aluminium 4× M10, 1000 m | $14.00 | verified (https://www.robotshop.com/products/bluerobotics-75-mm-3-inch-end-cap-aluminum-4x-m10-hole-1000m) |
| End cap, cast acrylic blank, 400 m | €17.79 | verified (https://eu.robotshop.com/products/bluerobotics-end-cap-cast-acrylic-75-mm-3-inch-blank-400m) |
| 3" O-ring flange price, aluminium tube price | not captured (search budget exhausted) | — |

### 1.3 Blue Robotics WetLink Penetrator (WLP), M10 thread

| Item | Value | Status |
|---|---|---|
| Price range (BR store) | $13.00–$17.00 | verified (https://claude.wp.bluerobotics.com/?p=140112) |
| Sizes: seal "4.5 mm" LC (4.2–4.8 mm jacket), 4.5 mm HC (3.7–4.3), 5.5 mm LC (5.2–5.7), 5.5 mm HC (4.7–5.3), 6.5 mm HC (5.7–6.3), 7.5 mm LC/HC, 8.5 mm LC (8.5 ± 0.3) / HC | — | verified (https://www.robotshop.com/products/bluerobotics-wetlink-penetrator-jpt-m10-45mm-lc-42-to-48mm , https://www.robotshop.com/es/products/bluerobotics-wetlink-penetrator-jpt-m10-45mm-hc-37-to-43mm , https://www.robotshop.com/products/bluerobotics-wetlink-penetrator-jpt-m10-55mm-lc-52-to-57mm , https://robotshop.com/products/bluerobotics-wetlink-penetrator-jpt-m10-55mm-hc-47-to-53mm , https://www.robotshop.com/products/bluerobotics-wetlink-penetrator-jpt-m10-65mm-hc-57-to-63mm , https://www.robotshop.com/products/wetlink-penetrator-m10-85mm-lc) |
| Depth rating | HC ("hobby/low cost") 95–100 m; LC 950 m with tested cables | verified (https://www.robotshop.com/products/bluerobotics-wetlink-penetrator-hc-1-pack-m10-85-mm , https://eu.robotshop.com/products/wetlink-penetrator-m10-85mm-lc) |
| Seal material / temp | FKM, −25 to 200 °C | verified (https://www.robotshop.com/products/bluerobotics-wetlink-penetrator-jpt-m10-55mm-lc-52-to-57mm) |
| Individual prices seen | 5.5 LC $16.91; 4.5 HC $16.91; 8.5 LC CAD 18.57 / €13.83; 8.5 HC $13.00; 4.5 LC $13.00 | verified (URLs above, plus https://www.robotshop.com/products/bluerobotics-wetlink-penetrator-lc-1-pack-m10-45-mm) |

### 1.4 Other COTS IP68 tube enclosures 50–80 mm

No round tube product with published price was found. Closest: autoVimation Nautilus anodised-aluminium camera housing, IP68,
tested 15 bar / 150 m, for payloads ≤ 61 × 61 mm cross-section (box, not tube) — verified
(https://psirep.com/system/files/2026-03/autoVimation%20Nautilus%20Datasheet.pdf ,
https://alliancevision.com/index.php/fr/support-menu-fr/telechargement-fichier-alliance-vision-menu-fr/send/116-autovimation-jdw/1078-autovimation-nautilus).
Rectangular IP68 aluminium boxes: Stahlmetall (https://www.stahlmetall.com/pages/ip68-waterproof-enclosures-natural),
DEM/Deltron 60×55×31 mm upwards (https://www.electronicspecifier.com/?p=109075), Yongu
(https://pdf.directindustry.com/pdf/yongu/yongu-ip68-aluminum-waterproof-case-m03-serise/189540-992368.html), Takachi AWP
(https://pdf.directindustry.com/pdf/takachi-electronics-enclosure-co-ltd/awp-series-ip68-aluminium-enclosure-silicone-protector/187747-1145812.html).
None are shaft-penetrated; all would need a custom end plate. Blue Trail Engineering was not reached (search budget).

---

## 2. Rotary shaft seals, Ø8 and Ø10 mm

### 2.1 Elastomer (NBR/FKM) spring-loaded lip seals — sizes and prices

| Size (d×D×b) | Type | Price | Status |
|---|---|---|---|
| 8×16×7 | SKF/CR HMS4 single lip NBR | $4.25 (Motion, quote item) | verified (https://www.motion.com/products/sku/00602474) |
| 8×16×7 | TC double lip NBR (BASL) | $5.75 | verified (https://metricsealsinc.com/tc-8-x-16-x-7-s-8-x-16-x-7-basl) |
| 8×16×7 | FKM single lip | listed, no price | verified (https://metricsealsinc.com/020259-s-8-x-16-x-7-v) |
| 8×18×7 | TC double lip NBR | listed | verified (https://metricsealsinc.com/double-lip-low-pressure/tc-8-x-18-x-7-s-8-x-18-x-7-basl) |
| 10×19×7 | SKF/CR HMSA10 double lip NBR (carbon-steel spring) | $7.18 | verified (https://www.motion.com/products/sku/02335749) |
| 10×19×7 | CFW double lip NBR (BASL) | $6.20 | verified (https://metricsealsinc.com/cfw-s-10-x-19-x-7-basl) |
| 10×19×7 | HMS5 single lip | $4.37 (Motion); $4.25 (Metric Seals 646004) | verified (https://www.motion.com/products/sku/00602526 , https://metricsealsinc.com/single-lip-low-pressure/646004-s-10-x-19-x-7) |
| 10×22×7 | R23/TC double lip NBR | £2.19 ex VAT (Bearing Boys); $5.85 (Zoro DDS); $7.24 (Motion CR, quote) | verified (https://www.bearingboys.co.uk/Metric-Oil-Seals/OS10x22x7-R23-Double-Lip-Nitrile-Metric-Oil-Seal-7151-p , https://www.zoro.com/dds-shaft-seal-10-x-22-x-7-mm-nitrile-rubber-102207tc/i/G6134731/ , https://www.motion.com/products/sku/02335750) |
| 10×22×7 | Freudenberg Simrit 72 NBR 902 (ISO h11 shaft, H8 bore) | listed RS | verified (https://ie.rs-online.com/web/p/seals/8293660) |
| 10×20×6 | Freudenberg 72 NBR 902 ("90 % less friction torque" marketing claim) | listed RS | verified (https://uk.rs-online.com/web/p/seals/8289223) |
| 8×22×7 | — | not found in session | — |
| 10×22×7 FKM with stainless spring | not found; stainless garter springs seen only on other sizes | — |

Simply Bearings nearby reference: 22×33×10 TC/R23 NBR £5.76 ex VAT — verified (https://www.simplybearings.co.uk/products/22x33x10-tc).

### 2.2 Shaft / housing requirements (elastomer lip seals)

| Parameter | Value | Status |
|---|---|---|
| Shaft tolerance | ISO h11 | verified (SKF HMS5/HMSA10 doc copy https://www.scribd.com/document/508483667/SKF-Seals ; Freudenberg https://ie.rs-online.com/web/p/seals/8293660) |
| Shaft roughness | Ra 0.2–0.8 µm, Rz 1–5 µm, plunge-ground (no lead) | verified (same SKF copy; Klium SKF pages https://www.klium.be/en/skf-g-8x12x3-radial-shaft-seal-8-mm-x-12-mm-x-3-mm-7888) |
| Shaft hardness | SKF HMS5/HMSA10: min 45 HRC; SKF G-series pages: ≥ 55 HRC, hardening depth ≥ 0.3 mm; "at low speeds, good lubrication and minimal contamination a lower hardness can be used" | verified (https://www.scribd.com/document/508483667/SKF-Seals , https://www.klium.be/en/skf-g-18x24x3-radial-shaft-seal-18-mm-x-24-mm-x-3-mm-85298) |
| Housing bore | H8, Ra 1.6–6.3 µm | verified (same) |
| Pressure capability, standard lip seal | ~0.3–0.5 bar continuous (0.03–0.2 bar here is well inside) | typical/assumed (Trelleborg says PDR Type A up to 0.5 MPa; elastomer seals generally ≤ 0.5 bar unless pressure-type) |
| Lip orientation | lip toward the medium to be excluded (water) — i.e. spring side facing water | verified (Klium pages: mount lip outward to keep contaminants out) |
| Speed | 10 mm at 650 rpm = 0.34 m/s — trivial (RS lists SKF 10×26×7 to 2520 rpm) | verified (https://ie.rs-online.com/web/p/seals/2668819) |

**316 as a running surface:** 316 annealed is ~Rockwell B83 (McMaster 316 shaft listing, verified
https://www.mcmaster.com/products/axles/diameter~10-mm) ≈ HRC < 20, far below the 45–55 HRC the seal makers specify. SKF's own
note (verified above) allows softer shafts at low speed with good lubrication and little contamination; silty river water
violates the "minimal contamination" condition, so expect lip-groove wear on 316 over months. Mitigations: hard-chrome or
ceramic-coat the seal land; use a hardened sleeve; or use a PTFE lip (lower contact pressure). **SKF Speedi-Sleeve does not
exist below 11.99 mm shaft** — standard range 11.99–203.33 mm (verified https://docs.rs-online.com/f75e/A700000014065182.pdf ;
smallest listed 99049 for 11.91–12.01 mm https://uk.rs-online.com/web/p/bearing-accessories/0588122). Sleeve material is SAE
304, Ra 0.25–0.5 µm, wall ~0.28 mm; Gold variant ~2300 HV — verified
(https://simplybearings.co.uk/shop/p182125/SKF-CR99836-Gold-Coated-Hardened-Stainless-Speedi-Sleeve-for-Shafts-2.124-2.130-inch/product_info.html ,
https://machinebuilding.net/speedi-sleeve-restores-worn-shafts-quickly-and-economically). For an 8/10 mm shaft a pressed-on
hardened sleeve must be custom-made (e.g. 440C or 17-4PH H900 tube, ground) — typical/assumed.

### 2.3 PTFE lip seals

| Item | Value | Status |
|---|---|---|
| Trelleborg Turcon Varilip PDR: PTFE element in machined metal body; shaft range 6–170 mm; speed to 100 m/s; −60 to +200 °C; Type A single lip to 0.5 MPa (reinforced to 1 MPa); ~50 % of radial-oil-seal torque (in Fomblin oil test); "options for dry running and for soft shafts" | — | verified (https://datasheets.globalspec.com/ds/Trelleborg-Sealing-Solutions-Americas/turcon-varilip-pdr-hispin-pdr-rt/69caadab-3ce0-470f-8ad1-4da60a34236d , https://www.scribd.com/document/644543000/turcon-varilip-pdr-gb-en , https://www.trelleborg.com/seals/your-industry/semiconductor/products-and-capabilities/semiconductor-rotary-seals , https://www.trelleborg.com/en/seals/products-and-solutions/rotary-seals-or-shaft-seals/turcon-varilip-pdr) |
| Varilip shaft Ra / hardness / tolerance | not captured | typical/assumed: Ra 0.2–0.4 µm, ≥ 45 HRC preferred, h7–h8 |
| Dichta C-O stainless-cased PTFE lip seal: shaft finish Ra 0.2–0.4 µm; housing tolerances tabulated from 6–10 mm shaft | — | verified (https://hlgroup.fi/wp-content/uploads/Dichta-PTFE-huuliset-akselitiivisteet.pdf) |
| Parker FlexiLip LFN/LFE PTFE seals | start at 0.625 in / 0.750 in — too large for 8–10 mm | verified (https://ph.parker.com/us/17577/en/multi-purpose-single-lip-solid-ptfe-rotary-shaft-seal-for-high-speed-and-low-pressure-flexilip-lfn-n-lfn-s , https://ph.parker.com/us/17577/en/multipurpose-double-lip-solid-ptfe-rotary-shaft-seal-for-high-speed-and-low-pressure-flexilip-lfe-n-lfe-s) |
| Parjet HiPerLip: short-term dry running / long-term poor lubrication OK | — | verified (https://parjetseals.com/en-US/plist2-hiperlip) |
| Price, small PTFE lip seal | not found; typically $40–120 each at qty 1 from Trelleborg/Dichta distributors | typical/assumed |

### 2.4 Friction torque (no measured value for 8–10 mm found online)

Formula (verified, Uni-Stuttgart IMA: https://www.ima.uni-stuttgart.de/dokumente/forschung/dichtungstechnik/dienstleistungen/en/104180en.pdf):
M_fric = F_r · µ · d/2 ; P = M_fric · 2π n. µ is not constant (verified,
https://powertransmission.com/articles/761-theoretical-and-experimental-study-of-the-frictional-losses-of-radial-shaft-seals-for-industrial-gearbox).
Estimate (typical/assumed radial lip force 3–8 N for an 8–10 mm garter-spring seal, µ 0.3–0.6 water/boundary):
- Ø8: 3.6–19 mN·m per lip → 0.2–1.0 W at 500 rpm
- Ø10: 4.5–24 mN·m per lip → 0.25–1.3 W at 500 rpm
- Double-lip (TC/R23): roughly ×1.5–2. PTFE lip ≈ 50 % of elastomer (Trelleborg claim).
Against the 0.18–0.72 N·m generator torque this is ~1–13 % per lip — significant at the 300 rpm end. A magnetic coupling
removes it entirely. Freudenberg's "90 % less friction torque" figure is relative marketing with no baseline (verified
https://uk.rs-online.com/web/p/seals/8289223).

---

## 3. Static O-ring gland data

### 3.1 Gland dimensions (inch-series cross-sections)

| Cross-section W | Static radial (piston/bore) gland depth | Radial squeeze | Radial groove width | Face-seal gland depth | Face squeeze | Face groove width (liquids) | Status |
|---|---|---|---|---|---|---|---|
| 0.070 in / 1.78 mm | 0.050–0.052 in | 22–32 % | 0.093–0.098 in | 0.050–0.054 in | 19–32 % | 0.101–0.107 in | typical/assumed (Parker ORD 5700 Tables 4-1/4-3, not re-read online) |
| 0.103 in / 2.62 mm (-1xx) | 0.081–0.083 in (2.06–2.11 mm) | 0.017–0.025 in, 17–24 % | 0.140–0.145 in (3.56–3.68 mm) | 0.074–0.080 in (1.88–2.03 mm) | 20–30 % | 0.136–0.142 in (3.45–3.61 mm); vac/gas 0.120–0.125 | depth/squeeze radial verified (Parker copy https://www.scribd.com/doc/262729275/O-Ring-Design-Information); face values verified (Canyon Components https://www.canyoncomponents.com/face-seal-design); radial width typical/assumed |
| 0.139 in / 3.53 mm (-2xx) | 0.111–0.113 in (2.82–2.87 mm) | 16–23 % | 0.187–0.192 in (4.75–4.88 mm) | 0.101–0.107 in (2.57–2.72 mm) | 21–30 % | 0.177–0.187 in (4.50–4.75 mm) | face values verified (Canyon Components, same URL); radial typical/assumed |
| 2.0 mm metric | depth ≈ 1.55–1.65 mm radial (≈ 18–25 % squeeze), width ≈ 2.7 mm; face depth ≈ 1.5 mm, width ≈ 2.7 mm | — | — | — | — | — | typical/assumed (scale from 1.78/2.62 rows) |
| 2.5 mm metric | depth ≈ 1.95–2.05 mm radial (≈ 18–22 %), width ≈ 3.4 mm; face depth ≈ 1.85 mm, width ≈ 3.3 mm | — | — | — | — | — | typical/assumed |

General rules (verified unless noted): Parker recommends ≤ 5 % ID stretch (https://jlcmc.com/blog/o-ring-groove-design-guide);
Freudenberg: reduced CS for 2.62 mm at 1–5 % stretch = 2.59→2.53 mm, min squeeze > 0.1 mm
(https://fst.com/~/media/files/fst,-d-,com/markets/mobility/broschueren/fnst%20o-ring%20reference%20as568%20sizes.ashx);
Apple Rubber: gland fill ≤ 95 % for static seals, O-ring sits on the low-pressure side of a face groove
(https://www.applerubber.com/seal-design-guide/technical-summary/ ,
https://www.applerubber.com/seal-design-guide/seal-types-and-gland-design/static-seal-types/ , tables at
https://www.applerubber.com/seal-design-guide/seal-types-and-gland-design/illustrations-and-tables/ and
https://www.applerubber.com/src/pdf/table-a-static.pdf). Surface finish: groove faces Ra 0.8 µm (32 µin) for liquids, 0.4 µm
(16 µin) for gas/vacuum; groove bottom Ra 1.6 µm acceptable — typical/assumed (Parker ORD 5700). For a printed housing,
machine or insert a turned sealing land; FDM surfaces are not an O-ring sealing face — my recommendation.

### 3.2 Dash numbers / metric sizes for a 50–60 mm bore

AS568 nominal IDs (verified -137 = 52.07 mm ID, 2.62 mm CS at https://www.marcorubber.com/product/B1000-137 ; the rest are
the standard AS568 table, typical/assumed, re-check): -133 45.69, -134 47.30, -135 48.90, -136 50.47, -137 52.07, -138 53.64,
-139 55.25, -140 56.82, -141 58.42, -142 59.99 mm (all 2.62 mm CS). -224 44.04, -225 47.22, -226 50.39, -227 53.57, -228 56.74,
-229 59.92, -230 63.09 mm (3.53 mm CS). Metric ISO 3601: 50×2.5, 52×2.5, 55×2.5, 50×3, 53×3 (e.g. 53×3 NBR70 listed at
https://www.dexis.be/en/o-ring-nbr-70-53x3/15010219), 50×2, 52×2 — typical/assumed availability.
Blue Robotics' own 2" flange uses -133 radial (non-locking) / -031 radial + -030 face (locking) — see §1.1.

### 3.3 Material and prices

- EPDM is the usual choice for water; NBR OK for cool, non-chlorinated water (poor > ~50–75 °C); FKM is "generally not
  resistant to hot water/steam" but fine at 0–25 °C — verified (https://www.marcorubber.com/nbr-vs-sil-vs-fkm-vs-epdm/material-type/14v21v10v7 ,
  https://www.marcorubber.com/Buna-N-vs-EPDM/material-type/14v7 , https://jlcmc.com/blog/o-ring-material-guide ,
  https://www.scribd.com/document/414367348/o-Ring-Material-Guide-Gb-1 , https://eng-tips.com/threads/cooling-water-seals.524857).
  Recommendation: EPDM 70 for the static seals (never near mineral oil/grease — use silicone or PFPE grease on EPDM); NBR 70 if
  the shaft seal area is oil/grease lubricated. Blue Robotics ships Buna-N 70 and it works at these depths.
- Prices: AS568-137 NBR70 $0.18–0.38 each (https://shop.callapg.com/nitrile-70-durometer-o-ring--137-h70137 ,
  https://www.allworldmachinery.com/itemdetail/AS568-137), $81.29/400 (https://www.zoro.com/macho-o-ring-seal-137-bunanbr-o-ring-as568a-70a-durometer-black-id-2-116in-od-2-14in-cs-332in-400pk-137-nbr70m400/i/G711889663/);
  FKM -137 listed (https://shop.callapg.com/fluoroelastomer-70-durometer-o-ring--137-v70137). 50×2.5 price not found.

---

## 4. Bearings

### 4.1 Ratings and prices

| Bearing | d×D×B | C dyn (N) | C0 (N) | Speed limit | Price | Status |
|---|---|---|---|---|---|---|
| S6000-2RS 440C (RS PRO) | 10×26×8 | 4095 | 1764 | — | — | verified (https://uk.rs-online.com/web/p/ball-bearings/2612671) |
| S6000-2RS 440C (VXB/Zoro/IDC) | 10×26×8 | 4550 | 1970 | — | $18.78 (IDC/KSC), CAD 38.06, $87.59 SNR | verified (https://kscdirect.com/itemDetail/6268435/6000-series-bearing , https://bearingscanada.com/products/s6000-2rs-stainless-steel-bearing-10x26 , https://www.zoro.com/snr-ball-bearing-bore-dia-10mm-26mm-od-s6000-2rs-fg1/i/G8094479/) |
| S6900-2RS 440C (VXB) | 10×22×6 | 2490 | 1130 | 22,000 rpm grease | — | verified (https://vxb.com/products/6900-2rs-bearing-sealed-10x22x6 , https://bearingscanada.com/products/s6900-2rs-bearing-10x22x6-stainless-ste) |
| 6900-2RS chrome | 10×22×6 | 2700 | 1270 | 21,000 rpm | — | verified (https://2mequipment.com/products/6900-2rs-ball-bearing-10x22x6-sealed-61900-2rs1) |
| S608-2RS / 608-2RS | 8×22×7 | 3300 | 1370 | — | £9.99 (Enduro SS), AUD 6.77 | verified (https://uk.rs-online.com/web/p/products/2612681 , https://westbrookcycles.co.uk/s608_2rs_stainless_steel_bearing-10134 , https://minibearings.com.au/collections/bearings-single-row-ball?page=83) |
| S6200-2RSR 440C (FAG) | 10×30×9 | 4350 | 1910 | — | €12.62 (Misumi) | verified (https://www.qualitybearingsonline.ca/s6200-2rsr-fag-stainless-steel-deep-groove-bearing-10x30x9mm , https://api.uk.misumi-ec.com/vona2/detail/221303588114) |
| S6800-2RS 440C (SKD) | 10×19×5 | 1548 (348 lbf) | 756 (170 lbf) | 30,600 rpm | $1.52 | verified (https://www.skdin.com/products/productid-S6800 2rs) |
| 316 stainless bearings (McMaster) | various | ~5–7× lower than 440C (e.g. 6005: 270 lb vs 1900 lb; R4A 75 vs 440 lb); open, need lube; won't pit in salt water | — | — | verified (https://www.mcmaster.com/bearings/bearing-trade-number~6005/ , https://www.mcmaster.com/bearings/bearing-trade-number~r4a) |
| 608 ZrO2 full ceramic (VXB) | 8×22×7 | 1100 | 1350 | — | $9.99–27.52 open; $14.99 2RS | verified but sources disagree up to 3× (https://vxb.com/products/608-zro2-full-ceramic-open-ball-bearing-with , https://smallbearings.com/products/608-2rs-full-ceramic-sealed-bearin-2212 , https://miniaturebearings.com.au/products/8x22x7-ballbearing-czr608ttsmc34tfdry/data?view=data) |
| 6000 ZrO2 full ceramic, PTFE cage | 10×26×8 | not published | — | 180 °C max | $39.99–54.99 (VXB), £33.31 (123bearing), CAD 56.39 | verified (https://vxb.com/products/6000-2rs-full-ceramic-sealed-bearing-10x26x8-zro2 , https://123bearing.co.uk/bearing-housing/deep-groove-bearing/ceramic/6000-ce-zro2-ptfe-zen , https://bearingscanada.com/products/6000-full-ceramic-bearing-10x26x8-zro2) |
| igus xiros BB-6000-B180-10-ES/GL (xirodur B180 races, stainless or glass balls, PA cage) | 10×26×8 | 119 | 85 (max axial 285) | 1,900 rpm | $8.48 (igus CA), €13.95 (Simply Bearings), £6.80 (RS -30-ES) | verified (https://www.igus.ca/info/ball-bearings-xiros-b180-ca , https://simplybearings.co.uk/shop/p601254/xiros-xirodur-BB6000B18010ESC-Polymer-Ball-Bearing-with-PA-Cage-and-Stainless-Steel-Balls-and-Cover-Plate-10x26x8mm/product_info.html , https://uk.rs-online.com/web/p/ball-bearings/2724326) |
| igus xiros BB-608-B180-30-GL (glass balls, "suitable for underwater") | 8×22×7 | 94 | 80 | — | $17.88 GL / $5.39 ES (igus CA) | verified (https://uk.rs-online.com/web/p/ball-bearings/2724379 , https://www.igus.ca/info/ball-bearings-xiros-b180-with-cover-plate-ca) |
| igus BB-6800-B180-30-ES | 10×19×5 | — | — | — | listed | verified (https://uk.rs-online.com/web/p/ball-bearings/2724458) |

Water notes: ZrO2 is "extremely water resistant … often used in marine applications" but weakened by hot water/steam —
verified (https://www.smbbearings.com/products/zirconia-ceramic-bearings-inch.html , https://fhdbearings.com/?p=3731). 440C
"won't degrade from water or mild chemicals but weakens in salt water" — verified (McMaster, above). Sealed 2RS steel bearings
are not watertight; a flooded 440C bearing in silty water will corrode/wear — my recommendation is: dry-side 440C (or chrome)
sealed bearings, or, if flooded, full-ceramic ZrO2 with PTFE/PEEK cage or igus polymer (T200 practice, §8).

### 4.2 L10 life at Fa = 20 N, Fr = 15 N, n = 500 rpm (ISO 281; my calculation)

P = X·Fr + Y·Fa with X = 0.56 when Fa/Fr > e; e, Y from the normal-clearance DGBB table (Fa/C0 = 0.014 → e 0.19, Y 2.30;
0.028 → 0.22, 1.99; 0.17 → 0.34, 1.31; 0.28 → 0.38, 1.15 — typical/assumed standard table). L10 = (C/P)^3 ×10^6 rev;
L10h = L10 / (60 n).

| Bearing | Fa/C0 | P (N) | L10 (10^6 rev) | L10h at 500 rpm |
|---|---|---|---|---|
| S6000-2RS (C 4095, C0 1764) | 0.011 | 54.4 | 4.3 × 10^5 | 1.4 × 10^7 h |
| S6900-2RS (C 2490, C0 1130) | 0.018 | 52.8 | 1.05 × 10^5 | 3.5 × 10^6 h |
| S608-2RS (3300/1370) | 0.015 | 54.1 | 2.3 × 10^5 | 7.6 × 10^6 h |
| S6800-2RS (1548/756) | 0.026 | 48.9 | 3.2 × 10^4 | 1.1 × 10^6 h |
| 608 ZrO2 (1100/1350, uncertain) | 0.015 | 54.0 | 8.4 × 10^3 | 2.8 × 10^5 h |
| igus BB-6000-B180 (119/85) | 0.235 | 32.7 | 48 | **~1,600 h** |
| igus BB-608-B180 (94/80) | 0.25 | 32.3 | 25 | **~800 h** |

Conclusion: fatigue life is irrelevant for any steel/ceramic size — the limit is corrosion, lubricant washout and seal wear.
Polymer bearings are marginal at this axial load (igus rates life by wear, not ISO 281 — use igus's own calculator); take the
rotor thrust on a steel/ceramic bearing. Applied resultant 25 N is below the usual 0.01·C minimum load (41 N for 6000) —
typical/assumed guideline; harmless at 500 rpm (skidding is a high-speed concern). Flood thrust 70 N → Fa/C0 = 0.04 for S6000,
still trivially within C0.

---

## 5. Shaft material and hardware

| Topic | Finding | Status |
|---|---|---|
| 316 | best freshwater/saltwater corrosion; soft: McMaster 316 rotary shafts Rockwell B83, Ø-tolerance −0.015/0 mm (≈ h7) | verified (https://www.mcmaster.com/products/axles/diameter~10-mm , https://www.mcmaster.com/products/axles/diameter~8-mm) |
| 17-4PH | HB 280–440; McMaster H1150 rod Rockwell C28, H900 "comes hardened" (typ. ≈ HRC 40–44, typical/assumed); corrosion between 316 and 416, more pitting-prone than 316 | verified (https://hmaking.com/17-4ph-vs-316-stainless-steel/ , https://www.mcmaster.com/products/h1150-temper-rods , https://www.mcmaster.com/h900-temper-rods) |
| 416 | most wear-resistant/hardenable, "least corrosion-resistant stainless"; "if you're not in salt water you should be all right with 416"; the usual pump-shaft pick | verified (https://shop.machinemfg.com/416-stainless-steel-vs-316-key-differences , https://www.eng-tips.com/viewthread.cfm?qid=161981 , https://www.russelmetals.com/en/product/steel-plates-baldwin/mar-10/) |
| 303 | free-machining, HRB ~95 annealed (typical/assumed), corrosion below 316; Zoro 303 keyed shaft 10×300 $19.39 | verified price (https://www.zoro.com/zoro-select-keyed-shaft-303-ss-10-mm-dia-300-mm-l-zshk-m10-m0300-303su/i/G111815361) |
| Recommendation | 316 shaft for corrosion, with a hardened seal land (sleeve or coating) if an elastomer lip seal is used; or 17-4PH H900 if a single hard shaft is preferred and you accept slightly lower corrosion resistance | my recommendation |
| 316 shaft 10 × 300 mm | Zoro 316 keyed shaft $29.15 (ZSHK-M10-M0300-316SU); McMaster 316 shafts listed in 5/8/9/10 mm × 300 mm (price not captured) | verified (https://zoro.com/zoro-select-keyed-shaft-316-ss-10-mm-dia-300-mm-l-zshk-m10-m0300-316su/i/G111815330) |
| Misumi | standard precision shafts are Cf53/52100/440C h6–h7 (6–30 mm, 1 mm increments); SUS316 only as configurable round bar, no h6 price captured | verified (https://www.newequipment.com/product-directory/motion-control/linear-motion-positioning/product/55112632/47561-a-new-standard-in-precision-linear-shaft , https://jp.misumi-ec.com/maker/misumi/mech/product/sus316/) |
| Shaft collars | Ruland MCL-10-ST 316 clamp collar $25.99 (Zoro) / £32.85 (Acorn); Climax MC-10-S 303 set-screw collar $14.73 (Motion); 8 mm 316 not captured | verified (https://www.zoro.com/ruland-shaft-collar-clamp-1pc-10mm-316-ss-mcl-10-st/i/G7826786/ , https://acorn-ind.co.uk/p/mcl-10-st-ruland , https://www.motion.com/products/sku/07028385) |
| Set screws M3 316 cup point | $8.63/50 (M3×16, Mutual Screw) | verified (https://mutualscrew.com/products/socket-set-screws-316-stainless-steel-m3-x-16mm_metrichba03016rczz) |
| DIN 471 circlip 10 mm, 1.4122 stainless | £36.31/100 (PTS); $40.90/10 Wurth (Schnap); RS PRO bag of 50 AUD 30.44 | verified (https://www.pts-uk.com/products/retaining-rings-and-clips/external-circlips/metric-a2/a47110 , https://www.schnap.com.au/circlip-10-pcs-stainless-steel-din-471-rohs-wurth-4890110.html , https://au.rs-online.com/web/p/circlips/2096621) |
| DIN 6799 e-clip 8 mm stainless | not found; 12 mm shaft size €8.36/50 (RS) | verified (https://ie.rs-online.com/web/p/circlips/2096902) |
| 3 × 20 mm dowel pins | 316: $1.13 ea (Motion); A2: $1.85/10 (Zoro); 304 50-pk (Walmart/uxcell); A4 DIN 7 (MROSupply) | verified (https://www.motion.com/products/sku/11739727 , https://www.zoro.com/i/G3411707/ , https://www.walmart.com/ip/Uxcell-3mmx20mm-304-Stainless-Steel-Dowel-Pin-50-Pack/755120446 , https://www.mrosupply.com/fasteners/6420185_fstpck-551222_mrosupply-fasteners/) |

---

## 6. Cable exit

| Item | Finding | Status |
|---|---|---|
| PG7 nylon IP68 gland, 3–6.5 mm | £0.20–0.28 ea (Farnell PRO ELEC, Maplin); €1.00 Lapp 53018000 (2.5–6.5 mm); Essentra CG-PG7-2-BK | verified (https://cpc.farnell.com/c/cable-leads-connectors/cable/pg7-cable-gland , https://pro.maplin.co.uk/products/pg7-black-nylon-cable-gland-ip68 , https://www.buerklin.com/en/p/lapp/cable-glands/53018000/32P3046/ , https://digikey.cn/en/products/detail/essentra-components/CG-PG7-2-BK/3811769) |
| PG7 nickel-plated brass IP68, 3–6.5 mm | AUD 7.27 (Altronics); RS PRO 8319046; Alpha Wire FIT | verified (https://www.altronics.com.au/product/h4334-3-65mm-eg7-pg7-ip68-metal-cable-gland , https://uk.rs-online.com/web/p/cable-glands/8319046 , https://uk.rs-online.com/web/p/cable-glands/1753768) |
| M12 stainless IP68 | Weidmüller 1.4305 (303) 3–6.5 mm £35.89 ex VAT; Lapp SKINTOP INOX M12x1.5 (53806739) €12.13 / CAD 117.53 (×5), "sea-water resistant" stainless, grade not stated; Lapp SKINTOP HYGIENIC M12 is 316, 4–6 mm; INOX SC 4–7 mm | verified (https://uk.rs-online.com/web/p/cable-glands/2876417?gb=s , https://bankoflamps.com/lapp-53806739-4044776711872 , https://www.lumen.ca/en/products/11-conduit-raceway-strut/03-conduit-fittings/01-hazardous-location-fittings/02-cable-glands/p-Q0FCT0xGNTM4MDY3Mzk=-cabolf53806739-lapp-53806739-skintop-inox-m12x15 , https://express.ecsnz.com/en/skintop-hygienic-stainless-steel-gland-m12x15 , https://tameson.co.uk/products/skintop-inox-m12-stainless-steel-cable-gland-53806739) |
| Blue Robotics WetLink | see §1.3: $13–17, M10, FKM seal, 95 m (HC) / 950 m (LC) | verified |
| 3-core cable | Alpha Wire 5063C (Xtra-Guard 1, 3 × 18 AWG tinned, PVC) nominal OD 6.05 mm; 5033C 3×18 AWG ≈ AUD 35.87/m (1000 ft reel only); Pacer 14/3 round 10.4 mm OD is too big; Ancor 18 AWG single tinned $0.21/ft | verified (https://advantageelectricsupply.com/part/alpha-wire/5063c-sl001/2099731 , https://uk.rs-online.com/web/p/control-cable/0103606 , https://shop.hamiltonmarine.com/products/pacer-wire-tinned-14-3-round-black-green-white--by-foot--60289.html , https://www.delcity.net/store/wire-cable/ancor-marine-grade-tinned-primary-wire/18-gauge-100-ft/) — a 4–5 mm PUR 3×0.5 mm² option was not captured (search budget) |
| Potting: 3M Scotchcast 2131 (polyurethane, 1 kV splices) | 213 g kit $42.27 (Motion) to $84.16; 612 g $132.55; DigiKey flags 2131 as discontinued | verified (https://www.motion.com/products/sku/09507289 , https://www.egrimesdirect.com/products/3m-2131-217g , https://www.gescan.com/products/10-adhesives-chemicals-lubricants/01-adhesives/13-general-purpose-adhesives/p-TU1NMjEzMTYxMkc=-3m-canada-2131-612g-215oz-3m-scotchcast-flame-retardant-compound , https://www.digikey.de/en/products/detail/3m/2131/16536686) |
| 3M Scotchcast 2136 potting kit 1.5 oz | $74.76 | verified (https://steinerelectric.com/Catalog/Wire-ConnectorsTermination-And-Management/Wiring-Connectors/Splicing-And-Terminating-Accessories/Resins-And-Compounds/3M-Scotchcast-2136-Potting-Kit1-5-oz-Size-A-2-Part-PouchBlackLiquidPart-A-1-08-Part-B-0-98-756431) |
| MG Chemicals 8810 PUR (tough) / 8800 PUR (flexible) 375 mL | £37.88 ex VAT (8810); 832WC epoxy 375 mL $68.25 (DigiKey) | verified (https://uk.rs-online.com/web/p/potting-compounds/1927565 , https://uk.rs-online.com/web/p/potting-compounds/1927564 , https://electronicspecifier.com/product-centre/distributors/digi-key/part/5b09dd1c5677c82bbf02f65c) |
| AquaBond RC-7000 re-enterable (2123 substitute) 350 mL | $73.55 | verified (https://production.poolsupplyunlimited.com/pool/aquabond-rc-7000-350-reenterable-electrical-potting-compound/38807p1) |
| WetLink cable splice kit (no potting, 5 m) | $20.00 | verified (https://www.robotshop.com/products/wetlink-cable-splice-kit) |
| Forum: urethane "PUR80" works as Scotchcast alternative; cure before wetting | — | verified (https://discuss.bluerobotics.com/t/alternatives-to-scotchcast-potting-compound/1892) |

---

## 7. Fasteners, inserts, galvanic notes

| Item | Finding | Status |
|---|---|---|
| 316 SHCS M3×10 | $0.30 ea in 50s (Govets DIN 912); $10.59 ea single (Zoro AMPG) | verified (https://govets.com/value-collection-096653476125-310-02124105.html , https://www.zoro.com/ampg-m3-050-socket-head-cap-screw-socket-plain-316-stainless-steel-10-mm-length-zss616m3x10/i/G6317637) |
| 316 SHCS M3×12 | $5.39 ea (Zoro Select) | verified (https://www.zoro.com/zoro-select-m3-050-socket-head-cap-screw-socket-plain-316-stainless-steel-12-mm-length-zul602m3x12/i/G310397460/) |
| 316 SHCS M4×12, 100 pk | $56.99 ($0.57 ea, Newport) | verified (https://www.zoro.com/newport-fasteners-m4-070-socket-head-cap-screw-plain-316-stainless-steel-12-mm-l-100-pk-366341-100/i/G006341142) |
| 316 button head M3×10, 50 pk | $5.19 ($0.10 ea) | verified (https://www.zoro.com/boltsandnutscom-m3-050-socket-head-cap-screw-button-plain-316-stainless-steel-10-mm-length-50-pk-m3c10bshcsa4d-50/i/G114477054/) |
| Heat-set inserts: McMaster 94180A331 M3×0.5, 5.56 mm long, min wall 4.57 mm, hole #8 drill (≈ 5.0 mm) | — | verified (https://medesignlab.me.wisc.edu/wp-content/uploads/sites/2200/2024/08/M3-Inserts-Drawing.pdf , https://www.mcmaster.com/brass-inserts) |
| McMaster 94180A333 (M3, 6.4 mm) 100 pk | $44.45 ($0.44 ea) via Zoro | verified (https://zoro.com/bsc-preferred-tapered-heat-set-inserts-for-plastic-brass-m3-x-050-mm-thread-size-6400-mm-installed-lngth-100pk-94180a333/i/G611638880) |
| Generic brass M3×4 / M3×3 50 pk | ≈ AUD 12 | verified (https://core-electronics.com.au/brass-heat-set-inserts-for-plastic-m3-x-4mm-50-pack.html.plain.md) |
| Stainless 303 heat-set inserts exist (stronger, lead-free) | — | verified (https://www.mcmaster.com/inserts/thread-size~m1-6) |
| Galvanic series (seawater, SCE): Al 6061 −820 mV; naval brass −450 mV; 316 passive −150 mV (active −550 mV); keep coupled metals within 200 mV | 316–Al ≈ 670 mV, brass–316 ≈ 300 mV → both exceed guideline | verified (https://www.gerrmarine.com/Articles/controllingcorrosionpt1.pdf , https://www.rfcafe.com/references/general/galvanic-series.htm , https://ns2.alliedtitanium.com/technical/galvanic/Galvanic_Series.pdf) |
| Freshwater | lower conductivity → lower rate, but Al is still the anode; anodise (Type III) the aluminium, keep brass inserts out of wetted aluminium, put Tef-Gel/nylon washers under 316 heads in Al, prefer 316 or 303 inserts in parts that are wetted | typical/assumed (seawater data only found) |
| Anti-seize: Tef-Gel 2 oz $46.00 (Fisheries) / $39.09 (Hamilton); Loctite LB 8009 metal-free 28 g $12.83, 255 g $42.88, 1315 °C | Tef-Gel "does not electrically insulate"; LB 8009 "for stainless, aluminium, soft metals" | verified (https://www.fisheriessupply.com/ultra-safety-systems-ultra-tef-gel-anti-seize-lubricant-tg2 , https://shop.hamiltonmarine.com/products/tef-gel-lubricant-anti--seize---corrosion-2oz-tub-33066.html , https://skygeek.com/henkel-loctite-51609-anti-seize-heavy-duty.html , https://www.ellsworth.com/products/by-market/general-industry/lubricant-products/anti-seize/henkel-loctite-heavy-duty-anti-seize-gray-1-oz-can/) |

---

## 8. COTS flooded-motor practice (Blue Robotics T200) — evidence for a flooded generator

- Fully flooded brushless outrunner; windings/stator encapsulated (changed from epoxy-coated to fully potted for abrasion and
  insulation resistance and to stop broken wire phases); magnets and rotor coated — verified
  (https://bluerobotics.com/store/thrusters/t200-thruster/ , https://bluerobotics.com/?p=129135 , https://patents.justia.com/patent/12291319).
- Bearings are solid plastic bushings/plastic ball bearings, water-lubricated; "run in air ≤ 10 s" or bearings overheat and
  deform; a 2019 batch of white bearings deformed under continuous use and was recalled; shaft-to-bearing tolerance variation
  gives per-unit performance scatter — verified (https://bluerobotics.com/wp-content/uploads/2020/01/Blue-Robotics-TB04-White-Bearings.pdf ,
  https://bluerobotics.com/?p=133206 , https://discuss.bluerobotics.com/t/t200-motor-stucked/6616 ,
  https://discuss.bluerobotics.com/t/t200-needs-servicing/5504).
- Body/prop polycarbonate; only exposed metal 316 — verified (https://nauticexpo.com/prod/bluerobotics/product-69617-546027.html).
- Price from $230 (T200 R2) — verified (https://claude.wp.bluerobotics.com/?p=137980).
- Implication: a flooded generator is viable *if* the stator is fully potted, magnets are coated/encapsulated, and bearings are
  polymer or ceramic designed for water. For silty river water with continuous duty the T200 bearing wear history argues for
  ceramic (ZrO2) rather than polymer, and for a sacrificial, easily replaced bearing cartridge. A dry cartridge with a magnetic
  coupling avoids all of this at the cost of coupling volume — my inference.

---

## 9. Kit cost estimates (one prototype)

### (a) Blue Robotics 2" enclosure route (note §1.1: motor does not realistically fit; costs shown for completeness, and a 3" variant)

| Item | 2" (acrylic / aluminium) | 3" (acrylic) | Status |
|---|---|---|---|
| Tube | $25 (acrylic 100 mm) / ≈$55 (Al 100 mm) | ≈$150–215 (150–240 mm) | verified / JPY-converted / CAD-based |
| Flange caps or flanges+end caps (2) | 2 × $36 = $72 | 2 flanges ≈ $45 ea (typical/assumed) + end caps $14 + $16 = ≈$120 | partly verified |
| Clamps (non-locking only) | $34 | — | verified |
| Spare O-rings | $2–19 | $5–19 | verified range |
| WetLink penetrator | $13–17 | $13–17 | verified |
| Lip seal (NBR double lip) | $5–8 | $5–8 | verified |
| 2 × S6000-2RS 440C | $38 | $38 | verified |
| 316 shaft 10 × 300 | $29 | $29 | verified (keyed; plain likely less) |
| Collar + circlips | $20–30 | $20–30 | verified |
| 316 screws + inserts | $15 | $15 | verified-range |
| Cable 3 m + nylon gland spare | $10–20 | $10–20 | typical/assumed |
| **Total** | **≈ $265–300** | **≈ $410–510** | estimate |

### (b) Printed/coated housing + machined end caps + same seals

| Item | Cost | Status |
|---|---|---|
| FDM housing (PETG/ASA/PA, ~150 g) + epoxy/urethane coating | $10–30 | typical/assumed |
| 2 machined end caps (6061 anodised or Delrin), with O-ring lands and seal bore | $60–160 (job-shop); $10–20 if turned in-house | typical/assumed |
| Static O-rings (4) | $2–5 | verified unit prices |
| Lip seal, 2 bearings, shaft, collar, circlips, screws, inserts | ≈ $115–130 (same as above) | verified |
| Cable gland: PG7 nylon $1 or SKINTOP INOX ≈ $15–40 | $1–40 | verified |
| Cable + potting (MG 8810 or Scotchcast 2136) | $45–85 | verified |
| **Total** | **≈ $245–450** | estimate |

Add ≈ $40–60 for a 6000-size full-ceramic pair or $20–35 for igus polymer pair if a flooded bearing variant is built.

---

## 10. Not found / could not be verified in this session

- Blue Robotics 2" tube OD and wall thickness; 2" flange-cap blank price; 3" O-ring flange and aluminium tube USD prices.
- Blue Robotics official pages themselves (bluerobotics.com, robotshop.com) — all values via search snippets only.
- Parker ORD 5700 tables read directly (values given from a Scribd copy, Canyon Components, and memory where tagged).
- Measured friction torque for any 8–10 mm lip seal; radial lip force for small seals; Varilip PDR shaft Ra/hardness/tolerance; PTFE lip-seal prices at small size.
- 8×22×7 seal price; 10×22×7 FKM with stainless spring.
- 6000-size ZrO2 load ratings (not published by retailers); 608 ZrO2 ratings conflict 3×.
- McMaster 316 shaft price for 10 × 300 mm; Misumi SUS316 h6 shaft price; 8 mm 316 shaft collar price; DIN 6799 8 mm stainless e-clip price; 50 × 2.5 NBR O-ring price.
- A 3-core, 4–5 mm OD PUR submersible cable with price; Hummel HSK-INOX price; Lapp SKINTOP INOX alloy grade (316 vs 304).
- Freshwater-specific galvanic potentials (seawater table only).
- Other COTS round IP68 tube enclosures 50–80 mm with prices (Blue Trail Engineering not reached).
