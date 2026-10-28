FROZEN-CONDITIONS manifest 14a9c9ec130eb7d260464aa85927008ee9f7e8a02d1faae1154d9a81dca4ba17 at code d2b07f4ba34f56b2e942ff639b53fe298313e0a4

# Frozen benchmark conditions (W13b, Oct 27)

Every file that decides how a sealed benchmark run is executed and scored, by sha256, frozen BEFORE any
system ran on the sealed releases. `scripts/w13b_bench.py` prints this file's first line into every result.
A change to any file below after this point invalidates the run unless it is re-frozen with a recorded reason.

What was decided before freezing (all in `conditions.toml`):
- judge baselines answer in the normalized format (owner, Oct 27); prompts from tuning round 1 (round 0 + one round);
- B-judge-N pass plan: 2 samples per persona, persona and critique at high effort; calibrated cost $1.067 =
  **1.23x** the auditor's fresh $0.867 on the dev fixture (n = 1 each), outside the +-15% band in the
  baseline's favour, frozen as is by owner ruling;
- NOT built, so reported "not measured": B-explore, B-explore+scenarios, B-repeat, the no-generators ablation
  run (code exists; not in the $16 plan);
- scoring is pre-adjudication until the owner adjudicates the blind sheets.

| file | sha256 |
|---|---|
| `bench/conditions/.gitkeep` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `bench/conditions/FORMAT.md` | `c6791b14b98f25f4f1250aa0a1221ba5820a6630bea43860f47375dc7518084d` |
| `bench/conditions/conditions.toml` | `3f67ba195d2319dcfd603b296788dd0b5b804a28551bcb48c04e25adaec30787` |
| `bench/conditions/findings.schema.json` | `cc6dbcc2a09cd4e807613943d89733d1f49cc0ae849366c672f52c33803c8601` |
| `bench/conditions/prompts/_common.md` | `bdc0da793da80af002830dfd2a14aea2dc026cf6ee948d2b8ea127b7e3411e50` |
| `bench/conditions/prompts/judge_consolidate.md` | `11c4395c2cb2e65a0fce28bf54a9b2ee6ecb3aefebe0a27f25b0edb8cfda55ef` |
| `bench/conditions/prompts/judge_critique.md` | `ef8a32a737eb102f3b16ec53528de70bb6671f2c65056e7f5494e2e3dbb2730b` |
| `bench/conditions/prompts/judge_one.md` | `b70d7f60015bc9de778c861414079a902ff5ccd7dd5f49e10ce3ca74204dd0a1` |
| `bench/conditions/prompts/judge_persona.md` | `4be09edc06fc1e7f331276839da973c553b7f085907c16769c3e4782ea541879` |
| `bench/conditions/truth.schema.json` | `db9439cb80f2a7aa0c74e1274d650678fbb2bd851f56d445cfaff69cb93405ff` |
| `examples/northbound/contract/rubric.md` | `0a15b5eda532ae422d2bf17b51824188513e0c33747876808e9eef3d4cad6af6` |
| `scripts/w13b_bench.py` | `a47c97421139dcec060e7f2ed2b2ff4498d84f4a546e4d43ebb0e89decbeb840` |
| `src/semaudit/__init__.py` | `2e5442bd8b4ae3e1173cc25476d7586ebc110d7bac9c543b49ca3a8c52174264` |
| `src/semaudit/adapters/__init__.py` | `496cdfb9ade86d1e5d2425e1625897aa23f8def32861f5e2a32af5c87e515651` |
| `src/semaudit/adapters/base.py` | `3555119e8e83c21047b288692f19ffe50c4a19bc9dcf246772cbae3240be34ac` |
| `src/semaudit/adapters/hooks.py` | `e23089843b2bcd0cd8c9575adc62ce3fef1f314125a49b2fd527c474d9667143` |
| `src/semaudit/bench/__init__.py` | `b039a3aac98f2ceff5e1cff45a7a22ddabe3e0e12a455788caef2947fb37abe2` |
| `src/semaudit/bench/ablate.py` | `d93ee7e195aaace8f59e0b44b53638f075175d4387ffc58bfe74c6e4444dc360` |
| `src/semaudit/bench/adjudicate.py` | `25fb6fb9cee41af281261c4983550048d8bfa5accf95f32b59d20082f578f4f6` |
| `src/semaudit/bench/e3.py` | `1f013f90df6672a44abfa9ced829b424a1b965c5a312d2b9db46e5bd03ec76dd` |
| `src/semaudit/bench/findings.py` | `0bd57921a02c630116b7b521f8a8d4ceef5c35a545f5ffc9d0e87f4634a1ba50` |
| `src/semaudit/bench/judge.py` | `d3c785565cdf361606b00e0c7544c897b87b2df299529b0f2fccf67ff20bbffb` |
| `src/semaudit/bench/match.py` | `3be6cd24b9e40a7b4e0be1f2da9ae6c1602becdc6f35cce232f239d25446ed25` |
| `src/semaudit/capture/__init__.py` | `9de0ef48feb1da6bc9494d8f1ca0e0a817ea6854303737a6a966b3288cfa8cd5` |
| `src/semaudit/capture/dom.py` | `f8a7d6c8fc362b5cd7c22fb61ad009a99a1eaa5feefee2ddbbb1e09e3416934b` |
| `src/semaudit/capture/launcher.py` | `325448a45b6d59aa7c87b99bfb9e7b14d1b21456c382f1111766081fbaaed24e` |
| `src/semaudit/capture/runner.py` | `ac848611b43b37ce480b297e0c0dd6a8b510f86543ed1a3d1237ef1355d2dbdf` |
| `src/semaudit/capture/sinks.py` | `0eb59ca72fbcae70c0840f2eb0aae5b11e1c0cd17989d63798d6c7e27dfc5e2f` |
| `src/semaudit/check/__init__.py` | `be91191ff82bbf63ca5973ca6b3f40a19a81ac6a28107ed6935ba373cf5af67a` |
| `src/semaudit/cli.py` | `4c82b3b7e95cc983500a63645082315ced77483559aa31d3d5efd54d09002176` |
| `src/semaudit/contract/__init__.py` | `9851edfc164c74523b6290d236edb7b4b3d47a04d67fdb69a7ec9c24f844d814` |
| `src/semaudit/contract/approve.py` | `99535ed0475dfc9164a72e41f51cff5f642d00004839593b46f1a67f415412dd` |
| `src/semaudit/contract/review.py` | `fb3180c8e5804358fa22fe3b04355decf458a09fc10c1a697efe08d76eefb631` |
| `src/semaudit/contract/schema.py` | `0303c6e18c162b0890a5e76f408deb6c9d35e8670b1aeccba1a8bd56e232822e` |
| `src/semaudit/contract/validate.py` | `0a0fc11f94ec7b660324771cd45167d440155a952c1918ae6bcd982350a02507` |
| `src/semaudit/decide/__init__.py` | `7529ef9157947707b3a4ca4577e78bec8d878b20bf26df1b5f0ef5c89eb92178` |
| `src/semaudit/decide/issues.py` | `e86888a3b73f0e6cdd60c6a1802245312d362499f6058c26f1bef39ac884e8ec` |
| `src/semaudit/decide/memory.py` | `6c7d06af512222232656f19445a17099b79847ce88bc8d9aacc82af92bd07b9e` |
| `src/semaudit/decide/pipeline.py` | `47b38ca2750214a26685fa2d9d7451090f197d6e85f06d7e72219fd380b4538f` |
| `src/semaudit/decide/repro.py` | `7261fe7bf5c663303ff3f4cd4ab9ec252f24a3e25a0e075159bd38500c13f201` |
| `src/semaudit/decide/run.py` | `6a32c06eddabe64d2383ca31a5fed4aa08337e8db36eb8f7e6ebffeb55a82596` |
| `src/semaudit/explore/__init__.py` | `13f95927d8d384f472b4b02def14b8fe3ea0de710a6aebfd0c91bc0204e8d383` |
| `src/semaudit/extract/__init__.py` | `18a193641b0f7af2579fc8e2acc45a7dd519c00d26a4df89cd48bc141747c08a` |
| `src/semaudit/extract/messages.py` | `7945b0d120a1aee8ba169ff96ebe25825785aec3ed6727b1ab82212ef3a7403b` |
| `src/semaudit/graph/__init__.py` | `24461ca5a12b7bbd78a95af347351c45fd0fdc93f0349cd9d16d19ad8ea35dff` |
| `src/semaudit/models/__init__.py` | `b15c2c14dd8b66e22b3952fa53fa0e55455de796f5ba3054c7c7567a0ae2110b` |
| `src/semaudit/models/router.py` | `597371bfc0a4763a9cc4f85efb2f467410f60c15a0f207960f66b3ce0f92958d` |
| `src/semaudit/onboard/__init__.py` | `feb0e1221b537d926d02a5b442c978c823ecb6c3e563c4f5c81a8ec07524dc9a` |
| `src/semaudit/relate/__init__.py` | `205d745c72689b145fe22de4c0372e9d8a707be6a2e31ac0839ee35f5f9083f1` |
| `src/semaudit/relate/compare.py` | `2edc2ee98614de606340b927c0e20a91f440a147154fb3fa6f6292ba7345d12a` |
| `src/semaudit/relate/interpret.py` | `edc2bdd88adde864183dc77ebd24b22a710c6b8bd2bf18470e92bfc0a8f7ff6a` |
| `src/semaudit/relate/rules.py` | `d770e205eb3bad11b9b894f0031475578f6517b5421f23b7eaa45c2948817462` |
| `src/semaudit/report/__init__.py` | `e14481e5e1388a83ab8df167b6eb8ed79cc5a961b2ef53459bc255fad7485651` |
| `src/semaudit/report/manifest.py` | `874326ded648b0b5aaf2ff39ec805ff311a66fbc56b283291f836fe0c33fd081` |
| `src/semaudit/report/page.py` | `c732233c68c8ca45ef67c0a4b13f89f82d53ea82851b124d405905a4f03894b3` |
| `src/semaudit/report/review.py` | `5b05a19b4f12e26f5b5a83cdcdac24824e7c7fa9379ce3861c143138df7ece5d` |
| `src/semaudit/report/serve.py` | `c5c3d190f8107274782fca4ceb6960a4989f3dfdcb62e6fcc98f704f07ae1fab` |
| `src/semaudit/story/__init__.py` | `fbe6609e536df419aafbd7966e71483ecee99f97f20690f53751c70b951efeb2` |
| `src/semaudit/story/align.py` | `79f97e4c5943e434a2e55ecfa27e61fc3f704fad24a294ede5f4770ed34a2e8c` |
| `src/semaudit/story/build.py` | `6308de75158a20a83773404ef5d99b46853923f78623f1d6e811c97d9ae21f37` |
| `src/semaudit/story/episode.py` | `d15455292b8822028a18bab2d1e00406b236b80bf7bc159f0bd5fc155af44d6a` |
| `src/semaudit/story/model.py` | `d38c3a88617c9584a68bef9df9ff5caf817068dde300b29a83514d61b3f53592` |
| `src/semaudit/verify/__init__.py` | `99f2e7ce52d473f44b99c4a0a9fb55413738a080c59466dd033e3b99c53d789b` |
| `src/semaudit/verify/evidence.py` | `cd3d95e12390880f9a8759e689ab9103c770630f2b1cf2b39967cb64fad0624f` |
| `src/semaudit/verify/report.py` | `0ced15beda902dce1ea64ddf4ef1181d5f4934ac65e8f149d6b37ed312d1b6ef` |
| `src/semaudit/verify/steps.py` | `877bbcb4e791c8f769daa9c98e28a240343aef1d96557d818993b311fe9dbcbf` |
