# Benchmark freeze

Sealed on **2026-10-26** by the W13a sealing session, before any system was run on the benchmark. Re-sealed on **2026-10-27** (see "Re-seals" below), also before any system was run on the benchmark.

The benchmark releases `bench-01`, `bench-02` and `bench-03`, their contracts, their ground truth and their
tests live **outside this repo** until scoring (`~/Documents/src/semantic-auditor-bench-sealed/`). This file
pins the SHA-256 of every sealed file, so anyone can check afterwards that nothing changed. Feature-module
file names describe the features, so they are listed under opaque labels; the sealed `MANIFEST.sha256` maps
every path to its hash, and its own hash is below.

Verify (after unsealing, from the sealed folder): `python3 tools/freeze.py --check <repo>/bench/FROZEN.md`

- Sealed files: **90**
- `MANIFEST.sha256`: `f1701ccff7b9310b6ab15580f0dc0eeee9026f227c374218d906f9be0cd99e0b`

## History (earlier freezes and re-seal records)

| File | SHA-256 |
|---|---|
| `history/2026-10-26-first-freeze/FROZEN.md` | `3a568c52006cc107e19557b727608783d812e8b9e85924a4d1714e9d7f017e29` |
| `history/2026-10-26-first-freeze/MANIFEST.sha256` | `33ce3943a462a21730448d7ef912956caf52ecf60a024285372daa60aa61e61c` |
| `history/2026-10-26-first-freeze/contracts/bench-01/personas.yaml` | `33e9e61543da72ad15b5cc6eeb45394de34ca355db38659f814ef5350217f02b` |
| `history/2026-10-26-first-freeze/contracts/bench-01/principles.yaml` | `8936337c897f1b26201754fa1a1c290be9707c6b869763a98b6e0cf448bf3bb3` |
| `history/2026-10-26-first-freeze/contracts/bench-02/personas.yaml` | `61352f0890eda36eb76cffa77fceb4bb464e9ff76ccd180a587f157848bc9826` |
| `history/2026-10-26-first-freeze/contracts/bench-02/principles.yaml` | `d34c1b15806a472551c101cfc6a9909ba5c683bdf7bae472a4dd3c1be9c51b2a` |
| `history/2026-10-26-first-freeze/contracts/bench-03/personas.yaml` | `996663cd84e49b87b46657b974752ec262760b96a58caf6ac737645b5fee96c7` |
| `history/2026-10-27-migration.yaml` | `dea96b34c47c0eb2c0ea4b8dc515928c07e693399b72f02956d4f974b437e021` |
| `history/2026-10-27-second-freeze/FROZEN.md` | `7f84dd7bd5fa922bbc1fad91aa18153b4fd698eb077bb6161f7dda632238e7ba` |
| `history/2026-10-27-second-freeze/MANIFEST.sha256` | `cac7f3ed5acd780532ff2a0b293cbbe36349b7241777d3da4d96572bfd637b62` |
| `history/2026-10-27b-normalized-truth.yaml` | `e457e7c3be7c706ce7db8585c483f9b5eb1084b985ff3590c1452467730cd0a1` |

## Ground truth

| File | SHA-256 |
|---|---|
| `ground_truth/bench-01.stories.yaml` | `caa35ce97b5727b7c8a31ff71a0a085eaa15357f509d4592f787d043dde21811` |
| `ground_truth/bench-01.yaml` | `b1bdd7c23478c1f544a5ee481619a5680f382f5727f9900af0abae6abd64f930` |
| `ground_truth/bench-02.stories.yaml` | `3165be56454218e787b652e6915fb89eca6ff1991122a0d72a681649fdba3e62` |
| `ground_truth/bench-02.yaml` | `e26ab8f36e69b4024f9a156fa52f020d0ba7f3d1ca02ca640e0a0e911914ed64` |
| `ground_truth/bench-03.stories.yaml` | `8d33a33f17710f261baded4918900534d358eb082cb1ef66732054acb9fc98d9` |
| `ground_truth/bench-03.yaml` | `48b07f8e56912183a25532ddbb33fca2685244206fd3943bb152b8964c9c7308` |
| `ground_truth/normalized/bench-01.truth.json` | `6feaad068a3a33c32524fd32dac9de917d087ac2fbdea660d8317ee07b472f15` |
| `ground_truth/normalized/bench-02.truth.json` | `8ae15c655a2fa5e6da38c2a184542dd484fa03b3335f5b8955ce6a05435cb6a3` |
| `ground_truth/normalized/bench-03.truth.json` | `7bead37363bedea90a90a6f3ad57ecae31e9ab510c2eb01111509882ac0823cb` |

