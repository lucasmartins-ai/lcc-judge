# Encoder Bake-off — Results (Sprint 2)

Devices: `mps` · depths (tiktoken cl100k tokens): [0, 64, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768] · AUC bar for effective context: 0.9 · probe suite versions: 1.0, 1.1, 1.2 (rows are version-tagged; cross-version D/AUC comparisons need care)

Two families: AUC_detect = fact vs unrelated filler; AUC_judge = incident vs healthy lookalike. Lexical shortcuts remain possible: these labels do not establish necessity, KEEP relevance or numerical reasoning. Effective context = largest depth with AUC >= bar per family. Depth 0 = control (decisive line alone). Latency is per (objective, block) score call.
Gate AUC is strict P(fact > noise): ties contribute zero. Effective context uses unrounded AUC; 0 is the report sentinel when no depth passes. Historical experiment entries retain their original measurements. Compare models only on identical case IDs, probe versions and input/window settings. Older rows lack execution provenance; the device list records available metadata and does not certify legacy timings as CPU.

## Summary

| model | params (M) | window | eff.ctx detect | eff.ctx judge | D@0 | D@64 | D@256 | D@512 | D@1024 | D@2048 | D@4096 | D@8192 | D@16384 | D@32768 | J@0 | J@64 | J@256 | J@512 | J@1024 | J@2048 | J@4096 | J@8192 | J@16384 | J@32768 | p50 ms @256 | p50 ms @4K | load s | RSS Δ GB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lexical-overlap | 0 | 1000000000 | 0 | 0 | 0.70 (n=8) | 0.69 (n=8) | 0.70 (n=8) | 0.66 (n=8) | 0.66 (n=8) | 0.66 (n=8) | 0.69 (n=8) | 0.66 (n=8) | — | — | 0.45 (n=8) | 0.47 (n=8) | 0.52 (n=8) | 0.47 (n=8) | 0.47 (n=8) | 0.45 (n=8) | 0.47 (n=8) | 0.44 (n=8) | — | — | 0.1 | 0.4 | 0.0 | 0.0 |
| laya-multilingual | 0 | 1024 | 0 | 0 | 0.25 (n=8) | 0.66 (n=8) | 0.47 (n=8) | 0.45 (n=8) | 0.56 (n=8) | 0.58 (n=8) | 0.41 (n=8) | 0.52 (n=8) | — | — | 0.38 (n=8) | 0.53 (n=8) | 0.42 (n=8) | 0.41 (n=8) | 0.59 (n=8) | 0.55 (n=8) | 0.62 (n=8) | 0.31 (n=8) | — | — | 297.4 | 361.9 | 4.74 | 2.711 |
| laya-typed-decisions | 0 | 1024 | 0 | 0 | 0.92 (n=8) | 0.67 (n=8) | 0.56 (n=8) | 0.78 (n=8) | 0.48 (n=8) | 0.62 (n=8) | 0.50 (n=8) | 0.61 (n=8) | — | — | 0.70 (n=8) | 0.52 (n=8) | 0.58 (n=8) | 0.52 (n=8) | 0.36 (n=8) | 0.45 (n=8) | 0.80 (n=8) | 0.53 (n=8) | — | — | 582.2 | 782.0 | 1.01 | 0.748 |
| laya-lcc-relevance-v1 | 0 | 1024 | 0 | 0 | 0.28 (n=8) | 0.62 (n=8) | 0.44 (n=8) | 0.62 (n=8) | 0.70 (n=8) | 0.53 (n=8) | 0.64 (n=8) | 0.62 (n=8) | — | — | 0.38 (n=8) | 0.45 (n=8) | 0.41 (n=8) | 0.44 (n=8) | 0.70 (n=8) | 0.28 (n=8) | 0.53 (n=8) | 0.34 (n=8) | — | — | 291.1 | 352.8 | 2.17 | 0.0 |
| minilm-msmarco-ce | 23 | 512 | 0 | 0 | 0.89 (n=8) | 0.77 (n=8) | 0.58 (n=8) | 0.50 (n=8) | 0.41 (n=8) | 0.47 (n=8) | 0.50 (n=8) | 0.62 (n=8) | — | — | 0.58 (n=8) | 0.47 (n=8) | 0.53 (n=8) | 0.39 (n=8) | 0.39 (n=8) | 0.48 (n=8) | 0.55 (n=8) | 0.56 (n=8) | — | — | 27.8 | 29.8 | 3.97 | 0.329 |
| bge-small-en-v1.5 | 33 | 512 | 0 | 0 | 0.58 (n=8) | 0.70 (n=8) | 0.56 (n=8) | 0.58 (n=8) | 0.45 (n=8) | 0.45 (n=8) | 0.53 (n=8) | 0.66 (n=8) | — | — | 0.42 (n=8) | 0.52 (n=8) | 0.48 (n=8) | 0.39 (n=8) | 0.47 (n=8) | 0.44 (n=8) | 0.56 (n=8) | 0.55 (n=8) | — | — | 48.2 | 51.5 | 0.76 | 0.008 |
| ModernBERT-base | 149 | 8192 | 0 | 0 | 0.75 (n=8) | 0.77 (n=8) | 0.81 (n=8) | 0.88 (n=8) | 0.77 (n=8) | 0.64 (n=8) | 0.64 (n=8) | 0.58 (n=8) | — | — | 0.45 (n=8) | 0.47 (n=8) | 0.44 (n=8) | 0.73 (n=8) | 0.53 (n=8) | 0.52 (n=8) | 0.55 (n=8) | 0.56 (n=8) | — | — | 186.6 | 3133.8 | 3.51 | 0.37 |
| gte-multilingual-base | ERROR: load failed: ValueError: Alibaba-NLP/new-impl You can inspect the repository content at https://hf.co/Alibaba-NLP/gte-multilingual-base.
Please pass the argument `trust_remote_code=True` to allow cust |
| specialist-exp02-512 | 149 | 512 | 0 | 0 | 0.81 (n=8) | 0.28 (n=8) | 0.44 (n=8) | 0.45 (n=8) | 0.48 (n=8) | 0.62 (n=8) | 0.45 (n=8) | 0.64 (n=8) | — | — | 0.69 (n=8) | 0.47 (n=8) | 0.56 (n=8) | 0.33 (n=8) | 0.39 (n=8) | 0.53 (n=8) | 0.50 (n=8) | 0.58 (n=8) | — | — | 160.4 | 164.8 | 3.83 | 0.37 |
| specialist-exp02-8k | 149 | 8192 | 0 | 0 | 0.81 (n=8) | 0.28 (n=8) | 0.23 (n=8) | 0.00 (n=8) | 0.11 (n=8) | 0.23 (n=8) | 0.38 (n=8) | 0.31 (n=8) | — | — | 0.69 (n=8) | 0.47 (n=8) | 0.47 (n=8) | 0.42 (n=8) | 0.17 (n=8) | 0.41 (n=8) | 0.45 (n=8) | 0.42 (n=8) | — | — | 176.8 | 2816.8 | 0.84 | 0.008 |
| specialist-exp02c-512 | 149 | 512 | 0 | 256 | 0.58 (n=8) | 0.73 (n=8) | 0.70 (n=8) | 0.69 (n=8) | 0.44 (n=8) | 0.75 (n=8) | 0.62 (n=8) | 0.53 (n=8) | — | — | 0.72 (n=8) | 0.89 (n=8) | 0.92 (n=8) | 0.78 (n=8) | 0.30 (n=8) | 0.45 (n=8) | 0.69 (n=8) | 0.55 (n=8) | — | — | 155.0 | 158.7 | 4.43 | 0.371 |
| specialist-exp02c-1k | 149 | 1024 | 512 | 256 | 0.58 (n=8) | 0.73 (n=8) | 0.72 (n=8) | 0.95 (n=8) | 0.48 (n=8) | 0.72 (n=8) | 0.44 (n=8) | 0.67 (n=8) | — | — | 0.72 (n=8) | 0.89 (n=8) | 0.95 (n=8) | 0.83 (n=8) | 0.42 (n=8) | 0.59 (n=8) | 0.75 (n=8) | 0.69 (n=8) | — | — | 191.9 | 333.7 | 1.01 | 0.008 |
| specialist-exp02c-8k | 149 | 8192 | 2048 | 2048 | 0.58 (n=8) | 0.73 (n=8) | 0.72 (n=8) | 0.95 (n=8) | 0.73 (n=8) | 1.00 (n=8) | 0.69 (n=8) | 0.38 (n=8) | — | — | 0.72 (n=8) | 0.89 (n=8) | 0.95 (n=8) | 0.83 (n=8) | 0.91 (n=8) | 0.94 (n=8) | 0.89 (n=8) | 0.61 (n=8) | — | — | 200.3 | 3230.8 | 3.61 | 0.371 |
| specialist-exp02c-12k | 149 | 12288 | 0 | 0 | — | — | — | — | — | — | — | 0.86 (n=8) | — | — | — | — | — | — | — | — | — | 0.88 (n=8) | — | — | None | None | 2.94 | 0.37 |
| specialist-exp03-extrap-49k | 149 | 49152 | 0 | 0 | — | — | — | — | — | — | — | 0.86 (n=8) | 0.78 (n=8) | 0.64 (n=8) | — | — | — | — | — | — | — | 0.88 (n=8) | 0.89 (n=8) | 0.72 (n=8) | None | None | 4.76 | 0.381 |
| specialist-exp03-dynamic-49k | 149 | 49152 | 0 | 0 | 0.55 | — | — | 0.56 | — | — | 0.56 | 0.56 | 0.57 | 0.75 (n=8) | 0.66 | — | — | 0.68 | — | — | 0.74 | 0.74 | 0.73 | 0.83 (n=8) | None | 621.6 | 4.39 | 0.379 |
| specialist-exp04-frozen-dyn-49k | 149 | 49152 | 0 | 0 | 0.56 | — | — | 0.55 | — | — | — | — | — | — | 0.66 | — | — | 0.72 | — | — | — | — | — | — | None | None | 3.08 | 0.383 |
| specialist-exp04-unfreeze2-dyn-49k | 149 | 49152 | 0 | 0 | 0.59 | — | — | 0.53 | — | — | 0.62 (n=4) | — | 0.51 | — | 0.69 | — | — | 0.78 | — | — | 0.75 (n=4) | — | 0.76 | — | None | 631.4 | 3.39 | 0.455 |
| specialist-exp05-frozen-8k | 149 | 8192 | 0 | 0 | 0.67 | — | — | 0.66 | — | — | 0.66 | 0.55 | — | — | 0.66 | — | — | 0.71 | — | — | 0.75 | 0.63 | — | — | None | 1201.1 | 3.95 | 0.381 |
| specialist-exp05-unfreeze2-8k | 149 | 8192 | 0 | 0 | 0.76 | — | — | 0.71 | — | — | 0.70 | 0.55 | — | — | 0.75 | — | — | 0.81 | — | — | 0.82 | 0.62 | — | — | None | 637.5 | 3.02 | 0.459 |

