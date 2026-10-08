# Tool dependency preparation (historical preflight)

This records the completed preflight before the new worker and captures. The
subsequent [actual relation phase](../../tool-relations-grounded-v1/RESULTS.md)
installed these exact dependencies offline inside its confined image and captured
68 main fixtures. Statements below about pending captures describe that earlier
stage, not the current work queue. No dependency was installed on the host.

The current confined source image was inspected under the existing isolation
flags:Debian13/trixie has no Git, GCC or make. The first inspection supplied the
Python binary as a script by mistake and failed; the corrected -I -c probe is
saved in dependency-inspection-v2.json. No tool observation was admitted from
that failed probe.

A separate disposable image downloads Git and dependencies through APT. Before
any new measurement,31package files/23,006,960bytes were matched to SHA256 and
size from the retained APT package indexes. Exact versions, HTTPS pool URLs and
hashes are frozen in debian-packages.json. Git is1:2.47.3-0+deb13u1arm64, SHA
8c6b1e96b226211260d7814472215a8a1ed38ee37400c421d454391c1807cb5a.
The discovery Dockerfile uses live APT indexes; that alone is not a fixed future
recipe. The subsequent worker must install the exact saved/hash-checked blobs
offline from the original immutable Python base. The full APT fetch image stays
local; no package was installed on the host.

Tenacity9.1.4pure-Python wheel was fetched with verifiedTLS from the immutable
PyPI file URL and checked SHA6095a360c919085f28c6527de529e76a06ad89b23659fa881ae0649b867a9d55.
Its manifest is tenacity.json; it is not installed on the host or executed in a
fixture yet. Git/Tenacity dependencies are private ignored artifacts under
release-staging/tool-worker-deps-v1/, separately from public source/receipts.
No generated-fixture API, current trusted worker, data protocol, scorer or LCC
default was changed. This preparation does not show retry/network/Git quality.

Next: new bounded trusted worker and regressions, immutable image/source/dependency
freeze, calibration with actual Git/Retrying/socket events, then fresh fixture
splits and independent raw audits before model adaptation. Preserve first errors;
retry artifact downloads separately from experimental execution.