## Contracts (product policy, personas, scenarios)

| File | SHA-256 |
|---|---|
| `contracts/bench-01/RELEASE_NOTES.md` | `ea4d3502fed7f7424bbff10c9fb0d9643ac700f87245e4d8371a8464d9bfa10b` |
| `contracts/bench-01/app.yaml` | `e24f3235be46d4e07582b6d1db8a581a03e02f7446934f45b1e67c9e22116d1b` |
| `contracts/bench-01/decisions.yaml` | `8e320883ff03ee901bd50faa359b4d54f622d1f97a5f7d0ce1f5a887a6e11efb` |
| `contracts/bench-01/facts.yaml` | `a65b9acefac5e861dade00f8460eaf170e38d411c5cb36bf80211d3217ffcac2` |
| `contracts/bench-01/features.yaml` | `57abcd7dd05b5de89308290c541282da58a53232553a2f2403f573b91c126d74` |
| `contracts/bench-01/oracles.yaml` | `1efbb567fac20ddcb383e201229f503d7534e54e607591e95f4564d7c26e2393` |
| `contracts/bench-01/personas.yaml` | `59a0024916bdba744a2af0de50385817fef3aa28c4cfed073638f9475d4fa23c` |
| `contracts/bench-01/principles.yaml` | `8f1360f24b156ac6c202d8ff368ec6a3fc797235b33e36978b401261bf4581b0` |
| `contracts/bench-01/release_policy.yaml` | `731768150cc31fc9ad51791e4865d91a513ec3294e1c3f96f563c8ab7407b5c6` |
| `contracts/bench-01/rubric.md` | `5a328de976776be6404757ad7b0f590c315caa7fdb990e1c22f3f204ef54f903` |
| `contracts/bench-01/scenarios.yaml` | `f1bafbb131029663466a7bd2241ed6dc7375e87a04d0184dcc94f025e3ae311e` |
| `contracts/bench-01/state.yaml` | `38747addd15427b69919748c549628b2c379ff379f6440ff0afffd3d9958f114` |
| `contracts/bench-01/subject.yaml` | `78f25e72d30583e0a953e0359139c982980b640cd29165c17ae9d66890b2f7c4` |
| `contracts/bench-01/surfaces.yaml` | `bde1ba34ed43fdf3ca36dfffe307551bec317db6a0ed19b55f23d830c3fa0883` |
| `contracts/bench-02/RELEASE_NOTES.md` | `46302543a62e8081dc7610653694671ef7432770fad57421f648f60bc05e6803` |
| `contracts/bench-02/app.yaml` | `95eeeef5c51e67f8d2cddbfea0fb0d2c3274be90b5d6385ad8fab907b20cc3e3` |
| `contracts/bench-02/decisions.yaml` | `5bbc505b0435049f16f29facf15a8711592d6c1a50784d037740e4e5870df22f` |
| `contracts/bench-02/facts.yaml` | `71736effad35c9f4c1ca5d02bd086f669d8e8a8164633464bf3a4ce884d21139` |
| `contracts/bench-02/features.yaml` | `8d5739b6701604f43ef409d32c96787d59b7a239a72a7a1d3302286e87c14275` |
| `contracts/bench-02/oracles.yaml` | `1efbb567fac20ddcb383e201229f503d7534e54e607591e95f4564d7c26e2393` |
| `contracts/bench-02/personas.yaml` | `b0c33086725aca6ef9525e04b624d8c20f15f7ceef662909c2f9212577ffdf28` |
| `contracts/bench-02/principles.yaml` | `298b8e1f86dd8c732b67d429c72556f3456a3e7c63da7945f679e542746f023d` |
| `contracts/bench-02/release_policy.yaml` | `731768150cc31fc9ad51791e4865d91a513ec3294e1c3f96f563c8ab7407b5c6` |
| `contracts/bench-02/rubric.md` | `5a328de976776be6404757ad7b0f590c315caa7fdb990e1c22f3f204ef54f903` |
| `contracts/bench-02/scenarios.yaml` | `9478bcae0f0e3da8cabd75726d8456dca681e34e05e225aa9dcd010778a6c3bb` |
| `contracts/bench-02/state.yaml` | `38747addd15427b69919748c549628b2c379ff379f6440ff0afffd3d9958f114` |
| `contracts/bench-02/subject.yaml` | `78f25e72d30583e0a953e0359139c982980b640cd29165c17ae9d66890b2f7c4` |
| `contracts/bench-02/surfaces.yaml` | `bde1ba34ed43fdf3ca36dfffe307551bec317db6a0ed19b55f23d830c3fa0883` |
| `contracts/bench-03/RELEASE_NOTES.md` | `0fb86c1d097d97f634c627371f4555ec44bd429c4b00de158a7acf25fdffa850` |
| `contracts/bench-03/app.yaml` | `b8469ea7a98f6dc240264c1ca1c41830018140a7ff91e9f7c946d6bbfc9106af` |
| `contracts/bench-03/decisions.yaml` | `8db3c8c9743c2a951f730c2b49cc71e761893f34c2607cd6fa372655a3514b06` |
| `contracts/bench-03/facts.yaml` | `a65b9acefac5e861dade00f8460eaf170e38d411c5cb36bf80211d3217ffcac2` |
| `contracts/bench-03/features.yaml` | `7182c727366f3c934a1dfbfc40148dbca5c2651bdb30287913b1922af539569f` |
| `contracts/bench-03/oracles.yaml` | `1efbb567fac20ddcb383e201229f503d7534e54e607591e95f4564d7c26e2393` |
| `contracts/bench-03/personas.yaml` | `ef90845b8a70537cf06850b1e88b7f3de03bb4c4bf48608a33ca71cefae089c0` |
| `contracts/bench-03/principles.yaml` | `848360343de438595700f590b282a71abc3bb51631b83934cf81a88cc95cde1e` |
| `contracts/bench-03/release_policy.yaml` | `731768150cc31fc9ad51791e4865d91a513ec3294e1c3f96f563c8ab7407b5c6` |
| `contracts/bench-03/rubric.md` | `5a328de976776be6404757ad7b0f590c315caa7fdb990e1c22f3f204ef54f903` |
| `contracts/bench-03/scenarios.yaml` | `c33c9c1cce15d186d4827c22d62b3dd7b0f98718d0799def14bde3898b7516e0` |
| `contracts/bench-03/state.yaml` | `38747addd15427b69919748c549628b2c379ff379f6440ff0afffd3d9958f114` |
| `contracts/bench-03/subject.yaml` | `78f25e72d30583e0a953e0359139c982980b640cd29165c17ae9d66890b2f7c4` |
| `contracts/bench-03/surfaces.yaml` | `3de975a9440e026270ac555b7f488b72c9812857e2119417d92e51e857324a80` |