## Per-depth detail

### lexical-overlap

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.703 | 0.453 | 0.189 | 0.065 | 0.172 | 0.0 | 0 |
| 64 | 8 | 0.688 | 0.469 | 0.251 | 0.107 | 0.229 | 0.0 | 0 |
| 256 | 8 | 0.703 | 0.516 | 0.265 | 0.123 | 0.233 | 0.1 | 0 |
| 512 | 8 | 0.656 | 0.469 | 0.251 | 0.123 | 0.233 | 0.1 | 0 |
| 1024 | 8 | 0.656 | 0.469 | 0.251 | 0.123 | 0.233 | 0.1 | 0 |
| 2048 | 8 | 0.656 | 0.453 | 0.251 | 0.123 | 0.249 | 0.2 | 0 |
| 4096 | 8 | 0.688 | 0.469 | 0.266 | 0.123 | 0.247 | 0.4 | 0 |
| 8192 | 8 | 0.656 | 0.438 | 0.251 | 0.123 | 0.247 | 0.7 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### laya-multilingual

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.25 | 0.375 | 0.851 | 0.795 | 0.867 | 83.8 | 0 |
| 64 | 8 | 0.656 | 0.531 | 0.868 | 0.849 | 0.947 | 213.4 | 0 |
| 256 | 8 | 0.469 | 0.422 | 0.845 | 0.93 | 0.899 | 297.4 | 0 |
| 512 | 8 | 0.453 | 0.406 | 0.94 | 0.921 | 0.917 | 364.7 | 0 |
| 1024 | 8 | 0.562 | 0.594 | 0.935 | 0.86 | 0.872 | 362.5 | 0 |
| 2048 | 8 | 0.578 | 0.547 | 0.942 | 0.926 | 0.913 | 378.5 | 0 |
| 4096 | 8 | 0.406 | 0.625 | 0.879 | 0.896 | 0.826 | 361.9 | 0 |
| 8192 | 8 | 0.516 | 0.312 | 0.899 | 0.922 | 0.931 | 366.1 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### laya-typed-decisions

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.922 | 0.703 | 0.566 | 0.446 | 0.539 | 177.6 | 0 |
| 64 | 8 | 0.672 | 0.516 | 0.5 | 0.478 | 0.499 | 404.9 | 0 |
| 256 | 8 | 0.562 | 0.578 | 0.496 | 0.494 | 0.489 | 582.2 | 0 |
| 512 | 8 | 0.781 | 0.516 | 0.495 | 0.476 | 0.495 | 769.1 | 0 |
| 1024 | 8 | 0.484 | 0.359 | 0.48 | 0.485 | 0.489 | 790.9 | 0 |
| 2048 | 8 | 0.625 | 0.453 | 0.486 | 0.477 | 0.494 | 778.5 | 0 |
| 4096 | 8 | 0.5 | 0.797 | 0.489 | 0.484 | 0.467 | 782.0 | 0 |
| 8192 | 8 | 0.609 | 0.531 | 0.482 | 0.475 | 0.481 | 780.0 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### laya-lcc-relevance-v1

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.281 | 0.375 | 0.54 | 0.735 | 0.654 | 84.2 | 0 |
| 64 | 8 | 0.625 | 0.453 | 0.663 | 0.65 | 0.759 | 198.3 | 0 |
| 256 | 8 | 0.438 | 0.406 | 0.613 | 0.673 | 0.669 | 291.1 | 0 |
| 512 | 8 | 0.625 | 0.438 | 0.739 | 0.624 | 0.722 | 344.8 | 0 |
| 1024 | 8 | 0.703 | 0.703 | 0.745 | 0.614 | 0.649 | 352.7 | 0 |
| 2048 | 8 | 0.531 | 0.281 | 0.683 | 0.674 | 0.734 | 349.4 | 0 |
| 4096 | 8 | 0.641 | 0.531 | 0.664 | 0.596 | 0.589 | 352.8 | 0 |
| 8192 | 8 | 0.625 | 0.344 | 0.697 | 0.669 | 0.757 | 352.5 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### minilm-msmarco-ce

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.891 | 0.578 | 0.092 | 0.006 | 0.091 | 8.8 | 0 |
| 64 | 8 | 0.766 | 0.469 | 0.168 | 0.005 | 0.075 | 21.4 | 0 |
| 256 | 8 | 0.578 | 0.531 | 0.078 | 0.027 | 0.041 | 27.8 | 0 |
| 512 | 8 | 0.5 | 0.391 | 0.001 | 0.0 | 0.015 | 26.3 | 0 |
| 1024 | 8 | 0.406 | 0.391 | 0.03 | 0.005 | 0.033 | 26.0 | 0 |
| 2048 | 8 | 0.469 | 0.484 | 0.077 | 0.007 | 0.047 | 27.3 | 0 |
| 4096 | 8 | 0.5 | 0.547 | 0.043 | 0.03 | 0.012 | 29.8 | 0 |
| 8192 | 8 | 0.625 | 0.562 | 0.008 | 0.001 | 0.002 | 35.2 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### bge-small-en-v1.5

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.578 | 0.422 | 0.81 | 0.801 | 0.812 | 23.8 | 0 |
| 64 | 8 | 0.703 | 0.516 | 0.812 | 0.791 | 0.808 | 39.4 | 0 |
| 256 | 8 | 0.562 | 0.484 | 0.804 | 0.802 | 0.804 | 48.2 | 0 |
| 512 | 8 | 0.578 | 0.391 | 0.797 | 0.791 | 0.804 | 48.2 | 0 |
| 1024 | 8 | 0.453 | 0.469 | 0.8 | 0.797 | 0.801 | 48.8 | 0 |
| 2048 | 8 | 0.453 | 0.438 | 0.798 | 0.798 | 0.807 | 50.4 | 0 |
| 4096 | 8 | 0.531 | 0.562 | 0.8 | 0.8 | 0.794 | 51.5 | 0 |
| 8192 | 8 | 0.656 | 0.547 | 0.801 | 0.791 | 0.797 | 56.9 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### ModernBERT-base

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.75 | 0.453 | 0.939 | 0.928 | 0.94 | 66.8 | 0 |
| 64 | 8 | 0.766 | 0.469 | 0.899 | 0.889 | 0.901 | 128.1 | 0 |
| 256 | 8 | 0.812 | 0.438 | 0.882 | 0.868 | 0.884 | 186.6 | 0 |
| 512 | 8 | 0.875 | 0.734 | 0.866 | 0.851 | 0.863 | 257.0 | 0 |
| 1024 | 8 | 0.766 | 0.531 | 0.835 | 0.825 | 0.834 | 479.1 | 0 |
| 2048 | 8 | 0.641 | 0.516 | 0.811 | 0.807 | 0.81 | 1087.7 | 0 |
| 4096 | 8 | 0.641 | 0.547 | 0.798 | 0.793 | 0.798 | 3133.8 | 0 |
| 8192 | 8 | 0.578 | 0.562 | 0.789 | 0.787 | 0.788 | 7987.1 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### specialist-exp02-512

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.812 | 0.688 | 0.552 | 0.419 | 0.468 | 58.2 | 0 |
| 64 | 8 | 0.281 | 0.469 | 0.474 | 0.58 | 0.483 | 127.3 | 0 |
| 256 | 8 | 0.438 | 0.562 | 0.549 | 0.571 | 0.543 | 160.4 | 0 |
| 512 | 8 | 0.453 | 0.328 | 0.601 | 0.611 | 0.637 | 160.3 | 0 |
| 1024 | 8 | 0.484 | 0.391 | 0.599 | 0.597 | 0.616 | 161.3 | 0 |
| 2048 | 8 | 0.625 | 0.531 | 0.611 | 0.585 | 0.607 | 162.9 | 0 |
| 4096 | 8 | 0.453 | 0.5 | 0.611 | 0.598 | 0.6 | 164.8 | 0 |
| 8192 | 8 | 0.641 | 0.578 | 0.625 | 0.586 | 0.608 | 170.3 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### specialist-exp02-8k

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.812 | 0.688 | 0.552 | 0.419 | 0.468 | 57.2 | 0 |
| 64 | 8 | 0.281 | 0.469 | 0.474 | 0.58 | 0.483 | 124.8 | 0 |
| 256 | 8 | 0.234 | 0.469 | 0.608 | 0.652 | 0.613 | 176.8 | 0 |
| 512 | 8 | 0.0 | 0.422 | 0.699 | 0.743 | 0.704 | 254.9 | 0 |
| 1024 | 8 | 0.109 | 0.172 | 0.744 | 0.768 | 0.762 | 458.9 | 0 |
| 2048 | 8 | 0.234 | 0.406 | 0.763 | 0.771 | 0.767 | 1016.2 | 0 |
| 4096 | 8 | 0.375 | 0.453 | 0.766 | 0.77 | 0.769 | 2816.8 | 0 |
| 8192 | 8 | 0.312 | 0.422 | 0.764 | 0.767 | 0.766 | 6973.4 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### specialist-exp02c-512

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.578 | 0.719 | 0.475 | 0.41 | 0.25 | 53.8 | 0 |
| 64 | 8 | 0.734 | 0.891 | 0.458 | 0.273 | 0.139 | 119.1 | 0 |
| 256 | 8 | 0.703 | 0.922 | 0.54 | 0.312 | 0.127 | 155.0 | 0 |
| 512 | 8 | 0.688 | 0.781 | 0.337 | 0.213 | 0.153 | 154.5 | 0 |
| 1024 | 8 | 0.438 | 0.297 | 0.194 | 0.29 | 0.321 | 153.6 | 0 |
| 2048 | 8 | 0.75 | 0.453 | 0.21 | 0.15 | 0.297 | 155.1 | 0 |
| 4096 | 8 | 0.625 | 0.688 | 0.296 | 0.219 | 0.177 | 158.7 | 0 |
| 8192 | 8 | 0.531 | 0.547 | 0.172 | 0.156 | 0.133 | 163.4 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### specialist-exp02c-1k

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.578 | 0.719 | 0.475 | 0.41 | 0.25 | 58.2 | 0 |
| 64 | 8 | 0.734 | 0.891 | 0.458 | 0.273 | 0.139 | 126.7 | 0 |
| 256 | 8 | 0.719 | 0.953 | 0.54 | 0.305 | 0.11 | 191.9 | 0 |
| 512 | 8 | 0.953 | 0.828 | 0.613 | 0.193 | 0.247 | 267.2 | 0 |
| 1024 | 8 | 0.484 | 0.422 | 0.289 | 0.326 | 0.355 | 322.2 | 0 |
| 2048 | 8 | 0.719 | 0.594 | 0.418 | 0.244 | 0.37 | 319.5 | 0 |
| 4096 | 8 | 0.438 | 0.75 | 0.331 | 0.38 | 0.185 | 333.7 | 0 |
| 8192 | 8 | 0.672 | 0.688 | 0.234 | 0.179 | 0.16 | 339.8 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### specialist-exp02c-8k

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 0.578 | 0.719 | 0.475 | 0.41 | 0.25 | 62.4 | 0 |
| 64 | 8 | 0.734 | 0.891 | 0.458 | 0.273 | 0.139 | 139.8 | 0 |
| 256 | 8 | 0.719 | 0.953 | 0.54 | 0.305 | 0.11 | 200.3 | 0 |
| 512 | 8 | 0.953 | 0.828 | 0.613 | 0.193 | 0.247 | 301.9 | 0 |
| 1024 | 8 | 0.734 | 0.906 | 0.577 | 0.366 | 0.151 | 532.8 | 0 |
| 2048 | 8 | 1.0 | 0.938 | 0.522 | 0.051 | 0.099 | 1173.2 | 0 |
| 4096 | 8 | 0.688 | 0.891 | 0.486 | 0.295 | 0.097 | 3230.8 | 0 |
| 8192 | 8 | 0.375 | 0.609 | 0.619 | 0.609 | 0.583 | 8195.0 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### specialist-exp02c-12k

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | None | None | None | None | None | None | 0 |
| 64 | 0 | None | None | None | None | None | None | 0 |
| 256 | 0 | None | None | None | None | None | None | 0 |
| 512 | 0 | None | None | None | None | None | None | 0 |
| 1024 | 0 | None | None | None | None | None | None | 0 |
| 2048 | 0 | None | None | None | None | None | None | 0 |
| 4096 | 0 | None | None | None | None | None | None | 0 |
| 8192 | 8 | 0.859 | 0.875 | 0.448 | 0.144 | 0.132 | 8951.8 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### specialist-exp03-extrap-49k

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | None | None | None | None | None | None | 0 |
| 64 | 0 | None | None | None | None | None | None | 0 |
| 256 | 0 | None | None | None | None | None | None | 0 |
| 512 | 0 | None | None | None | None | None | None | 0 |
| 1024 | 0 | None | None | None | None | None | None | 0 |
| 2048 | 0 | None | None | None | None | None | None | 0 |
| 4096 | 0 | None | None | None | None | None | None | 0 |
| 8192 | 8 | 0.859 | 0.875 | 0.448 | 0.144 | 0.132 | 1988.7 | 0 |
| 16384 | 8 | 0.781 | 0.891 | 0.642 | 0.303 | 0.183 | 7402.6 | 0 |
| 32768 | 8 | 0.641 | 0.719 | 0.613 | 0.499 | 0.304 | 37881.2 | 0 |

