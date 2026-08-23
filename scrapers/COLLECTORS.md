# Bright Data collector validation

Local scraper code is the reviewed source of truth. Bright Data's CLI currently
supports natural-language scraper creation and execution, but not uploading the
local `interaction.js` and `parser.js` files verbatim. A Collector ID is not
treated as production-ready until its actual output validates against RegLens's
canonical Product Passport model.

| Product | Market | Collector ID | Live output | Manual action |
| --- | --- | --- | --- | --- |
| Brach's Classic Jelly Beans | US | `c_mt5uzri62rgqs8h4cg` | Valid through provider normalization after CLI heal; brand remains missing | Optionally replace with the richer reviewed local parser in Studio |
| Fanta Orange | SA | `c_mt5vf72d2duy4zg283` | Executed; noncanonical flattened output | Replace with local code/schema in Studio, publish, rerun |
| Fanta Orange | CA | `c_mt5vl3jb1edb91v4dx` | Executed; noncanonical nested/string output | Replace with local code/schema in Studio, publish, rerun |
| REIGN Orange Dreamsicle | US | `c_mt5w3b4emf5gnkj7m` | Executed; noncanonical and incomplete output | Replace with local code/schema in Studio, publish, rerun |
| Red Bull Original 8.4 fl oz | US | `c_mt5vegv112moxplzmd` | CLI run: 403, template not generated | Open in Studio, add local code/schema, publish, rerun |
| Mountain Dew Code Red 20 fl oz | US | `c_mt5voe0y6x79qv6vs` | Executed; identity/caffeine only, noncanonical, nested label omitted | Add local code/schema in Studio and verify nested label |
| DORITOS Nacho Cheese | US | `c_mt5vs9c425wuilt88y` | CLI run: 403, template not generated | Complete in Studio with local code/schema and verify SmartLabel iframe |
| Cheetos Crunchy | US | `c_mt5vffsv2go5gbfc9o` | CLI run: 403, template not generated | Add local code/schema in Studio; confirm one run retains both panels |
| MAGGI 2-Minute Masala Noodles | IN | `c_mt5vgjjy25qvjoy8rs` | CLI run: 403, template not generated | Open in Studio, add local code/schema, publish, rerun |
| Nongshim Shin Ramyun Original Big Bowl | US | `c_mt5vg0q8zb75v0u4i` | Executed; facts returned in noncanonical nested/string fields | Replace with local code/schema in Studio, publish, rerun |

Existing Alani Nu, CELSIUS, C4, and Bloom collector IDs remain local environment
configuration and are never copied into documentation with credentials.

CLI retries also created incomplete templates that should not be configured:
`c_mt5ve5sogi3ftf8nq`, `c_mt5veuvp20ueripoq`, and
`c_mt5vokml1i0arqarpy`. The CLI does not currently expose a deletion command;
they can be cleaned up manually in the Bright Data control panel.