## Release modules

| File | SHA-256 |
|---|---|
| `nbbench/__init__.py` | `ea6babff3a187d258f4f847609123b4175f41f73fc3513e1ad2b293feb4b7c51` |
| `nbbench/releases/bench_01.py` | `1956be58ba309c90c4330c189335c673fe864b7e9c581d6fb0a9fc79de6ff718` |
| `nbbench/releases/bench_02.py` | `f026f18f4be8d7377ceaf328987845f94e1e7b77e42db7f1d2e2a4ea03e826a6` |
| `nbbench/releases/bench_03.py` | `07be3c2e1c0b2f7b5244d5f7e67f85c7593295bc623af42ee2e59dcd195d8ab7` |
| `sitecustomize.py` | `15a519ece46725507ce446a0a9ebbd9e437e330222bc3ddf7bbe3a8ca27324c2` |

## Feature modules (names sealed)

| File | SHA-256 |
|---|---|
| `feature module #1` | `09e4becbec7f0daf59469d893e0a2c2e49b1bbc142c2053c766cf55fe3cdb66f` |
| `feature module #2` | `17e3e0592cd75a8f6322018dd32d43be0bef154a962b0ce09b6a8945638ed612` |
| `feature module #3` | `1fdaf1c846fe23a14c9ec013a88c4d590b0c51ee7b4ddf3554958da1d9a7f81e` |
| `feature module #4` | `46ca4b568835ffbccbbfc1bf4bfa3b0713691920a48dbf1ff47d56890f8923ca` |
| `nbbench/features/__init__.py` | `6a7787a8ffe7a3d741bd6b2e28e1c0de214bcc7ad82748db63856402655ad28c` |
| `feature module #5` | `95b25c4eb38db8368afad174a582f43043d05642edc3d0c194702a38f4ef6ed0` |
| `feature module #6` | `96e509b0e2178e88f1f836b461a02652e34374eef98a510edf9ff52aefeb5c33` |
| `feature module #7` | `b64e8a9ac505cea2d9fdb58a21dbde89e17bff984d31d466c6543238cfc3d502` |
| `feature module #8` | `b81bd65cd4963691dbc7f3fef6d33474a291fc30606ddf9ce806a79bf51dcf1c` |
| `feature module #9` | `cb1c2d1575e6214c90f5be127aae34c523bdf6f57e04fb0bf2e9710c08d00265` |
| `feature module #10` | `e4f2e2738f5b5c4d7c4acd5c79370556955b51b64c99062e470368b15feff5d4` |