### specialist-exp03-dynamic-49k

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 62 | 0.554 | 0.657 | 0.378 | 0.319 | 0.229 | 18.4 | 0 |
| 64 | 0 | None | None | None | None | None | None | 0 |
| 256 | 0 | None | None | None | None | None | None | 0 |
| 512 | 62 | 0.561 | 0.684 | 0.415 | 0.346 | 0.24 | 68.5 | 0 |
| 1024 | 0 | None | None | None | None | None | None | 0 |
| 2048 | 0 | None | None | None | None | None | None | 0 |
| 4096 | 62 | 0.562 | 0.743 | 0.247 | 0.186 | 0.084 | 621.6 | 0 |
| 8192 | 62 | 0.563 | 0.741 | 0.234 | 0.199 | 0.106 | 1939.8 | 0 |
| 16384 | 62 | 0.571 | 0.726 | 0.266 | 0.186 | 0.12 | 6920.5 | 0 |
| 32768 | 8 | 0.75 | 0.828 | 0.4 | 0.17 | 0.119 | 37144.4 | 0 |

### specialist-exp04-frozen-dyn-49k

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 62 | 0.563 | 0.657 | 0.707 | 0.653 | 0.541 | 18.6 | 0 |
| 64 | 0 | None | None | None | None | None | None | 0 |
| 256 | 0 | None | None | None | None | None | None | 0 |
| 512 | 62 | 0.549 | 0.722 | 0.307 | 0.227 | 0.115 | 68.2 | 0 |
| 1024 | 0 | None | None | None | None | None | None | 0 |
| 2048 | 0 | None | None | None | None | None | None | 0 |
| 4096 | 0 | None | None | None | None | None | None | 0 |
| 8192 | 0 | None | None | None | None | None | None | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### specialist-exp04-unfreeze2-dyn-49k

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 62 | 0.586 | 0.691 | 0.54 | 0.46 | 0.348 | 18.4 | 0 |
| 64 | 0 | None | None | None | None | None | None | 0 |
| 256 | 0 | None | None | None | None | None | None | 0 |
| 512 | 62 | 0.531 | 0.779 | 0.322 | 0.311 | 0.099 | 68.0 | 0 |
| 1024 | 0 | None | None | None | None | None | None | 0 |
| 2048 | 0 | None | None | None | None | None | None | 0 |
| 4096 | 4 | 0.625 | 0.75 | 0.202 | 0.088 | 0.003 | 631.4 | 0 |
| 8192 | 0 | None | None | None | None | None | None | 0 |
| 16384 | 62 | 0.511 | 0.756 | 0.229 | 0.205 | 0.07 | 6943.3 | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### specialist-exp05-frozen-8k

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 62 | 0.673 | 0.658 | 0.537 | 0.349 | 0.371 | 57.5 | 0 |
| 64 | 0 | None | None | None | None | None | None | 0 |
| 256 | 0 | None | None | None | None | None | None | 0 |
| 512 | 62 | 0.658 | 0.712 | 0.355 | 0.188 | 0.163 | 142.9 | 0 |
| 1024 | 0 | None | None | None | None | None | None | 0 |
| 2048 | 0 | None | None | None | None | None | None | 0 |
| 4096 | 62 | 0.66 | 0.748 | 0.268 | 0.1 | 0.083 | 1201.1 | 0 |
| 8192 | 62 | 0.545 | 0.632 | 0.587 | 0.554 | 0.442 | 2538.9 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

