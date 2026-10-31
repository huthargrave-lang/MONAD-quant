# Generator candidates for an 8-inch (203 mm) axial hydrokinetic turbine

Date: 2026-10-31. Researched with web search only. **Caveat on access:** this session's network allowlist blocked direct page fetches of copterlab.com, customgimbals.com, smc-powers.com, store.tmotor.com, robotshop.com, sparkfun.com, cubemars.com, iflight.com, ligpower.com, rcdrone.top, onedrone.com, vxb.com, hobbyking.com, hackaday.io, simplefoc.com and rctimer.com; every number below therefore comes from search-engine snippets/summaries of those pages (URL given each time) and should be re-checked against the live page before purchase. The per-turn web-search budget was exhausted before a few follow-ups (Hackaday gimbal-wind result, Piccoli/Yim cogging amplitudes, MN5008 KV170 data, PMD 762-C01 electrical data, GB54-2 resistance, seal-friction data) could be run.

Marking convention: **[V]** = verified from a published page (URL given); **[A]** = assumed/estimated by me; **[C]** = conflicting sources; **[?]** = not found.

Turbine operating points (given): 1.0 m/s 300 rpm 5.5 W 0.18 N·m; 1.5 m/s 475 rpm 20 W 0.40 N·m; 2.0 m/s 650 rpm 49 W 0.72 N·m. Static torque at 1 m/s ~0.09 N·m. Runaway 590 rpm (1 m/s), 1270 rpm (2 m/s). Envelope ~Ø60 × 35 mm.

---

## 1. GB5015 brushless gimbal motor (Copterlab) — everything found

Product page (not fetchable from this session): https://copterlab.com/5015-brushless-gimbal-motor-without-encoder . The same motor is listed by Copterlab's sister site https://customgimbals.com/en/gimbal-brushless-motors and by the apparent OEM, SMC Powers (http://www.smc-powers.com/English/Product/3705921759.html , http://shop.smc-powers.com/GB5015-Gimbal-motor.html). Copterlab's comparison table is at https://copterlab.com/gimbal-custom-motors .

