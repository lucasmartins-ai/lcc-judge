# Preparation only — no training or final inference

This first data/protocol preparation is preserved. Before training, review found
that differing batch sizes and constructor RNG consumption would weaken the
frozen/last-two comparison. The replacement study `../direct-relevance-v1/`
uses equal batch sizes and explicitly resets both relevance heads at the same
seed boundary. No scored results or trained weights were selected/retried here.