## Tests, tools and README

| File | SHA-256 |
|---|---|
| `README.md` | `5fbb9a314d4672ec43a7edf6aa9cc2fb41d73d6756ba3f29cc7ed72fc2094bd5` |
| `tests/conftest.py` | `c645f016492f19990c736f549297b9b3dcf1103d4ba723a36cd227faf75d6ff7` |
| `tests/gtlib.py` | `08006a3f8b3193748a1fe5430c268f019c5711db3792bf49e2bbf16fc88e2245` |
| `tests/nbdrive.py` | `0f31e63b4f36dddec37c58217b4b2c71f318489b2816b109396e8917777d6bb0` |
| `tests/test_contract_and_base.py` | `4e90202b38224ec72cab20cd521f617d00c40117d77624c58b3179c8fa5a81bf` |
| `tests/test_env_and_server.py` | `6dd8e6570d45b0d29fc0b61171da5ecedb949f37cba1b63895cf7c2658941dd6` |
| `tests/test_ground_truth.py` | `a31990a11757382327b5995f9a8bcc2faffaeced06bcb87037e6eb157d476cea` |
| `tests/test_normalized.py` | `d6dcd779459d417e209a9d6970d6264f70cbcff9627bed8fd932065792c28d87` |
| `tools/freeze.py` | `69e2c44c0359c47445d2fdbb94ac89269558b4955636bcb266ca7d55410b8282` |
| `tools/migrate_check.py` | `2003a5e7ab2889bce0e6d54e2a2ac3634fa926295e11958d20e1f986a27e4d82` |
| `tools/record_stories.py` | `00e9926d1b69b24f117bce5093b767dd8b4f1c1c71777e69df49a753ada3c7cb` |
| `tools/to_normalized.py` | `7f71579e2931c0a46aea045a515e0a776840608c2ec61cdcbb004c21580cbed2` |

## Re-seals