| Item | Value | Status / source |
|---|---|---|
| Body diameter × length | 49 × 29 mm | [V] copterlab.com/gimbal-custom-motors ; smc-powers.com (OD 49, L 29) |
| Stator | 43 × 15 mm (GB5010 sibling: 43 × 10 mm) | [V] shop.smc-powers.com/GB5015-Gimbal-motor.html |
| Slots / poles | 24N28P | [V] smc-powers.com/English/Product/3705921759.html (search summary). Note: 24N22P is listed for other motors in the same table; count magnets on receipt. |
| Mass | 165 g "without encoder house" | [V]/[C] copterlab.com/gimbal-custom-motors says 165 g; SMC pages show 120/155 g in a weight row and 135 g in a product title — conflicting. Weigh it. |
| Torque | 220 mN·m @ 14.8 V | [V] copterlab.com/gimbal-custom-motors ; SMC also lists "max torque 4 kg·cm" (= 0.39 N·m) with no voltage stated. Interpreted as **stall/holding torque at 14.8 V** (usual gimbal-vendor convention) — see §2. |
| Input voltage | 12–24 V | [V] copterlab.com/gimbal-custom-motors |
| Suggested gimbal payload | 1200–2200 g (shared row with GB5010) | [V] copterlab.com/5010-brushless-gimbal-motor-without-encoder |
| KV (rpm/V) / back-EMF constant | not published | [?] |
| Phase / line resistance | not published | [?] (SMC's DM5015 page has resistance values but that is a different series) |
| Inductance | not published | [?] |
| Max continuous / peak current | not published | [?] |
| Bearing type | not published | [?] |
| Shaft | hollow shaft "supports slip ring"; Copterlab table lists a 12.5 mm slip ring with 18 wires (accessory) → bore ≈ 12.5 mm likely | [V] smc-powers.com (hollow); [A] bore size |
| Mounting holes | top M4 × 25/30 mm, bottom M4 × 30 mm (SMC GB5015 row); M3 × 30/35 belongs to the larger 8008 motor | [V] smc-powers.com/English/Product/3705921759.html (search summary) |
| Wire gauge / turns | not published | [?] |
| Price | US$54.91 w/o encoder; $106.07 / $106.98 with AS5048A / AS5048B encoder (Copterlab/customgimbals); SMC Powers $37.69 ($36.94 for 3+, encoder status unclear); AliExpress GB5010/GB5015 with encoder US$68–70 | [V] customgimbals.com/en/gimbal-brushless-motors ; shop.smc-powers.com/GB5015-Gimbal-motor.html ; http://www.aliexpress.com/item/gimbal-motor-with-AS5048-encorder/32415133671.html |
| Lead time | not published for this motor; Copterlab states "Free shipping available" (https://copterlab.com/gimbal-encoders) and, for another product, "Manufactured per order request, dispatched in 3 weeks" (https://copterlab.com/2-axis-raspberry-pi-high-quality-pan-tilt-brushless-gimbal) | [?] / [V] |
| NDAA compliant | yes (page title) | [V] customgimbals.com |
| IP65 variant | **not found** on any Copterlab/customgimbals/SMC page or search result. Nearest sealed gimbal motors found are CubeMars GL series, rated **IP45** only (https://store.cubemars.com/products/gl35 ; https://rcdrone.top/products/cubemars-gl60-kv25-brushless-gimbal-motor-large-hollow-shaft-low-cogging-ultralight-ip45-waterproof). IP65 would mean dust-tight + low-pressure water jets, **not immersion**; inside a sealed, water-cooled housing the motor's own IP rating is irrelevant — the housing + shaft seal (or magnetic coupling) carries the sealing duty. | [?] |

Encoder accessories: AS5048B PCB 15 × 17 mm (https://copterlab.com/spare-parts). Old BaseCam forum note that a 5015 "does not work good without encoders" as a gimbal motor (https://forum.basecamelectronics.com/index.php?p=%2Fdiscussion%2F1843%2Fencoder-motors-%2Fp1) — irrelevant for generator use.

**Must be measured on the physical motor:** KV, line-to-line resistance (all three pairs), inductance (optional), cogging/detent torque, pole count, bore/shaft diameter and shaft material, mounting hole pattern and thread, bearing type/axial play, mass, lead wire gauge, winding temperature rise under load. Procedures in §5.

---

## 2. Generator evaluation of the GB5015

### 2.1 Convention
* **KV** is the hobby definition: no-load rpm per volt of DC bus, i.e. the **peak line-to-line back-EMF** is E_LL,pk = rpm / KV. (For sinusoidal EMF, E_LL,rms = E_LL,pk / √2.)
* **Kt = 60 / (2π·KV)** N·m/A. With this pairing, P = T·ω = Kt·I·ω = I·(rpm/KV) = I·E_LL,pk, so **I is the DC output current of a 3-phase bridge rectifier** (6-pulse, ideal, no overlap).
* **Copper loss:** at any instant two phases carry the DC current in series, so P_cu ≈ I_dc² · R_LL where **R_LL is the line-to-line resistance** (= 2·R_phase for a wye motor; what you measure between two leads). (Exact 120°-conduction result: I_ph,rms = I_dc·√(2/3), P_cu = 3·I_ph,rms²·R_ph = 2·R_ph·I_dc² = R_LL·I_dc².)
* **Rectified DC voltage:** V_dc ≈ E_LL,pk − I_dc·R_LL − 2·V_f, with V_f = 0.4 V (Schottky) assumed. Inductive (commutation) drop, iron and bearing losses ignored → results are slightly optimistic. Gimbal motors have high inductance (e.g. 4.78 mH/phase for the SteadyWin GB5210, 2.72 mH line-line for the GL60 KV25); at 650 rpm with 11–14 pole pairs (120–150 Hz) the line-line reactance reaches several ohms, comparable to R — measure L or test under load.
* **Useful figure of merit:** motor constant **Km = Kt / √R_LL** [N·m/√W]. Electrical efficiency at a point ≈ 1 − T/(Km²·ω) (ignoring diodes). The maximum torque a passive rectifier load can extract at speed ω is Km²·ω/2 (at 50 % efficiency). Required Km for this turbine:

| point | T/ω | Km for 50 % η | Km for 75 % η | Km for 90 % η |
|---|---|---|---|---|
| 1.0 m/s (0.18 N·m, 31.4 rad/s) | 0.0057 | 0.107 | 0.151 | 0.239 |
| 1.5 m/s (0.40 N·m, 49.7 rad/s) | 0.0080 | 0.127 | 0.179 | 0.284 |
| 2.0 m/s (0.72 N·m, 68.1 rad/s) | 0.0106 | 0.145 | 0.206 | 0.325 |

### 2.2 What the published GB5015 spec implies
Only one electrical fact is published: 220 mN·m at 14.8 V. If, as is usual for gimbal-motor listings, that is the **stall (holding) torque with 14.8 V across the leads**, then Kt·(14.8/R_LL) = 0.22, i.e. Kt/R_LL = 0.0149 N·m/V, and Km² = Kt²/R_LL = 0.0149·Kt. Any winding consistent with that spec has **Km ≤ ~0.08** (KV 25 → R_LL 25.7 Ω, Km 0.076; KV 54 → 12 Ω, Km 0.051; KV 107 → 6 Ω, Km 0.036). All are **below the 0.107 needed to absorb 0.18 N·m at 300 rpm at all**. Peer 50-60 mm, 24-slot, 12–24 V gimbal motors with published data have Km ≈ 0.09–0.14 (GM5208-24: 0.124 with 13.7 Ω; GM4108H-120T: 0.106; GB5210/XTG5210: ~0.14 if their 6 Ω is line-line), so the GB5015 *may* be better than its one-line spec suggests — but that can only be settled by measuring KV and R.

### 2.3 Operating-point tables (all three scenarios are **[A] assumed**)

**S1 — spec-implied, high-turn (KV 25, R_LL 25 Ω, Kt 0.382, Km 0.076)**

| point | rpm | T N·m | E_oc V | I_dc A | I²R W | V_dc | P_el W | η |
|---|---|---|---|---|---|---|---|---|
| 1.0 m/s | 300 | 0.18 | 12.0 | 0.47 | 5.6 | <0 | – | cannot absorb (max 0.09 N·m, 1.3 W at 300 rpm) |
| 1.5 m/s | 475 | 0.40 | 19.0 | 1.05 | 27.4 | <0 | – | cannot absorb (max 0.14 N·m, 3.3 W) |
| 2.0 m/s | 650 | 0.72 | 26.0 | 1.88 | 88.8 | <0 | – | cannot absorb (max 0.19 N·m, 6.4 W) |

Continuous torque at 5 / 8 W copper: 0.17 / 0.22 N·m. Runaway open-circuit DC: 24 V @ 590 rpm, 51 V @ 1270 rpm.

**S2 — spec-implied, mid-turn (KV 54, R_LL 12 Ω, Kt 0.177, Km 0.051):** cannot absorb any operating point; max 0.04 / 0.06 / 0.08 N·m (0.5 / 1.3 / 2.6 W) at the three speeds. Runaway 11 V / 24 V.

**S3 — "peer-class" winding like the iPower GM5208-24 (KV 21, R_LL 13.7 Ω, Kt 0.455, Km 0.123)** — valid only if the GB5015 is really better than its 220 mN·m line suggests:

| point | rpm | T N·m | E_oc V | I_dc A | I²R W | V_dc V | P_el W | η |
|---|---|---|---|---|---|---|---|---|
| 1.0 m/s | 300 | 0.18 | 14.3 | 0.40 | 2.1 | 8.1 | 3.2 | 56 % |
| 1.5 m/s | 475 | 0.40 | 22.6 | 0.88 | 10.6 | 9.8 | 8.6 | 43 % |
| 2.0 m/s | 650 | 0.72 | 31.0 | 1.58 | 34.3 | 8.5 | 13.4 | 27 % |

Continuous torque at 5 / 8 W copper: 0.27 / 0.35 N·m. Runaway 28 V / 60 V.

### 2.4 Thermal limit and the 2 m/s point
Assumed sealed-housing budget: 5–8 W continuous copper loss → T_cont = Km·√P. Even in the optimistic S3 case that is 0.27–0.35 N·m, so **the GB5015 cannot absorb 0.72 N·m at 2 m/s continuously** (34 W copper loss in S3; ~90–200 W in S1/S2). The turbine will run up toward a higher tip-speed ratio until torque falls to what the generator + charger current limit accept; the MPPT/charger must have a current limit and a dump/brake path.

Better thermal data found: Precision Microdrives 762-C01, a Ø62 × 25 mm slotted outrunner gimbal-type motor, publishes 4.9 °C/W housing-to-ambient and 1.2 °C/W winding-to-housing with 150 °C max winding (https://www.precisionmicrodrives.com/datasheets/762-C01-V1.pdf ; their 35 mm motor: 10 / 4.5 °C/W, https://www.precisionmicrodrives.com/datasheets/735-400-V1.pdf). In free air that is ≈20 W at 150 °C. In a water-cooled housing the housing-to-ambient term collapses, so if the stator base is thermally bonded to the wet wall, a 60–70 K rise could permit ~15–25 W; the 5–8 W figure is conservative and depends mainly on the stator-to-housing joint. Gimbal-motor duty is normally near-zero speed; see Olliw's note that for gimbals resistance, not KV, is the key parameter (https://www.olliw.eu/?p=14371).

---

## 3. Alternatives

### 3.1 Gimbal motors (50–70 mm class) and small gimbal motors

| Motor | Size, mass | Slots/poles | KV (rpm/V) | R_LL (Ω) | Kt / Km | Torque | Price / availability | η @1 m/s, @2 m/s (model) | Sources |
|---|---|---|---|---|---|---|---|---|---|
| **CubeMars GL60 KV25** | Ø69 × 22.3 mm, 230 g, 20 mm bore, IP45 [V] | [?] | 21.5 (also "25") [V/C] | 5.5 (also 4.6) [V/C] | 0.45 N·m/A [V] / Km 0.19 | 0.6 N·m rated @1.35 A, 310 rpm; 1.75 N·m peak @4 A [V]; L 2.72 mH LL | $141.99 (ca.robotshop) – $185 (upgraderc); €119.89 EU robotshop "re-stocking"; $159 rcdrone sold out | **78 %, 68 %**; absorbs all three points; T_cont(5–8 W) 0.42–0.54 N·m | https://www.cubemars.com/product/gl60-kv25-gimbal-motor.html ; https://www.robotshop.com/products/cubemars-gl60-kv25-brushless-dc-motor-w-o-encoder ; https://rcdrone.top/products/cubemars-gl60-kv25-brushless-gimbal-motor-large-hollow-shaft-low-cogging-ultralight-ip45-waterproof ; https://ca.robotshop.com/products/cubemars-gl60-kv25-brushless-dc-motor-w-o-encoder ; https://eu.robotshop.com/products/cubemars-gl60-kv25-brushless-dc-motor-w-o-encoder ; https://upgraderc.com/products/cubemars-gl60-outrunner-gimbal-motor ; https://www.directindustry.com/prod/cubemars/product-217143-2388955.html |
| **iPower/iFlight GM5208-24** | Ø59.5 × 31.2 mm, 204 g, 12.6 mm bore [V] | 24N22P [V] | ≈20.8 (no-load 396–436 rpm @20 V) [V→A] | 13.7 (iFlight) / 25.6 (uk.robotshop) [C] | 0.46 / Km 0.12 (13.7 Ω) or 0.09 (25.6 Ω) | 40 W max, 3–5S [V] | $42.99 in stock (iFlight), $56.81 (robotshop US), €51.90 (iFlight EU) | 57 %, 29 % (13.7 Ω); 25 %, cannot absorb 1.5/2 m/s (25.6 Ω) | https://shop.iflight.com/ipower-motor-gm5208-24-brushless-gimbal-motor-pro1347 ; https://www.robotshop.com/products/ipower-motor-gm5208-24-brushless-gimbal-motor ; https://uk.robotshop.com/products/ipower-motor-gm5208-24-brushless-gimbal-motor ; https://iflight-rc.eu/en/products/gm5208-24-gimbal-motor |
| SteadyWin GB5210 | 178 g (202 g w/ encoder); dims [?] | 11 pole pairs [V] | ≈28 (max 678 rpm @24 V) [A] | 5.94 "phase" (LL = 5.94 or 11.9) [C] ; L 4.78 mH | 0.30–0.34 / Km 0.14 or 0.10 | 0.46 N·m @1.56 A nominal, 1.03 N·m stall [V] | $25, backordered | 63 %, 43 % (if 5.94 LL); 34 %, cannot absorb 2 m/s (if 11.9) | https://aifitlab.com/products/steadywin-gb5210-motor ; https://www.roboticscenter.ai/store/product/steadywin-gb5210-motor/ |
| X-TEAM XTG5210 | 175.4 g [V] | 24N22P, 80 T [V] | [?] (28 assumed) | 6 [V] | Km ≈0.14 [A] | 12–24 V | [?] | 63 %, 42 % (assumed KV) | https://www.x-teamrc.com/?p=15687 |
| T-Motor GB54-1 (LIGPOWER) | Ø60.7 × 23–24 mm, 137 g, 12.7 mm hole [V] | 12N14P [V] | 33 [V] | 15.6 [V] | 0.29 / Km 0.073 | "torsion" 0.33 N·m, cameras to 1.8 kg [V] | $69.90 (T-Motor, irlock 4 left, ligpower); £64.52 backorder (robotshop UK) | cannot absorb any point (max 0.08 N·m @300 rpm) | https://store.tmotor.com/goods-444-GB54-1.html ; https://www.robotshop.com/products/ligpower-gb54-1-gimbal-type-3-6s-uav-drone-motor-kv33 ; https://rcdrone.top/products/t-motor-high-torque-low-speed-gimbal-motor-gb54-1-kv33 ; https://irlock.com/products/t-motor-gb54-1 ; https://www.getfpv.com/tiger-gb54-1-brushless-gimbal-motor-hollow-shaft.html |
| T-Motor GB54-2 | Ø60.7 × 25 mm, 156 g, 12.7 mm hole [V] | 12N14P [V] | 26 [V] | [?] ("150", units unstated; 16 Ω assumed) | Km ≈0.09 [A] | 0.45 N·m, 3–6S [V] | $74.90 (ligpower table); getfpv out of stock | 25 %, cannot absorb 2 m/s | https://www.robotshop.com/products/ligpower-gb54-2-gimbal-type-3-6s-uav-drone-motor-kv26 ; https://rcdrone.top/products/t-motor-high-torque-low-speed ; https://www.ligpower.com/categorys/gimbal-motor ; https://www.getfpv.com/tiger-gb54-2-brushless-gimbal-motor-hollow-shaft.html |
| T-Motor GB36-1 | Ø41.8 × 24.3 mm, 88 g, 8 mm shaft hole [V] | [?] | 50 [V] (one T-Motor page says KV26 [C]) | 15.6 (reseller) [V] | 0.19 / Km 0.048 | 0.24 N·m [V] | [?] | cannot absorb | https://store.tmotor.com/goods-441-GB36-1.html ; https://www.robotshop.com/products/ligpower-gb36-1-gimbal-type-3-6s-uav-drone-motor-kv50 ; https://rcdrone.top/products/t-motor-high-torque-gimbal-mot |
| iPower GM4108H-120T | Ø47 × 24 mm (32.3 mm w/ shaft), 124–125 g, 8 mm bore, 12 mm mount c-c [V] | 24N22P [V] | ≈27 (513–567 rpm @20 V) [V→A] | 11.1 [V] | 0.35 / Km 0.106 | 1200–1800 g·cm @1.5 A, 20 V [V] | [?] | 42 %, 3 % | https://iflight-rc.eu/products/gm4108h-120t-gimbal-motor ; https://www.robotshop.com/products/ipower-gbm4108h-120t-gimbal-motor |
| Flashhobby BGM5208-75T (sold as "GBM5208-75T") | Ø63 × 24 mm, 184 g, 5/7 mm hollow, M3 [V] | 24N22P, 75 T × 0.22 mm [V] | [?] (sibling 75HS ≈ 29–31 rpm/V no-load) | 15.0 [V] | Km ≈0.08 [A] | 75HS stall 0.15–0.37 N·m | [?] | 7 %, cannot absorb | https://www.unmannedtechshop.co.uk/products/bgm5208-75-brushless-gimbal-motor ; https://rcdrone.top/products/src-bgm5208-75t-gimbal-motor ; https://rcdrone.top/products/src-bgm5208-75hs-gimbal-motor |
| iPower GBM5208H-200T / -180T | 180T: Ø63 × 25 mm, 172 g, 12N14P, 10.2 Ω [V]; 200T: no specs captured [?] | | [?] | 10.2 (180T) | | | | | https://www.onedrone.com/store/ipower-gbm5208h-200t-hollow-shaft.html ; https://www.onedrone.com/store/tags/ipower |
| Flashhobby BGM5208-200HS | Ø63 × 24 mm, 185 g, 12 mm bore [V] | 12N14P [V] | [?] | 15 [V] | | | | | https://rcdrone.top/products/src-bgm5208-200hs-gimbal-motor |
| DYS BGM5208-200 (Evelta) / iPower GM5208 200T | 200 T × 0.27 mm, 12N14P [V]; Alibaba 200 T listing 15.5 Ω [V] | | "200KV" label [C, implausible] | 15.5 | | | | | https://evelta.com/brushless-outrunner-gimbal-motor-high-torque-low-noise-camera-stabiliser-for-rc-drone/ ; https://www.alibaba.com/product-detail/NEW-iPower-AlexMos-32-bit-GM5208_1601048210307.html |
| iPower GBM6208H-150T ("6208 gimbal") | Ø67 × 35 mm, 218 g [V] | 24N22P [V] | [?] (22 assumed) | 13.9 [V] | Km ≈0.12 [A] | | [?] | 52 %, 19 % | https://www.onedrone.com/store/tags/ipower ; https://shop.iflight.com/ipower-motor-gm6208-150t-brushless-gimbal-motor-pro208 |
| Rctimer GBM5010-150T ("5010 gimbal") | [?] | [?] | 90 (title) [V] | [?] | | | | too high KV, no data | https://rctimer.com/rctimer-gbm5010-150t-gimbal-brushless-motor-p0446.html |
| Copterlab GB5010 | 49 × 24 mm, 120 g, stator 43 × 10 [V] | | [?] | [?] | | 190 mN·m @14.8 V [V] | | same caveat as GB5015 | https://copterlab.com/5010-brushless-gimbal-motor-without-encoder |
| Emax GB4114 (42KV, 3S) | Ø46 mm, 4-M3 [V]; electrical [?] | | 42 [V] | [?] (BGM4114-100T sibling 15 Ω, 136 g, 46 × 30) | | | used only | not computable | https://www.unmannedtechshop.co.uk/products/emax-gb-4114-42kv-3s-gimbal-motor-pre-loved-good ; https://rcdrone.top/products/src-bgm4114-100t-8-5-gimbal-motor |
| Turnigy GBM4006-150T | 83 g [V] | 24N22P [V] | 35 [V] | 13.5 [V] | 0.27 / Km 0.074 | | HobbyKing | cannot absorb | https://hobbyking.com/en_us/turnigy-gbm4006-150t-brushless-gimbal-motor-bldc.html |
| Turnigy HD 5206 | 150 g [V] | 12N14P [V] | 42 [V] | 9.3 [V] | 0.23 / Km 0.075 | | HobbyKing | cannot absorb | https://hobbyking.com/en_us/turnigy-hd-5206-brushless-gimbal-motor-bldc.html |
| SparkFun ROB-27477 | 40 × 16 mm, 58.3 g [V] | [?] | 117 [V] | 6.34 [V] | 0.082 / Km 0.032 | stall 0.15 N·m @1.9 A; nominal 0.09 N·m @1.1 A [V] | $34.95 in stock | far too weak | https://www.sparkfun.com/products/27477 ; https://cdn.sparkfun.com/assets/d/6/b/5/8/27477_27478_Datasheet.pdf ; https://evelta.com/sparkfun-gimbal-motor-with-without-encoder-12v-467rpm |
| Precision Microdrives 762-C01 | Ø62 × 25 mm, Hall sensors, gimbal mount [V]; thermal data above | | [?] | [?] | | 3.0 A recommended limit (sibling sheet) | stocked design, 8-week availability [V] | not computable | https://www.precisionmicrodrives.com/?p=12779 ; https://www.precisionmicrodrives.com/datasheets/762-C01-V1.pdf |
| CubeMars GL80 KV30 / GL35 KV100 (for scale) | GL80: 315 g, 2.9 N·m peak; GL35: 90 g, 0.15 N·m, $54.99, IP45 | | 27 / 100 | | | | | | https://www.robotshop.com/products/cubemars-gl80-kv30-brushless-dc-motor-w-o-encoder ; https://store.cubemars.com/products/gl35 |

### 3.2 Low-KV multirotor outrunners (very low R, but voltage at 300 rpm is below the 3–4 V floor)

| Motor | Size, mass | KV | R_LL | Km | Price | η model (1 m/s / 2 m/s) and V_dc | Sources |
|---|---|---|---|---|---|---|---|
| T-Motor MN7005 KV115 | Ø79 × 21 mm, 188 g, 15 mm bore [V] | 115 [V] | 0.288 Ω (table ambiguous) [C] | 0.155 | $219.99 T-Motor/irlock; $153.99 getfpv | 45 % / 42 % but **V_dc only 1.2 V / 2.4 V** — unusable without a sub-3 V boost | https://store.tmotor.com/product/mn7005-kv115-motor-antigravity-type.html ; https://m.reach.dog/shop/robotshop-usa/products/tmotor-uav-brushless-motor-antigravity-mn7005-kv115 ; https://aws.robu.in/?p=1402971 ; https://www.getfpv.com/tiger-motor-antigravity-mn7005-115kv.html ; https://www.ligpower.com/product/mn7005-kv115-motor-antigravity-type.html |
| T-Motor U8 KV100 / U8 II KV100 | U8 II: 272–277 g [V]; diameter not captured (U8 family ≈87 mm [A]) | 100 [V] | 0.134–0.141 (U8) / 0.170 (U8 II) [V] | 0.26 | [?] | 65 % / 72 %, V_dc 1.9 / 4.7 V | https://uav-en.tmotor.com/2022/u_0311/786.html ; https://www.kopterworx.com/t-motor-u8-kv100.html ; https://rcdrone.top/products/t-motor-newest-u8-ii-kv85-kv10 |
| T-Motor MN8012 KV100 | 351 g [V]; ~Ø90 mm [A] | 100 [V] | 0.085 [V] | 0.33 | [?] | 68 % / 78 %, V_dc 2.0 / 5.1 V | https://irlock.com/products/t-motor-mn8012-antigravity-type-12s-uav-motor-kv100 ; https://www.ligpower.com/product/mn8012-motor-antigravity-type.html |
| Sunnysky X8318 KV100 | **no SunnySky datasheet found** [?]; an "HLY X8318S KV100/120, 36N40P" eBay listing exists | 100 | [?] | | | | https://www.ebay.de/itm/388782021654 |
| (reference) T-Motor P80 III KV100; SunnySky X8020S KV100 | 649 g, 45–51 mΩ; 57 mΩ | 100 | | | | far too big | https://cdn.robotshop.com/media/T/Tmo/RB-Tmo-279/pdf/ligpower_p80iii_kv100_pin_heavy_lift_agricultural_datasheet.pdf ; https://buddyrc.com/products/sunnysky-x8020-motors |

### 3.3 Hub motor (too large; one example)
6.5-inch hoverboard hub motor, 36 V 350 W: 30 poles / 15 pole pairs (https://docs.odriverobotics.com/v/0.5.5/hoverboard.html), measured KV ≈ 16–17 rpm/V and phase resistance 281 mΩ (https://forum.esk8.news/t/esk8-motor-dyno-results-database-no-words-no-pictures-just-graphs-serious/35617 ; https://discourse.odriverobotics.com/t/project-hoverarm/441/8), ~3 kg per wheel (https://robodo.in/products/6-inch-350w-36v-brushless-e-bike-wheels-scooter-hub-motor-for-self-balancing-scooters-hover-board-electric-and-self-balance-board), 800 rpm rated (https://www.shopabunda.com/products/6-5-inch-self-balancing-scooter-motor-wheel-with-tire-self-balance-2-wheels-unicycle-hover-board-motor-replacement). Model: Km ≈ 0.77, η ≈ 95 % at all three points, V_dc 17 / 28 / 38 V — electrically ideal, but Ø≈165 mm, ~3 kg, and user reports of noticeable detent torque (not quantified here). Hub-motor-as-hydro thread: https://endless-sphere.com/sphere/threads/hubmotor-hydro-generator.114090 .

### 3.4 Purpose-made PMGs / micro-hydro / coreless axial-flux
* ATO 100 W low-rpm PMG (ATO-PMG-NE100WS): 12/24/48 V, rated 750 rpm, 1 N·m rated, **0.1 N·m starting torque**, 3.1 kg, 140 W max; another ATO 100 W: 600 rpm, 1.36 N·m (https://ato.com/100w-alternator). Starting torque alone exceeds the turbine's 0.09 N·m static torque → will not self-start at 1 m/s.
* VXB 100 W 12/24 V PMG: 600 rpm rated, 130 W max, weatherproof (https://vxb.com/products/100w-12v-24v-permanent-magnet-generator-for-off-gr ; https://vxb.com/products/3-phase-gearless-permanent-magnet-generator-for-wi).
* VXB 300 W coreless axial-flux: cogging-free, starting torque < 0.1 N·m, 150–600 rpm direct drive, listed $649 (page also shows an inconsistent $1,090) (https://vxb.com/products/300w-coreless-axial-flux-permanent-magnet-wind-tur); comparable 300 W/600 rpm coreless units weigh 7.5–8.9 kg, Ø250 mm (https://rx-energy.en.made-in-china.com/product/GxTrMEayJZkS/China-300W-600rpm-Small-Axial-Flux-Coreless-Generator-Maglev-Wind-Generator.html). Far too large/heavy; rated speed matches, power 6× oversized.
* 54energy 100–300 W 3-phase PMGs (no rated rpm in snippet): https://54energy.net/products/100w-200w-12v-24v-3-phase-gearless-permanent-magnet-generator-wind-controller-for-wind-turbine-water-turbine-diy .
* "12 V micro hydro generator 10 W" (F50-series in-pipe units, DC output 5/12/80 V, 88 × 58 × 39 mm): integrated pipe turbine, not a bare generator (https://www.fruugo.us/12v-micro-hydro-generator-10w-small-water-turbine-for-offgrid-hydroelectric-power/p-450560229-949632840 ; https://www.fuelcellstore.com/micro-hydro-generator ; https://www.ato.com/12v-water-turbine).
* DIY coreless axial-flux: Windstuffnow kit (12 magnet pairs, 9 coils, 3-phase) — no volts/rpm found (https://www.utterpower.com/?p=3962 ; https://pic.hallikainen.org/piclist/2008/a/05/21/175518a.txt); Hugh Piggott axial-flux plans are metre-class (https://scoraigwind.com/homebrew.html). A custom coreless disc generator in Ø60 mm is feasible (zero cogging) but Km will be lower than a slotted gimbal motor of the same size; no off-the-shelf gimbal-size coreless unit was found [?].
* Motors-as-generators background: https://licm.mcgill.ca/default.aspx/G-qUNa/447282/Motors%20As%20Generators%20For%20Micro%20Hydro%20Power.pdf ; KidWind generator data https://www.vernier.com/files/kidwind/generator_data.pdf ; hydrokinetic rectifier+boost MPPT papers https://doaj.org/article/39787d19a7654810ae46123d112ef010 , https://scholarsmine.mst.edu/masters_theses/5207 ; Victron forum: 3-phase gen → bridge → BlueSolar MPPT 75/10 → 12 V, MPPT over-loaded the wheel, cap the current (https://communityarchive.victronenergy.com/questions/25471/strong-av-fluctuation-of-mppt-for-hydro.html); Hackaday gimbal-motor wind turbine (670 rpm at 10.5 km/h; motor model/output not captured) https://hackaday.io/project/185070/log/205886 .

---

## 4. Cogging / detent torque

Published numbers are rare and the two found have unit conflicts between vendor pages:
* CubeMars **GL40 II KV82.5** (rated 0.25 N·m): cogging reduced "from 1 cN·m to 0.7 cN·m" (https://www.cubemars.com/product/gl40-II-kv82-5-gimbal-motor.html) — rendered as "1 mN·m → 0.7 mN·m" on https://store.tmotor.com/product/gl40II-outrunner-gimbal-motor.html . 10→7 mN·m = 4→2.8 % of rated (my arithmetic).
* CubeMars **GL60 II KV28** (rated 0.6 N·m): "2.4 cN·m → 1.5 cN·m" (https://www.cubemars.com/product/gl60-II-kv28-gimbal-motor.html ; https://openelab.io/es/products/cubemars-gl60-ii-bldc-gimbal) vs "24 cN·m → 15 cN·m" on https://www.directindustry.com/prod/cubemars/product-217143-2761938.html . 24→15 mN·m (4→2.5 % of rated) is the physically plausible reading; 0.24 N·m would be 40 % of rated and not "low cogging". By implication the original **GL60 KV25 has ≈24 mN·m peak cogging** [A] — about 27 % of the 0.09 N·m available static torque.
* T-Motor GB2208/GB4106/GB54 pages only say "low cogging" and quote a "torsion" (holding torque) of 0.07 / 0.2 / 0.33–0.45 N·m, not cogging (https://store.tmotor.com/product/gb2208-gimbal-type.html ; https://www.ligpower.com/product/gb4106-gimbal-type.html).
* Research: METU paper on cogging rejection for a low-cost gimbal motor (30–65 % tracking-error reduction; amplitude not in abstract) https://open.metu.edu.tr/handle/11511/54998 ; Piccoli & Yim anticogging (up to 88 % ripple removal on eleven RC motors; amplitudes in PDF, not retrieved) https://www.modlabupenn.org/anticogging/ , https://www.modlabupenn.org/wp-content/uploads/piccoli_matthew_anticogging_torque_ripple_suppression_modeling_and_parameter_selection.pdf ; Kpower guide: ask the supplier for torque-ripple data or test a sample https://www.kpower.com/insight_gearbox/8004.html .
* Rule of thumb [A]: fractional-slot gimbal windings (24N22P: LCM 264 cogging cycles/rev; 24N28P: LCM 168; 12N14P: LCM 84) typically show peak cogging of ~1–4 % of stall torque → **≈2–10 mN·m for a GB5015-class motor, ≈15–25 mN·m for a GL60-class motor**. Both are below 0.09 N·m, but the **sealed-housing shaft seal and bearings add drag that can be of the same order** (a lip seal on a 10–12 mm shaft can add tens of mN·m) — budget total breakaway torque ≤ 0.03–0.045 N·m (≤ 50 % of 0.09) and measure it with the seal installed. A magnetic coupling or a fully flooded (oil-filled) housing with a low-drag seal avoids this.

---

## 5. Recommendation and required measurements

**Primary: CubeMars GL60 KV25** (Ø69 × 22.3 mm, 230 g). It is the only candidate with complete published generator-relevant data (Kt 0.45 N·m/A, 5.5 Ω, 0.6 N·m rated at 1.35 A, 1.75 N·m peak, 2.72 mH, IP45, 20 mm hollow shaft) and the only ≤70 mm motor whose Km (0.19) meets the 1 m/s point at ~78 % and absorbs the full 1.5 m/s point (74 %) and, thermally permitting, most of the 2 m/s point (68 %, 14.5 W copper). It exceeds the Ø60 envelope by 9 mm but is 13 mm shorter than the 35 mm allowance; the 20 mm bore is convenient for a sealed shaft or a magnetic coupling. Runaway open-circuit DC 27 V (1 m/s) / 59 V (2 m/s) — choose a boost/MPPT with ≥60 V input or add a crowbar/dump load. Cost ~$140–185.

**Backup: iPower/iFlight GM5208-24** (Ø59.5 × 31.2 mm, 204 g, 24N22P, $42.99 in stock). Fits the envelope exactly; if its line-to-line resistance is the iFlight-listed 13.7 Ω (Km 0.12) it delivers ~3.2 W at 57 % at 1 m/s and ~9 W at 1.5 m/s, with continuous torque 0.28–0.35 N·m; if it is 25.6 Ω (robotshop) it is marginal. Measure before committing. SteadyWin GB5210 / X-TEAM XTG5210 (6 Ω, ~178 g, $25) are equivalent-or-better on paper but KV/dimensions are unpublished and stock is backordered.

**GB5015:** cheap enough ($54.91) to buy and bench-test, but its only electrical spec (220 mN·m @ 14.8 V) implies Km ≤ 0.08, i.e. it could not load the turbine at 1 m/s at all. Keep it only if measured Km = Kt/√R_LL ≥ 0.11.

**Measurements the builder must make on the physical motor (any candidate):**
1. **KV:** spin with a drill at a known speed (optical tacho, or read the electrical frequency on a multimeter: rpm = 60·f / pole-pairs, pole pairs = magnets/2, counted); measure true-RMS line-to-line AC volts, KV ≈ rpm / (1.414·V_rms); or connect the actual 3-phase bridge and read open-circuit DC: KV = rpm / V_dc. Repeat at 2–3 speeds to check linearity; verify all three line pairs are equal (balanced winding).
2. **Line-to-line resistance** (all three pairs, note temperature): a bench multimeter is adequate for 5–25 Ω (subtract lead resistance); for sub-ohm motors inject ~0.5–1 A DC and measure the drop. Compute Km = 60/(2π·KV)/√R_LL and compare with the table above.
3. **Inductance** (LCR meter, line-to-line, 100 Hz–1 kHz) to quantify reactive drop at 650 rpm.
4. **Cogging/detent torque:** wrap a thread on a known-radius drum, pull with a digital spring scale (or add weights) and record the peak force needed to creep through a full revolution: T = F·r. Then repeat with the motor installed in the sealed housing (bearings + seal) to get total breakaway torque; target ≤ 0.03–0.045 N·m.
5. **Shaft/bore diameter, length, material, keyway/flat; mounting hole PCD, count, thread (expect M4 on GB5015, per SMC); overall Ø and height with leads.**
6. **Bearing axial play / preload** (dial indicator push-pull) and radial play; whether bearings are shielded/sealed, and plan for a thrust bearing to carry rotor axial load.
7. **Mass** (the GB5015 listings disagree: 120/135/155/165 g).
8. **Loaded test:** drive at 300 and 475 rpm into the bridge + resistive load; log V_dc, I_dc, torque (or drill current) and case temperature over 30–60 min at ~0.2–0.4 N·m to confirm the 5–8 W (or better) thermal budget inside the housing.

---

## Open questions
1. GB5015 KV, R_LL, L, pole count, bore, mass — all unpublished; the 220 mN·m @ 14.8 V figure's meaning (stall at 14.8 V, or at some rated current?) decides whether it is viable.
2. Does Copterlab actually sell an IP65 GB5015? No such page was found; CubeMars GL series is IP45. What does Copterlab's "IP65" cover (stator potting? bearings? lead exit?).
3. GM5208-24: 13.7 Ω (iFlight) vs 25.6 Ω (robotshop UK) — which is correct?
4. SteadyWin GB5210 / XTG5210: is the quoted 5.94 Ω / 6 Ω phase or line-to-line? KV and dimensions?
5. GL60 KV25: 5.5 Ω vs 4.6 Ω, KV 21.5 vs 25; pole count; its own (non-II) cogging torque (inferred ≈24 mN·m).
6. GL40 II / GL60 II cogging units (mN·m vs cN·m) — confirm with CubeMars.
7. Real shaft-seal + bearing drag in the chosen housing design vs the 0.09 N·m static torque.
8. Thermal path from stator to the wet housing wall — can 15–20 W be dissipated, allowing more of the 2 m/s torque to be absorbed?
9. Charger: input-voltage rating vs 59–61 V runaway (GL60/GM5208 class); current limit so the MPPT cannot stall the rotor; brake/dump strategy.
10. Not researched due to the search budget: MN5008-class 56 mm low-KV outrunners, PMD 762-C01 electrical data, Windstuffnow kit specs, Hackaday gimbal-wind output numbers, Piccoli/Yim measured cogging amplitudes.
