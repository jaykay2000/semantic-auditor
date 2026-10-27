# Benchmark freeze

Sealed on **2026-10-26** by the W13a sealing session, before any system was run on the benchmark.

The benchmark releases `bench-01`, `bench-02` and `bench-03`, their contracts, their ground truth and their
tests live **outside this repo** until scoring (`~/Documents/src/semantic-auditor-bench-sealed/`). This file
pins the SHA-256 of every sealed file, so anyone can check afterwards that nothing changed. Feature-module
file names describe the features, so they are listed under opaque labels; the sealed `MANIFEST.sha256` maps
every path to its hash, and its own hash is below.

Verify (after unsealing, from the sealed folder): `python3 tools/freeze.py --check <repo>/bench/FROZEN.md`

- Sealed files: **70**
- `MANIFEST.sha256`: `33ce3943a462a21730448d7ef912956caf52ecf60a024285372daa60aa61e61c`

## Ground truth

| File | SHA-256 |
|---|---|
| `ground_truth/bench-01.stories.yaml` | `caa35ce97b5727b7c8a31ff71a0a085eaa15357f509d4592f787d043dde21811` |
| `ground_truth/bench-01.yaml` | `b1bdd7c23478c1f544a5ee481619a5680f382f5727f9900af0abae6abd64f930` |
| `ground_truth/bench-02.stories.yaml` | `3165be56454218e787b652e6915fb89eca6ff1991122a0d72a681649fdba3e62` |
| `ground_truth/bench-02.yaml` | `e26ab8f36e69b4024f9a156fa52f020d0ba7f3d1ca02ca640e0a0e911914ed64` |
| `ground_truth/bench-03.stories.yaml` | `8d33a33f17710f261baded4918900534d358eb082cb1ef66732054acb9fc98d9` |
| `ground_truth/bench-03.yaml` | `48b07f8e56912183a25532ddbb33fca2685244206fd3943bb152b8964c9c7308` |

## Contracts (product policy, personas, scenarios)

