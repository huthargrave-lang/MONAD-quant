# Electrical components for the GL60 river-turbine generator — research v3 (2026-10-31)

**Access note.** In this cloud session the outbound proxy returned `403 CONNECT` for every manufacturer/distributor host tried
(cubemars.com, store.cubemars.com, vishay.com, digikey.com, mouser.com, littelfuse.com, victronenergy.com, morningstarcorp.com,
epever.com, hammfg.com, budind.com, andersonpower.com, robotshop.com, sunforgellc.com, emarineinc.com, cdn.shopify.com, …).
No page or PDF could be fetched directly. All "verified" values below were taken from the **web-search extract of the named URL**
(the search engine's cached text of that page), not from a fetched copy — treat as "verified via search snippet (URL)".
Re-fetch the primary PDFs before committing to a purchase. The user must allow those hosts in the session network settings
if direct verification is wanted.

Legend: **V** = verified via search snippet of the URL given; **E** = estimate/engineering calculation; **C** = conflicting sources.

---

## 0. Generator: CubeMars GL60 KV25 gimbal motor (used as 14-pole-pair PM generator)

Manufacturer page (blocked by proxy, 403): https://www.cubemars.com/product/gl60-kv25-gimbal-motor.html
Store page (blocked): https://store.cubemars.com/products/gl60-kv25

| Parameter | Value | Status / source |
|---|---|---|
| KV | 25 rpm/V | V (product name; https://www.cubemars.com/product/gl60-kv25-gimbal-motor.html) |
| Ke (back-EMF const.) | 44.30 V/krpm (KV25); 20.05 V/krpm (KV55) | V (https://aifitlab.com/products/cubemars-gl60-motor) |
| Kt | **0.45 N·m/A** (AifitLab) vs **0.4 N·m/A** (DirectIndustry, Alibaba) | C (https://aifitlab.com/products/cubemars-gl60-motor ; https://www.directindustry.com/prod/cubemars/product-217143-2388955.html ; https://www.alibaba.com/product-detail/CubeMars-GL60-25kv-55kv-High-Quality_1600210191573.html) |
| Phase-to-phase resistance | 5500 mΩ (5.5 Ω) | V (cubemars product page snippet / AifitLab) |
| Phase-to-phase inductance | 2720 µH | V (same) |
| Rated voltage | 24 V | V |
| No-load speed | 516 rpm | V (cubemars table) — C: rcdrone.top lists 1140 rpm no-load / 840 rated for a KV55-type listing |
| Rated speed / power | 310 rpm / 19.4 W (cubemars) ; 20 W (OpenELAB https://openelab.io/products/cubemars-gl60-bldc-gimbal) | V |
| Rated current / torque | 1.35 A / 0.6 N·m | V |
| Peak current / torque | 4 A / 1.75 N·m | V |
| Pole pairs / winding | 14 pole pairs; 24N28P; star (Y) winding, FOC | V (https://www.alibaba.com/product-detail/CubeMars-GL60-25kv-55kv-High-Quality_1600210191573.html) |
| Mass | 230 g (cubemars) ; 226 g (rcdrone, KV55 variant) | V/C |
| Dimensions | Ø69 × 22.3 mm | V (https://www.robotshop.com/products/cubemars-gl60-kv25-brushless-dc-motor-w-o-encoder) |
| Rotor inertia | 355 g·cm² | V (https://eu.robotshop.com/nl/products/cubemars-gl60-kv25-borstelloze-dc-motor-z-o-encoder) |
| Hollow bore | **20 mm through-bore** ("large hollow shaft") | V (cubemars page snippet; https://rcdrone.top/products/cubemars-gl60-kv25-brushless-gimbal-motor-large-hollow-shaft-low-cogging-ultralight-ip45-waterproof) |
| Mounting holes | 4 × M3 on PCD 40 mm **and** 4 × M2.5 on PCD 50 mm (which pattern is on the stator base vs. rotor bell is **not stated**) | V-secondary (https://servodatabase.com/servo/cubemars/gl60-kv25) — NOT FOUND on primary |
| IP rating | IP45 | V-secondary only (rcdrone.top listing title) — not seen on cubemars snippet |
| Price | US$126.70 (RobotShop, w/o encoder, sale incl. US tariffs); US$138.99 with encoder (https://ozrobotics.com/product-category/motors/gimbal-motors/); from US$159 (rcdrone.top); US$132.99–160.99 (https://openelab.com/collections/cubemars-gimbal-motors-systems) | V |
| Product revision | Original "GL60 KV25" (Ø69×22.3, 230 g) still sold; a newer **GL60 II KV28** exists (Ø70.5 × 33.6 mm, 276 g, 20 mm bore, 4-M3 holes on Ø40, CAN/PWM driver built in): https://www.cubemars.com/product/gl60-II-kv28-gimbal-motor.html | V |
| Drawing / STEP | "GL60-Motor Installation Dimension Drawing.pdf" + STEP referenced on the AifitLab listing — not retrievable here | NOT FOUND |

**Not found on any reachable source:** which hole pattern is on the stator base vs. rotating bell face; thread depth; official IP rating; official Kt (0.40 vs 0.45).

Derived (E): with Rll = 5.5 Ω, Lll = 2.72 mH, 14 pp → at 700 rpm (163 Hz) Xll ≈ 2.8 Ω, |Z| ≈ 6.2 Ω; a 3-phase short at full speed draws ≈ 5 A transiently (≈ 9 A in the 3 m/s flood case). Because Kt·I_sc ≫ turbine torque, a shorted generator slows until I ≈ T_turbine/Kt ≈ 0.65/0.45 ≈ **1.4 A** — so a shorting brake is thermally benign in steady state (≈ 3·1.4²·2.75 Ω ≈ 16 W copper loss).

---

## 1. Rectifier

### 1a. Vishay VS-26MT / VS-36MT three-phase bridge modules (D-63, push-on terminals)
Family datasheet Vishay doc 93565 (vishay.com blocked). Mirrors: https://www.radiolocman.com/datasheet/pdf.html?di=184487 ; https://www.farnell.com/datasheets/2049266.pdf ; https://www.vishay.com/en/product/93565/
- **Voltage code = VRRM/10: "20" = 200 V, "40" = 400 V, "100" = 1000 V.** So **VS-26MT100 is a 1000 V part, not 100 V** — V (https://www.tme.eu/gb/details/vs-26mt100/three-phase-diode-bridge-rectifiers/vishay/ ; https://my.rs-online.com/web/p/bridge-rectifiers/1652874 ; https://novapart.co/products/VS-26MT100/bridge-rectifier-three-phase-1-kv-25-a-module-5)
- IO = 25 A (26MT) / 35 A (36MT); IFSM = 360 A — V
- **VFM = 1.26 V max per junction at IFM = 40 A peak, 25 °C** (standard-recovery silicon, not Schottky) — V (https://www.scribd.com/document/701044862/Vs-36mtseries ; https://datasheet.eeworld.com.cn/view/22708847.html)
- Vf at 1–2 A: ~0.7–0.8 V per diode (E, silicon PN at low current) → ≈1.5 V total bridge drop, ≈ 6–10 % of a 15–24 V bus. Acceptable but Schottky is better.
- Price: VS-26MT40 (400 V, 25 A) ≈ US$10.54–15.45 (DigiKey 112-VS-26MT40-ND) / US$12.99–20.12 (Mouser); VS-26MT20 (200 V) ≈ US$10.94–15.84 — V (https://findchips.com/search/26MT40 ; https://www.findchips.com/search/26mt20)
- Recommendation: if a module is wanted, use **VS-26MT20 (200 V)** or **VS-26MT40 (400 V)**; there is no 100 V code and no Schottky version of this module.

### 1b. Discrete Schottky, six × MBR10100 (100 V, 10 A, TO-220AC)
- onsemi MBR10100G: 100 V, 10 A, Tj −65…175 °C, IR 100 µA @ 100 V; ≈ €0.61 — V (https://www.digikey.nl/en/products/detail/onsemi/MBR10100G/918577)
- Diotec MBR10100: VF max 0.80 V @ 10 A, IR 5 µA @ 100 V — V (https://www.digikey.sg/en/products/detail/diotec-semiconductor/MBR10100/22193406)
- Panjit MBR10100-T0-00001: 800 mV @ 10 A; £0.72 ea (1), ~£0.20 @1k — V (https://www.digikey.co.uk/en/products/detail/panjit-international-inc/MBR10100-T0-00001/14661036)
- Vishay MBR10100-E3/4W: VF max 0.80 V @ 10 A, 25 °C; €2.04 — V (https://www.digikey.co.uk/en/products/detail/vishay-general-semiconductor-diodes-division/MBR10100-E3-4W/2153157 ; https://pdf.elecfans.com/TFUNK/MBR10100-E3--4W.html)
- **Vf at 1–2 A: NOT FOUND numerically** in any reachable extract (only in Fig. 3 curves); estimate **0.50–0.60 V at 1–2 A, 25 °C** (E) → ≈ 1.1 V total bridge drop.
- SB10100 (SMC Diode Solutions): VF 0.75 V typ / 0.85 V max @ 10 A — V (https://www.SMC-Diodes.com/propdf/SB10100%20N1492%20REV.A.pdf)
- STPS10H100CT (ST, 100 V, 2×5 A common-cathode TO-220): VF max 0.61 V @ 5 A — V (https://manualmachine.com/datasheet/stps10h100ct/8426862-datasheet-st). Common-cathode only; usable for the three upper diodes, not the lower three.
- SBR10100CTB (Diodes): 0.84 V @ 5 A, 100 V — V (https://elcodis.com/parts/3727645/SBR10100CTB_p2.html)
- "STPS10100" as a plain single-diode part number: NOT FOUND.

### 1c. Diodes Inc SB560 — confirmed **60 V, 5 A, VF 0.67 V max @ 5 A** → **unsuitable** (open-circuit DC 59 V at 2 m/s, ~88 V flood exceeds VRRM)
V (https://uk.rs-online.com/web/p/schottky-diodes-rectifiers/1223395 ; https://www.element14.cn/en-CN/diodes-inc/sb560-t/schottky-rectifier-60v-5a-do-201ad/dp/3944929). Note onsemi's SB560 is obsolete (https://www.digikey.de/en/products/detail/onsemi/SB560/1052003).

**Selection:** six × MBR10100 (any of onsemi/Vishay/Diotec/Panjit) on a small heatsink, ≈ US$4–6 total; 100 V VRRM covers 88 V flood Voc with the TVS clamping transients.

---

## 2. Charge controllers (rectified PM-generator input 10–60 V → 12 V battery)

| Controller | Topology | Input range / max | Max charge current & power | Efficiency | Standby | Price (USD) | Current-source behaviour | Verdict |
|---|---|---|---|---|---|---|---|---|
| **Genasun GVB-8-Pb-12V** (boost MPPT) | **Boost only** | Min panel voltage 5 V; **max input 60 V**; recommended Voc ≤ 50 V (STC); input range 0–60 V; min battery 9.5 V; rated input current 8 A, max input short-circuit 8 A / max input current 15 A | 8 A input-rated; 105 W (12 V model) | 96–99 % peak (claims) | 5–7 mA (Li-36V model listing) | US$125–190 (practicalpreppers); AUD 193.50–215 (solar4rvs) | Hardware input-current limit 8 A; manual flag "overloaded and limiting input current". **Boost cannot regulate when Vin > Vbat**: with this generator's Voc 27–88 V always above 12.8 V, current would flow uncontrolled through the boost inductor/diode into the battery, loading the generator at ≈ Vbat (E — the "Vin>Vbat" clause was NOT found verbatim in a reachable manual extract). | Unsuitable alone |
| Sources | | V: https://www.solar4rvs.com.au/assets/brochures/GVB-8-Pb-36V-WP.pdf ; https://www.solar4rvs.com.au/assets/brochures/GVB-8-Pb-24V.pdf ; https://cdn.shopify.com/s/files/1/0062/2959/0114/files/Genasun_GVB-8_Datasheet-ETL-2018.pdf ; https://practicalpreppers.com/?p=17642 ; https://www.solar4rvs.com.au/products/genasun-8a-mppt-12v-voltage-boost-for-lead-acid-waterproof ; manual: https://cdn.shopify.com/s/files/1/0756/6913/files/GVB-8-WP_Manual.pdf | | | | | | |
| **Genasun GV-10-Pb-12V** (buck MPPT) | Buck | **Max input 34 V**; recommended Voc ≤ 27 V (STC); input 0–34 V | 10.5 A; 140 W | 98.3 % peak | 0.9 mA | US$110 (Sunforge list; eMarine) | MPPT P&O; no published non-PV guidance. 34 V max is below Voc at ≥1.5 m/s (44 V) → would be destroyed unless pre-clamped. | Unsuitable |
| Sources | | V: https://sunforgellc.com/wp-content/uploads/2022/06/GV-10-PCB_Data-Sheet-rev-01-2021_AP.pdf ; https://cdn.enfsolar.com/Product/pdf/ChargeController/5a2ae9153b06b.pdf ; https://emarineinc.com/products/genasun-mppt-solar-controller-10-5a-input-12v-output ; https://sunforgellc.com/?p=133 | | | | | | |
| **Victron SmartSolar MPPT 75/15** | Buck only | **Max PV Voc 75 V**; **"PV voltage must exceed Vbat + 5 V for the controller to start; thereafter minimum PV voltage is Vbat + 1 V"**; 12/24 V auto | 15 A; 220 W @ 12 V | ~98 % max (E) | ~12 mA (E; not verified — Scribd copy shows 19/16 mA with ambiguous columns) | US$120.99 (Zoro), US$130.68 (Portlandia, sold out), US$67.15 (solaris-shop, currency unstated) | P&O tracker with periodic full sweep; when it pulls more than the turbine gives the bus sags, measured power falls and it backs off (E). Below MPP < Vbat+1 V it stops and the turbine freewheels (safe at 1 m/s Voc 27 V). **75 V limit is below the 88 V flood Voc** → dump must engage first. | Candidate (with dump) |
| Sources | | V: https://cdn.shopify.com/s/files/1/2510/0896/files/Datasheet-SmartSolar-charge-controller-MPPT.pdf ; https://www.scribd.com/document/370348010/victron-mppt ; https://community.victronenergy.com/questions/85108/is-this-real-no-charging-until-pv-bat-5v.html ; https://www.zoro.com/victron-energy-smartsolar-mppt-7515-retail-scc075015060r/i/G100446552 ; https://www.portlandiaelectric.supply/products/smartsolar-mppt-75-15 | | | | | | |
| **Victron SmartSolar MPPT 100/15** | Buck only | **Max PV Voc 100 V** (covers 88 V flood); same Vbat+5 V start rule | 15 A; 220 W @ 12 V / 440 W @ 24 V | same | same | **US$82.45 (solar-electric.com), US$89.97 (solarcellzusa)** | as 75/15 | **Preferred buck candidate** |
| Sources | | V: https://solarkontor.de/en/products/victron-smartsolar-mppt-100-15-bluetooth-integriert ; https://solarhouse.bg/wp-content/uploads/2024/07/Datasheet-SmartSolar-charge-controller-MPPT-75-10-75-15-100-15-100-20_48V-EN.en_.bg_.pdf ; https://www.solar-electric.com/victron-energy-smartsolar-mppt-100-15-charge-controller.html ; https://store.solarcellzusa.com/products/victron-energy-smartsolar-mppt-100-15 | | | | | | |
| **Morningstar SunSaver MPPT SS-MPPT-15L** | Buck | **Max solar input 60 V** per Morningstar quick-start guide (retailer titles say "75 VDC" — C); battery 7–36 V | 15 A; 200 W @ 12 V (E) | 97.5 % (E) | 35 mA (E) | US$295–342.70 (MSRP $379) | TrakStar P&O; manual says array voltage must never exceed max input. 60 V = 59 V Voc at 2 m/s → **no margin**, 88 V flood kills it. | Unsuitable |
| Sources | | V: https://morningstarcorp.com/products/sunsaver-mppt/quick-start-guide-sunsaver-mppt-en ; https://www.portlandiaelectric.supply/pages/specs-ss-mppt-15l ; https://solartown.com/solar-products/morningstar-sunsaver-ss-mppt-15l-mppt-charge-controller/ ; https://www.solacity.com/product/morningstar-sunsaver-ss-mppt-15l/ | | | | | | |
| **EPEver Tracer2210AN (G3)** | Buck | **Max PV Voc 100 V** (at min operating temp; 92 V @ 25 °C); 12/24 V auto | 20 A; 260 W @ 12 V / 520 W @ 24 V | 98 % max (E) | < 10 mA (G3); older AN: 98 mA @12 V | US$70–90 | P&O with periodic sweep; same current-source caveat as Victron; no non-PV guidance published. Cheapest 100 V-input option. | Alternative buck |
| Sources | | V: https://b2b.100mega.com/en/334540-epever-tracer2210an-g3 ; https://manuals.plus/asin/B071GRK4J8 ; https://cdn.shopify.com/s/files/1/0245/5633/9234/files/Tracer-AN_spec.pdf ; https://solarspechub.pages.dev/charge-controllers/epever/epever-tracer-2210an | | | | | | |
| **Generic "MPPT wind-turbine boost controller" 300–800 W, 12/24 V (Pikasola, MarsRock MPPT060, unbranded IP67)** | Boost from 3-phase AC in (built-in rectifier) | Max input stated as "AC 35 V" (800 W unit); braking at 14.5 V/29 V (12/24 V) battery; **no DC-input Voc limit published** | 15 A @12 V / 10 A @24 V; "max input current 25 A dc after rectification" (600 W unit) | unstated | unstated | ~US$40–90 (marketplace, E) | Designed for current-source turbines (they brake by shorting the generator at a battery-voltage threshold). But input limit 35 VAC (~50 V DC) is below the 59–88 V Voc and specs are unverifiable. | Not recommended |
| Sources | | V: https://www.fruugo.us/mppt-wind-turbine-charge-controller-800w-12v-24v-boost-charging-waterproof-ip67-auto-voltage-detection/p-460138949 ; https://ibspot.com/products/pikasola-mppt-wind-turbine-charge-controller-wind-generator-controller-12v-24v-auto-match-mppt-controller-ip67-waterproof-suitable-for-400watt-600watt-wind-turbine-generator ; https://manuals.plus/ae/1005002571590104 ; https://54energy.net/products/charge-controller-for-wind-turbine-max-600w-and-300w-solar-panel-waterproof-battery-controller-24v-48v-r-amp-x-mppt | | | | | | |
| **PowerSpout (hydro-specific)** | n/a — PowerSpout sells turbines, not small controllers | ME models pair with PV MPPT controllers (Outback FM60 for 140 V, MidNite Classic 250); PLT needs a diversion ("load dump") controller; turbine has an internal fast electronic 120 V dump element | — | — | — | — | Confirms the architecture: PV-type MPPT + independent dump. | Reference only |
| Sources | | V: https://cdn.shopify.com/s/files/1/0755/7165/9042/files/PowerSpout_Product_Listings.pdf ; https://aurorapower.net/powerspout-hydro-turbine-plt/ ; https://aurorapower.net/files/2020/06/PS-install-manual-2014.pdf | | | | | | |
| **LTC3780 generic buck-boost module** | 4-switch buck-boost, CV/CC | **Input 5–32 V**; output 1–30 V adj. | 10 A peak / 7–8 A continuous; 130 W peak, 80 W sustained (fan above 80 W) | "up to 98 %" (vendor claim) | unstated | €21.57 (OnBuy); US$16–17 at 25+ (Electropeak); CAD 64 (Fruugo) | CC limit is on the output, not the generator; **32 V max input** is below Voc at ≥1.5 m/s → needs a pre-clamp. No MPPT. | Only as a bench experiment |
| Sources | | V: https://www.onbuy.com/ie/p/ltc3780-automatic-buck-boost-power-module-solar-car-voltage-regulator-constant-voltage-constant-current-10a~p245267095/ ; https://electropeak.com/ltc3780-automatically-voltage-current-regulator ; https://components101.com/modules/ltc3780-dc-dc-step-up-module | | | | | | |

**Conclusion.** No small commercial MPPT charger offers true buck + boost over a 10–60 V input. Realistic options: (a) **Victron SmartSolar 100/15** (buck; loses the low-flow region where MPP < Vbat + 1 V ≈ 14 V, i.e. roughly < 1 m/s) + independent dump; or (b) a defined combination: Victron 100/15 as the main charger and a GVB-8 is *not* a safe parallel partner (boost conducts uncontrolled when Vin > Vbat). (c) EPEver 2210AN as a cheaper (a).

---

## 3. Over-voltage / overspeed protection (independent of the charger)

### 3a. Dump-load resistor (chassis-mount, aluminium-housed, 100 W on heatsink)
| Part | Rating | Price | Source |
|---|---|---|---|
| Ohmite **HS100 15R J** (DigiKey HS10015RJ-ND) | 15 Ω ±5 %, 100 W wirewound chassis mount | £10.96 (1), £7.67 (10); AUD 18.43; lead 15–24 wk | V https://www.digikey.co.uk/en/products/detail/ohmite/HS100-15R-J/5307072 |
| TE Connectivity **HSC10015RJ** | 15 Ω 5 % 100 W, aluminium housing | US$16.87 (1), US$8.93 (100) (digikey.com.br) | V https://www.digikey.com.br/en/products/detail/te-connectivity-passive-product/HSC10015RJ/2366348 |
| Arcol **HS100 15R J** | 15 Ω 100 W | £7.95 ex VAT (Rapid 62-8190); £9.87 (RS) | V https://www.rapidonline.com/arcol-hs100-15r-j-100w-aluminium-clad-resistor-62-8190 ; https://uk.rs-online.com/web/p/chassis-mount-resistors/1663825 |
| Derating | 100 W only on the standard heatsink at 25 °C; **≈ 30 W without heatsink** (distributor-reported) | — | V https://www.electrokit.com/upload/product/41013/41013430/kmHS_data_e2.pdf ; https://pt.farnell.com/arcol/hs100-3r-f/resistor-wirewound-3r-1-solder/dp/2678734 |

Sizing (E): 15 Ω at a 45 V engage threshold → 3 A / 135 W transient, settling at the turbine's power limit (≈ 60 W at 2 m/s → ≈ 30 V, 2 A — slightly above the 1.5 A short-term limit). A 33 Ω resistor settles at ≈ 44 V / 1.35 A (rated current) at 2 m/s but allows ≈ 80 V in a 200 W flood. **Compromise: two 33 Ω 100 W in parallel (16.5 Ω, 200 W)**, or 15 Ω per the brief with the brake as the flood backstop. Mount on a ≥ 1 °C/W heatsink (E) or bolt to the submerged/wet enclosure wall.

### 3b. Dump-load controller / crowbar
| Option | Key data | Price | Source |
|---|---|---|---|
| **Generic "DC 6–80 V voltage monitoring relay module"** (SPDT relay, adjustable upper/lower limits 0–99.9 V, ±0.1 V, 0–999 s delay; over/under-voltage modes) | Supply 6–80 V; set engage ≈ 45 V / release ≈ 35 V; relay drives the dump resistor (or a logic-level MOSFET for PWM-free switching) | ≈ US$8–15 (E; marketplace) | V https://www.fruugo.ie/dc-680v-voltage-monitoring-relay-time-delay-relay-charging-discharge-controller-module/p-334463426 ; https://www.fruugo.co.nz/voltage-detection-relay-switch-controller-for-6-80v-dc-with-protective-case/p-416414507-878702399 |
| Lettel **CRV1-DC24** DIN-rail voltage monitoring relay | thresholds 20–80 VDC, hysteresis 3 % | not found | V https://www.directindustry.com/prod/lettel/product-4614625-2807464.html |
| **Morningstar TriStar TS-45** in diversion mode | 45 A diversion, 12/24/48 V, max 125 V input, PWM to setpoint; needs a battery (min 9 V) on its "battery" terminals | US$219.20–243 (MSRP $274) | V https://thesolarstore.com/products/morningstar-tristar-ts-45-pwm-solar-charge-controller-45-amp-12v-24v-48v-no-digital-display ; https://rspsupply.com/p-8570-morningstar-ts-45-charge-controller-122448v-45a.aspx ; https://www.morningstarcorp.com/wp-content/uploads/datasheet-tristar-en.pdf |
| **APRS World DL300** (APRS8400) | 12/24 V PWM dump controller + 300 W resistor in steel box | US$150 | V https://www.environmental-expert.com/products/dump-load-897251 |
| Coleman Air **C440-HVAD** | 150 A continuous / 440 A surge diversion, 12/24/48 V, min 10.5 V | price NOT FOUND | V https://manualshive.com/en/manual/coleman-air/c440-hvad/2637062 |
| Discrete crowbar (E) | TL431 + 2N7000 driving a 100 V logic MOSFET (e.g. IRLZ44N) with 5 % hysteresis, 1.5KE62A as backstop | < US$5 | E |

The TS-45/DL300/C440 are **battery-side** diversion controllers (classic wind/hydro) and are overkill for 60 W; the 6–80 V relay module on the **generator DC bus** is the right scale and independent of the MPPT charger.

### 3c. 3-phase short-circuit brake switch
| Part | Rating | Price | Source |
|---|---|---|---|
| **NKK S32F** 3PDT toggle, panel mount | **20 A AC/DC; 30 V DC / 125 V AC**; 25,000 cycles | US$12.73 (ichome), ~US$20 (Cytech), SGD 27.56 (RS) | V https://www.digikey.be/en/products/detail/nkk-switches/S32F/1007143 ; https://ichome.com/product-detail/nkk-switches/s32f ; https://au.rs-online.com/web/p/toggle-switches/1959265 |
| Deligo PV DC rotary isolator 16 A, 1200 V (pole count unconfirmed) | DC-rated | £19.99 ex VAT | V https://www.electrical4less.co.uk/product/deligo-photovoltaic-solar-dc-rotary-isolator-switch-16a/ |
| "60 A brake switch for 3-phase AC wind turbines" (marketplace) | AC only | not found | V https://www.desertcart.ma/products/91273589 |

Use: wire S32F so that in "BRAKE" all three phases are tied together (3 poles → common bus) upstream of the rectifier. Closing at full speed carries ≈ 5 A transient then ≈ 1.4 A steady (E). **Opening** the brake (release) interrupts ≈ 1.4 A DC-like inductive current at near-zero volts, then voltage rises as the rotor spins up — mild arcing; the 30 V DC contact rating is exceeded only in the open-circuit state, where the switch is not interrupting current. A 3-pole DC-rated (≥ 60 V) rotary isolator was NOT FOUND at low voltage; the PV isolators (1000–1200 V DC) are the fallback.

### 3d. TVS across the DC bus
| Part | VRWM | VBR min/max | VC @ Ipp | Ppk | Price | Source |
|---|---|---|---|---|---|---|
| Littelfuse **SMCJ58A** (DO-214AB) | 58 V | 64.4 / 71.2 V | 93.6 V @ 16.1 A | 1500 W | CAD 0.42 (1); US$0.19–0.23 (LCSC/IBS) | V https://www.digikey.ca/en/products/detail/littelfuse-inc/SMCJ58A/762416 ; https://www.lcsc.com/product-detail/C409417.html |
| Littelfuse **1.5KE62A** (DO-201) | 53 V | 58.9 / 65.1 V | 85 V @ 17.9 A | 1500 W | ≈ US$0.5–1 (E) | V https://web.eecs.utk.edu/~dcostine/ECE482/components/parts/PartsKit/datasheets/F5624CT-ND.pdf ; https://www.tanotis.com/collections/circuit-protection/products/littelfuse-1-5ke62a-tvs-diode-1-5kw-62v-do-201 |
| Littelfuse **5KP60A** (P600) | 60 V | 66.7 / 73.7 V | 96.8 V @ 52.7 A | 5000 W | US$1.29–1.78 (100+/500+); €1.21 @100 | V https://uk.farnell.com/littelfuse/5kp60a/tvs-diode-unidir-60v-p600/dp/3930088 ; https://www.digikey.de/en/products/detail/littelfuse-inc/5KP60A-B/3427896 |

Note (E): a TVS is a pulse device — it must **not** be the steady-state limiter. With the dump engaging at ≤ 50 V and the brake as backstop, the 58–60 V standoff parts never conduct continuously; the 88 V flood Voc must be caught by the dump before the TVS (otherwise the 1.5 kW part fails short within seconds). Prefer 5KP60A for margin.

---

## 4. Fusing, connectors, enclosure

| Item | Part | Rating | Price | Source |
|---|---|---|---|---|
| Battery fuse | Littelfuse **0287005.PXCN** ATO/ATOF 5 A 32 V fast-acting | 5 A, 32 V | US$0.44 (DigiKey via aggregator); US$0.11 @5 (LCSC) | V https://octopart.com/part/littelfuse/0287005.PXCN ; https://www.lcsc.com/product-detail/Automotive-Fuses_Littelfuse-0287005-PXCN_C142682.html |
| Inline holder | Littelfuse **FHAC0001ZXJ** (splash-waterproof) | 20 A / 32 V (heavy-duty FHAC0002 / 0FHA0001HXGLO = 30 A) | €5.85 (Farnell), US$6.08 (Wirecare), US$8.70 (Waytek 30 A) | V https://ie.farnell.com/littelfuse/fhac0001zxj/fuse-holder-20a-32v-wire-leaded/dp/2762072 ; https://waytekwire.com/product/littelfuse-ato-atc-in-line-fuse-holder |
| Battery/charger connectors | Anderson Powerpole **1327 (red) + 1327G6 (black)** housings, **1331** 30 A contacts (16–12 AWG), 600 V | 30 A | contacts US$0.85 (Del City, 1), US$0.32 (Waytek, 40); housings ≈ US$0.8–1.6 ea (eBay kits 15 pr $24.99) | V https://www.delcity.net/store/battery-cables-accessories/anderson-sb-powerpole-connectors/contacts/30-amp-powerpole-items/5631/ ; https://www.waytekwire.com/product/anderson-power-1331-bk-16-12-ga-pp30 ; https://www.powerwerx.com/anderson-powerpole-colored-housings — **Powerpole is IP20, not waterproof** |
| Waterproof generator connector | Weipu **SP13** 2-pin (SP1312/S2-N socket, SP1310/P2 plug; 3-pin SP1312/S3-N for the 3 phases) | 13 A, 250 V, **IP68** | US$4.17 (2-pin), US$4.55 (3-pin) (TME); €3.59 (DigiKey SP1311/P2I-C) | V https://www.tme.com/in/en/details/sp1312_s2/weipu-connectors/weipu/sp1312-s2-n/ ; https://www.tme.com/in/en/details/sp1312_s3/weipu-connectors/weipu/sp1312-s3-n/ ; https://www.digikey.nl/en/products/detail/weipu-connector/SP1310-P2I-N/19084897 |
| Alt. waterproof connector | Bulgin Buccaneer 400 **PX0410/02P/5560** plug + PX0410/02S/5560 socket | **8 A** (2–3 pole), 250 V AC/DC, IP68 (10 m, 2 weeks), cable 3–7 mm | £9.35 ex VAT (plug) | V https://www.rapidonline.com/bulgin-px0410-02p-5560-400-series-buccaneer-2-pole-flex-cable-connector-plug-51-4343 ; https://uk.rs-online.com/web/p/industrial-circular-connectors/4260953 |
| Enclosure | Hammond **1554F2GY** polycarbonate | **IP68**, 119.4 × 88.6 × 61 mm (4.7 × 3.5 × 2.4 in) | US$22.16 (Farnell IL), AUD 31.66 (RS) | V https://il.farnell.com/hammond/1554f2gy/enclosure-polycarbonate/dp/4080932 ; https://au.rs-online.com/web/p/general-purpose-enclosures/8685066 ; https://www.digikey.tw/en/product-highlight/h/hammond/1554-1555-series |
| Alt. enclosure | Bud Industries **NBF-32004** ABS | NEMA 4X, IP65/IP66; 150 × 99.5 × 70.6 mm | US$12.46 (TestEquity) | V https://www.testequity.com/product/10013560-NBF-32004 ; https://www.digipart.com/part/NBF-32004 |
| Cable glands | **PG7 nylon IP68, 3–6.5 mm** (RS PRO 269-1824; Essentra CG-PG7-2; Jacob 50.007 PABSSW; Altronics H4304A) | IP68 | £26.64 / 25 (RS); AUD 2.90 ea (Altronics); £0.54 @100 (Essentra) | V https://uk.rs-online.com/web/p/cable-glands/2691824 ; https://www.digikey.co.uk/en/products/detail/jacob-gmbh/50-007-PABSSW/11674493 ; https://www.altronics.com.au/p/h4304a-3-6.5mm-eg7-pg7-black-ip68-cable-gland |

---

## 5. Schematic (text) and operating logic

```
GL60 KV25 (3-ph, Y, 14 pp)                       
  U ──┬─────────────────────┐                      
  V ──┼──┐  BRAKE SW (NKK S32F, 3PDT)              
  W ──┼──┼──┐  "RUN": phases pass through          
      │  │  │  "BRAKE": U,V,W tied together        
      ▼  ▼  ▼                                      
   3-ph bridge: 6 × MBR10100 (100 V Schottky) or VS-26MT20/40 module
      │ DC+                                        
      ├── TVS 5KP60A (or SMCJ58A) to DC−           
      ├── 6–80 V voltage-monitor relay (engage ≈45 V, release ≈35 V) ─► dump resistor 15 Ω/100 W (or 2×33 Ω) on heatsink ─► DC−
      ├── (bus voltmeter / shunt for logging)       
      └── Victron SmartSolar 100/15 PV+ / PV−       
                 │ BAT+ ── FHAC0001 holder + 5 A ATO fuse ── Powerpole ── 12 V battery (Pb or 4S LiFePO4 14.4 V abs)
                 │ BAT− ───────────────────────────────── Powerpole ── battery −
      DC− ───────┘ (single-point ground in the Hammond 1554F2GY box; SP13 IP68 glands for the generator cable)
```

Operating logic (E unless noted):
1. **Unloaded start / deploy** — brake switch in BRAKE while lowering into the flow (rotor stalls at ≈ 1.4 A short-circuit, ≈ 16 W heat). Flip to RUN: rotor accelerates; bus climbs toward Voc (27 V @ 1 m/s, 59 V @ 2 m/s). TVS never conducts below 58 V standoff.
2. **Charger start** — Victron starts when PV ≥ Vbat + 5 V (≈ 18–19 V for a 13–14 V battery; V from datasheet) → always true once unloaded, then tracks MPP down to Vbat + 1 V. MPP for this generator is predicted at 10–24 V / 0.4–1.5 A; at the lowest flows (MPP < ~14 V) the Victron drops out and the rotor freewheels at ≤ 27 V — harmless.
3. **Load ramp / generator current limit** — MPPT operation inherently holds generator current near the MPP value (≈ half the short-circuit current, 0.4–1.5 A for ≤ 2 m/s). No small MPPT has a settable input-current limit of 1.35 A; in the 3 m/s flood case the MPP current would exceed 1.5 A, so the **dump threshold (≈ 45 V) doubles as the overspeed/overcurrent trip**: bus > 45 V means flow beyond design or charger not loading.
4. **Full battery / disconnected load** — charger stops drawing → bus rises to Voc → at ≈ 45 V the relay module connects the dump resistor; bus falls to the turbine's power-limited point (≈ 30 V / 2 A @ 60 W with 15 Ω; ≈ 44 V / 1.35 A with 33 Ω) and the module releases at ≈ 35 V with hysteresis/delay to avoid chatter. The charger resumes when the battery accepts current. Rotor never runs away because the dump is on the generator bus, independent of the charger.
5. **Flood / retrieval** — flip BRAKE (shorts U-V-W): transient ≈ 5–9 A, then ≈ 1.4 A steady; rotor slows to a crawl. Interrupting the brake later arcs only at ≈ 1.4 A near 0 V (acceptable for the 20 A contacts).
6. **Fault** — 5 A battery fuse protects wiring from a reverse-fed charger fault; TVS absorbs inductive spikes when the brake/dump switch; Schottky bridge blocks battery back-feed.

---

## 6. Prototype cost (USD, one unit; prices as captured above, FX ≈ £1 = $1.30, €1 = $1.10, CAD/AUD converted — E)

| Item | Qty | Unit | Ext. | Status |
|---|---|---|---|---|
| CubeMars GL60 KV25 (w/o encoder, RobotShop) | 1 | 126.70 | 126.70 | V |
| MBR10100 Schottky (onsemi/Panjit) | 6 | 0.95 | 5.70 | V (€0.61 / £0.72) |
| (alt.) Vishay VS-26MT40 module | 1 | 10.54–15.45 | — | V |
| Victron SmartSolar MPPT 100/15 | 1 | 82.45 | 82.45 | V |
| Ohmite HS100 15R J dump resistor | 1 | 14.25 | 14.25 | V (£10.96) |
| Heatsink for resistor (generic, ~1 °C/W) | 1 | 8.00 | 8.00 | E |
| 6–80 V voltage-monitor relay module | 1 | 12.00 | 12.00 | E |
| TVS 5KP60A | 2 | 1.78 | 3.56 | V (500+ price; singles ~$2–3 E) |
| NKK S32F 3PDT brake switch | 1 | 12.73 | 12.73 | V |
| FHAC0001 inline holder + 0287005.PXCN 5 A fuse | 1+2 | 6.08 + 0.44 | 6.96 | V |
| Anderson Powerpole 1327/1327G6 + 1331 (2 pairs) | 4+4 | ~1.2 + 0.85 | 8.20 | V/E |
| Weipu SP13 3-pin IP68 pair (generator) + 2-pin pair (battery) | 2 pr | 4.55 / 4.17 | 17.44 | V (×2 halves each, E) |
| Hammond 1554F2GY IP68 enclosure | 1 | 22.16 | 22.16 | V |
| PG7 IP68 glands | 4 | 1.40 | 5.60 | V (RS £26.64/25) |
| Wire, lugs, standoffs, thermal paste | — | — | 15.00 | E |
| **Total (with Victron 100/15)** | | | **≈ 340** | E |
| Option: EPEver Tracer2210AN instead of Victron | | 70–90 | ≈ 330 | V/E |
| Option: Morningstar TS-45 battery-side diversion (not needed) | | 219.20 | +219 | V |
| Battery (12 V Pb or 4S LiFePO4) | | | not included | — |

---

## 7. Could not be found / verify (reachable sources)

1. Any primary CubeMars page/PDF (proxy 403): official Kt (0.40 vs 0.45 conflict), official IP rating (IP45 only on a reseller), **which mounting pattern (4×M3 PCD 40 / 4×M2.5 PCD 50) is on the stator base vs. the rotor bell**, thread depths, the "GL60-Motor Installation Dimension Drawing.pdf"/STEP, and an explicit current product revision statement (only inferred: GL60 vs GL60 II).
2. MBR10100 forward voltage at 1–2 A as a number (only in Fig. 3 curves of the datasheets); estimated 0.50–0.60 V.
3. Verbatim Genasun GVB-8 manual clause describing behaviour when input voltage exceeds battery voltage (boost pass-through) — inferred from topology.
4. Victron 75/15 / 100/15 self-consumption (datasheet column ambiguous in the only reachable copy).
5. Price for Coleman Air C440-HVAD; a US single-unit Powerwerx price for the 1327 housings; a US DigiKey price for 1.5KE62A.
6. A low-voltage (≥ 60 V DC-rated) 3-pole rotary isolator; only 1000–1200 V PV isolators and a 30 V DC-rated 3PDT toggle were found.
7. A branded wind/hydro boost controller with a published DC input-voltage limit ≥ 60 V.
8. Morningstar SS-MPPT-15L: 60 V (Morningstar guide) vs 75 V (retailers) — manufacturer figure used.