Each earlier freeze is kept unchanged (the repo's `bench/FROZEN-*.md`, and the sealed `history/*/`),
so it can still be checked. Hashes below are against the freeze each re-seal replaced.

### 2026-10-27: compatibility-only

semaudit 8756afd (main) generalized the contract schema: persona `trip` and top-level `party` became the persona `context` declared by a new `subject.yaml`, and the time_until condition's `trip_field` became `context_field`. The bench contracts no longer loaded. Only key names changed, plus the added subject files; no release behaviour, scenario, value, expected finding or ground truth changed. `python3 tools/migrate_check.py` proves it (rename map applied to the first-freeze YAML equals the new YAML; every other contract file is byte-identical). Done before any model or baseline scoring run.

- Previous freeze: 70 files, `MANIFEST.sha256` `33ce3943a462a21730448d7ef912956caf52ecf60a024285372daa60aa61e61c`, FROZEN.md `3a568c52006cc107e19557b727608783d812e8b9e85924a4d1714e9d7f017e29`
- Changed 9, added 12, removed 0; 61 unchanged

| File | Old SHA-256 | New SHA-256 | Reason |
|---|---|---|---|
| `README.md` | 286fb4779ecb4b49c2ae13a40b96d4d036b023b0ed958b84f3c9b9d61fa711ce | 682e696a399ecf17ef2cf949e13c33b111c9b025da172649ea615b3d168b847e | documents the re-seal and the migration check |
| `contracts/bench-01/personas.yaml` | 33e9e61543da72ad15b5cc6eeb45394de34ca355db38659f814ef5350217f02b | 59a0024916bdba744a2af0de50385817fef3aa28c4cfed073638f9475d4fa23c | rename: trip -> context, party -> context.party |
| `contracts/bench-01/principles.yaml` | 8936337c897f1b26201754fa1a1c290be9707c6b869763a98b6e0cf448bf3bb3 | 8f1360f24b156ac6c202d8ff368ec6a3fc797235b33e36978b401261bf4581b0 | rename: trip_field -> context_field |
| `contracts/bench-02/personas.yaml` | 61352f0890eda36eb76cffa77fceb4bb464e9ff76ccd180a587f157848bc9826 | b0c33086725aca6ef9525e04b624d8c20f15f7ceef662909c2f9212577ffdf28 | rename: trip -> context, party -> context.party |
| `contracts/bench-02/principles.yaml` | d34c1b15806a472551c101cfc6a9909ba5c683bdf7bae472a4dd3c1be9c51b2a | 298b8e1f86dd8c732b67d429c72556f3456a3e7c63da7945f679e542746f023d | rename: trip_field -> context_field |
| `contracts/bench-03/personas.yaml` | 996663cd84e49b87b46657b974752ec262760b96a58caf6ac737645b5fee96c7 | ef90845b8a70537cf06850b1e88b7f3de03bb4c4bf48608a33ca71cefae089c0 | rename: trip -> context, party -> context.party |
| `tests/nbdrive.py` | d493297aaffe6fc33923e9054d01c5bd3df3994bf85b3e167ae6e0409e392afb | 0f31e63b4f36dddec37c58217b4b2c71f318489b2816b109396e8917777d6bb0 | follows the rename: reads persona context instead of trip/party |
| `tests/test_contract_and_base.py` | 47cd9ce750a11c688fb81fb9310f99cd6cb68f7e05a3539963841215832ba9ee | 4e90202b38224ec72cab20cd521f617d00c40117d77624c58b3179c8fa5a81bf | follows the rename and the adapter's new persona_body(persona, context) signature |
| `tools/freeze.py` | 700bb7edae4f370a375ad03966ca823fee2b5d60b944abab31044b00587bc25a | c08a52b9c041c7344c6c1df256ca7e5721a551f66ecfbfb37598df09796720e0 | records re-seals: previous hashes kept, old -> new per file with a reason |
| `contracts/bench-01/subject.yaml` | (new) | 78f25e72d30583e0a953e0359139c982980b640cd29165c17ae9d66890b2f7c4 | added: the persona context fields, with the old trip/party defaults |
| `contracts/bench-02/subject.yaml` | (new) | 78f25e72d30583e0a953e0359139c982980b640cd29165c17ae9d66890b2f7c4 | added: the persona context fields, with the old trip/party defaults |
| `contracts/bench-03/subject.yaml` | (new) | 78f25e72d30583e0a953e0359139c982980b640cd29165c17ae9d66890b2f7c4 | added: the persona context fields, with the old trip/party defaults |
| `history/2026-10-26-first-freeze/FROZEN.md` | (new) | 3a568c52006cc107e19557b727608783d812e8b9e85924a4d1714e9d7f017e29 | added: first-freeze manifest, FROZEN.md and the pre-migration contract files, and this record |
| `history/2026-10-26-first-freeze/MANIFEST.sha256` | (new) | 33ce3943a462a21730448d7ef912956caf52ecf60a024285372daa60aa61e61c | added: first-freeze manifest, FROZEN.md and the pre-migration contract files, and this record |
| `history/2026-10-26-first-freeze/contracts/bench-01/personas.yaml` | (new) | 33e9e61543da72ad15b5cc6eeb45394de34ca355db38659f814ef5350217f02b | added: first-freeze manifest, FROZEN.md and the pre-migration contract files, and this record |
| `history/2026-10-26-first-freeze/contracts/bench-01/principles.yaml` | (new) | 8936337c897f1b26201754fa1a1c290be9707c6b869763a98b6e0cf448bf3bb3 | added: first-freeze manifest, FROZEN.md and the pre-migration contract files, and this record |
| `history/2026-10-26-first-freeze/contracts/bench-02/personas.yaml` | (new) | 61352f0890eda36eb76cffa77fceb4bb464e9ff76ccd180a587f157848bc9826 | added: first-freeze manifest, FROZEN.md and the pre-migration contract files, and this record |
| `history/2026-10-26-first-freeze/contracts/bench-02/principles.yaml` | (new) | d34c1b15806a472551c101cfc6a9909ba5c683bdf7bae472a4dd3c1be9c51b2a | added: first-freeze manifest, FROZEN.md and the pre-migration contract files, and this record |
| `history/2026-10-26-first-freeze/contracts/bench-03/personas.yaml` | (new) | 996663cd84e49b87b46657b974752ec262760b96a58caf6ac737645b5fee96c7 | added: first-freeze manifest, FROZEN.md and the pre-migration contract files, and this record |
| `history/2026-10-27-migration.yaml` | (new) | dea96b34c47c0eb2c0ea4b8dc515928c07e693399b72f02956d4f974b437e021 | added: first-freeze manifest, FROZEN.md and the pre-migration contract files, and this record |
| `tools/migrate_check.py` | (new) | 2003a5e7ab2889bce0e6d54e2a2ac3634fa926295e11958d20e1f986a27e4d82 | added: the mechanical-migration proof |

### 2026-10-27: additive-only

Added the converter from this ground truth to the repo's normalized truth format (bench/conditions/FORMAT.md, "The custodian's converter"), its output for each release, and a test that every item converts, validates with semaudit.bench.findings.Truth, and keeps its counts per kind. No ground truth, contract, release or feature file changed. Done before any model or baseline scoring run.

- Previous freeze: 82 files, `MANIFEST.sha256` `cac7f3ed5acd780532ff2a0b293cbbe36349b7241777d3da4d96572bfd637b62`, FROZEN.md `7f84dd7bd5fa922bbc1fad91aa18153b4fd698eb077bb6161f7dda632238e7ba`
- Changed 2, added 8, removed 0; 80 unchanged

| File | Old SHA-256 | New SHA-256 | Reason |
|---|---|---|---|
| `README.md` | 682e696a399ecf17ef2cf949e13c33b111c9b025da172649ea615b3d168b847e | 5fbb9a314d4672ec43a7edf6aa9cc2fb41d73d6756ba3f29cc7ed72fc2094bd5 | documents the converter and this re-seal |
| `tools/freeze.py` | c08a52b9c041c7344c6c1df256ca7e5721a551f66ecfbfb37598df09796720e0 | 69e2c44c0359c47445d2fdbb94ac89269558b4955636bcb266ca7d55410b8282 | re-seal records chain: each earlier re-seal is compared with the freeze it produced |
| `ground_truth/normalized/bench-01.truth.json` | (new) | 6feaad068a3a33c32524fd32dac9de917d087ac2fbdea660d8317ee07b472f15 | added: the converter's output, one truth file per release |
| `ground_truth/normalized/bench-02.truth.json` | (new) | 8ae15c655a2fa5e6da38c2a184542dd484fa03b3335f5b8955ce6a05435cb6a3 | added: the converter's output, one truth file per release |
| `ground_truth/normalized/bench-03.truth.json` | (new) | 7bead37363bedea90a90a6f3ad57ecae31e9ab510c2eb01111509882ac0823cb | added: the converter's output, one truth file per release |
| `history/2026-10-27-second-freeze/FROZEN.md` | (new) | 7f84dd7bd5fa922bbc1fad91aa18153b4fd698eb077bb6161f7dda632238e7ba | added: the second freeze's manifest and FROZEN.md, and this record |
| `history/2026-10-27-second-freeze/MANIFEST.sha256` | (new) | cac7f3ed5acd780532ff2a0b293cbbe36349b7241777d3da4d96572bfd637b62 | added: the second freeze's manifest and FROZEN.md, and this record |
| `history/2026-10-27b-normalized-truth.yaml` | (new) | e457e7c3be7c706ce7db8585c483f9b5eb1084b985ff3590c1452467730cd0a1 | added: the second freeze's manifest and FROZEN.md, and this record |
| `tests/test_normalized.py` | (new) | d6dcd779459d417e209a9d6970d6264f70cbcff9627bed8fd932065792c28d87 | added: every item converts and validates; counts per kind equal before and after |
| `tools/to_normalized.py` | (new) | 7f71579e2931c0a46aea045a515e0a776840608c2ec61cdcbb004c21580cbed2 | added: the converter to bench/conditions/truth.schema.json |