| File | SHA-256 |
|---|---|
| `contracts/bench-01/RELEASE_NOTES.md` | `ea4d3502fed7f7424bbff10c9fb0d9643ac700f87245e4d8371a8464d9bfa10b` |
| `contracts/bench-01/app.yaml` | `e24f3235be46d4e07582b6d1db8a581a03e02f7446934f45b1e67c9e22116d1b` |
| `contracts/bench-01/decisions.yaml` | `8e320883ff03ee901bd50faa359b4d54f622d1f97a5f7d0ce1f5a887a6e11efb` |
| `contracts/bench-01/facts.yaml` | `a65b9acefac5e861dade00f8460eaf170e38d411c5cb36bf80211d3217ffcac2` |
| `contracts/bench-01/features.yaml` | `57abcd7dd05b5de89308290c541282da58a53232553a2f2403f573b91c126d74` |
| `contracts/bench-01/oracles.yaml` | `1efbb567fac20ddcb383e201229f503d7534e54e607591e95f4564d7c26e2393` |
| `contracts/bench-01/personas.yaml` | `33e9e61543da72ad15b5cc6eeb45394de34ca355db38659f814ef5350217f02b` |
| `contracts/bench-01/principles.yaml` | `8936337c897f1b26201754fa1a1c290be9707c6b869763a98b6e0cf448bf3bb3` |
| `contracts/bench-01/release_policy.yaml` | `731768150cc31fc9ad51791e4865d91a513ec3294e1c3f96f563c8ab7407b5c6` |
| `contracts/bench-01/rubric.md` | `5a328de976776be6404757ad7b0f590c315caa7fdb990e1c22f3f204ef54f903` |
| `contracts/bench-01/scenarios.yaml` | `f1bafbb131029663466a7bd2241ed6dc7375e87a04d0184dcc94f025e3ae311e` |
| `contracts/bench-01/state.yaml` | `38747addd15427b69919748c549628b2c379ff379f6440ff0afffd3d9958f114` |
| `contracts/bench-01/surfaces.yaml` | `bde1ba34ed43fdf3ca36dfffe307551bec317db6a0ed19b55f23d830c3fa0883` |
| `contracts/bench-02/RELEASE_NOTES.md` | `46302543a62e8081dc7610653694671ef7432770fad57421f648f60bc05e6803` |
| `contracts/bench-02/app.yaml` | `95eeeef5c51e67f8d2cddbfea0fb0d2c3274be90b5d6385ad8fab907b20cc3e3` |
| `contracts/bench-02/decisions.yaml` | `5bbc505b0435049f16f29facf15a8711592d6c1a50784d037740e4e5870df22f` |
| `contracts/bench-02/facts.yaml` | `71736effad35c9f4c1ca5d02bd086f669d8e8a8164633464bf3a4ce884d21139` |
| `contracts/bench-02/features.yaml` | `8d5739b6701604f43ef409d32c96787d59b7a239a72a7a1d3302286e87c14275` |
| `contracts/bench-02/oracles.yaml` | `1efbb567fac20ddcb383e201229f503d7534e54e607591e95f4564d7c26e2393` |
| `contracts/bench-02/personas.yaml` | `61352f0890eda36eb76cffa77fceb4bb464e9ff76ccd180a587f157848bc9826` |
| `contracts/bench-02/principles.yaml` | `d34c1b15806a472551c101cfc6a9909ba5c683bdf7bae472a4dd3c1be9c51b2a` |
| `contracts/bench-02/release_policy.yaml` | `731768150cc31fc9ad51791e4865d91a513ec3294e1c3f96f563c8ab7407b5c6` |
| `contracts/bench-02/rubric.md` | `5a328de976776be6404757ad7b0f590c315caa7fdb990e1c22f3f204ef54f903` |
| `contracts/bench-02/scenarios.yaml` | `9478bcae0f0e3da8cabd75726d8456dca681e34e05e225aa9dcd010778a6c3bb` |
| `contracts/bench-02/state.yaml` | `38747addd15427b69919748c549628b2c379ff379f6440ff0afffd3d9958f114` |
| `contracts/bench-02/surfaces.yaml` | `bde1ba34ed43fdf3ca36dfffe307551bec317db6a0ed19b55f23d830c3fa0883` |
| `contracts/bench-03/RELEASE_NOTES.md` | `0fb86c1d097d97f634c627371f4555ec44bd429c4b00de158a7acf25fdffa850` |
| `contracts/bench-03/app.yaml` | `b8469ea7a98f6dc240264c1ca1c41830018140a7ff91e9f7c946d6bbfc9106af` |
| `contracts/bench-03/decisions.yaml` | `8db3c8c9743c2a951f730c2b49cc71e761893f34c2607cd6fa372655a3514b06` |
| `contracts/bench-03/facts.yaml` | `a65b9acefac5e861dade00f8460eaf170e38d411c5cb36bf80211d3217ffcac2` |
| `contracts/bench-03/features.yaml` | `7182c727366f3c934a1dfbfc40148dbca5c2651bdb30287913b1922af539569f` |
| `contracts/bench-03/oracles.yaml` | `1efbb567fac20ddcb383e201229f503d7534e54e607591e95f4564d7c26e2393` |
| `contracts/bench-03/personas.yaml` | `996663cd84e49b87b46657b974752ec262760b96a58caf6ac737645b5fee96c7` |
| `contracts/bench-03/principles.yaml` | `848360343de438595700f590b282a71abc3bb51631b83934cf81a88cc95cde1e` |
| `contracts/bench-03/release_policy.yaml` | `731768150cc31fc9ad51791e4865d91a513ec3294e1c3f96f563c8ab7407b5c6` |
| `contracts/bench-03/rubric.md` | `5a328de976776be6404757ad7b0f590c315caa7fdb990e1c22f3f204ef54f903` |
| `contracts/bench-03/scenarios.yaml` | `c33c9c1cce15d186d4827c22d62b3dd7b0f98718d0799def14bde3898b7516e0` |
| `contracts/bench-03/state.yaml` | `38747addd15427b69919748c549628b2c379ff379f6440ff0afffd3d9958f114` |
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
| `README.md` | `286fb4779ecb4b49c2ae13a40b96d4d036b023b0ed958b84f3c9b9d61fa711ce` |
| `tests/conftest.py` | `c645f016492f19990c736f549297b9b3dcf1103d4ba723a36cd227faf75d6ff7` |
| `tests/gtlib.py` | `08006a3f8b3193748a1fe5430c268f019c5711db3792bf49e2bbf16fc88e2245` |
| `tests/nbdrive.py` | `d493297aaffe6fc33923e9054d01c5bd3df3994bf85b3e167ae6e0409e392afb` |
| `tests/test_contract_and_base.py` | `47cd9ce750a11c688fb81fb9310f99cd6cb68f7e05a3539963841215832ba9ee` |
| `tests/test_env_and_server.py` | `6dd8e6570d45b0d29fc0b61171da5ecedb949f37cba1b63895cf7c2658941dd6` |
| `tests/test_ground_truth.py` | `a31990a11757382327b5995f9a8bcc2faffaeced06bcb87037e6eb157d476cea` |
| `tools/freeze.py` | `700bb7edae4f370a375ad03966ca823fee2b5d60b944abab31044b00587bc25a` |
| `tools/record_stories.py` | `00e9926d1b69b24f117bce5093b767dd8b4f1c1c71777e69df49a753ada3c7cb` |