### specialist-exp05-unfreeze2-8k

| depth | n | AUC detect | AUC judge | fact | unrelated | decoy | p50 ms | errors |
|---|---|---|---|---|---|---|---|---|
| 0 | 62 | 0.76 | 0.748 | 0.241 | 0.067 | 0.079 | 18.8 | 0 |
| 64 | 0 | None | None | None | None | None | None | 0 |
| 256 | 0 | None | None | None | None | None | None | 0 |
| 512 | 62 | 0.713 | 0.815 | 0.354 | 0.125 | 0.086 | 71.2 | 0 |
| 1024 | 0 | None | None | None | None | None | None | 0 |
| 2048 | 0 | None | None | None | None | None | None | 0 |
| 4096 | 62 | 0.702 | 0.824 | 0.26 | 0.06 | 0.043 | 637.5 | 0 |
| 8192 | 62 | 0.549 | 0.619 | 0.418 | 0.376 | 0.316 | 1435.1 | 0 |
| 16384 | 0 | None | None | None | None | None | None | 0 |
| 32768 | 0 | None | None | None | None | None | None | 0 |

## Reading notes

- `truncated` rows show where the model's tokenizer silently cut the block: the declared window is an upper bound, the curve is the truth.
- Bi-encoder cosine scores dilute single facts in long blocks even before truncation; that is real effective-context loss, not a harness artifact.
- The decoy family compares incident and healthy observations. Lexical shortcuts remain possible; use a lexical control. These labels do not establish necessity, KEEP relevance or numerical reasoning. A constant score has strict AUC=0 because pairs tie.
- Laya rows probe the *raw* model beyond LCC's production budget (LCC refuses states over 831 tokens and keeps blocks whole instead).
- Depth is counted in tiktoken tokens; each model sees its own tokenizer's count.
