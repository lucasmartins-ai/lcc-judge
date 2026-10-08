# Fixed generic-report control — completed negative diagnostic

Original validation-selectedBCE weights/receipts preserved; all three seeds,
no retraining or replay of base forwards. Fixed control question before new
inference: “Report the observed measurement and its value.” One control logit
perreport is subtracted with coefficient1 from the existing goal/report logit.
No label/slot is passed to the model; no anchor/coefficient tuning.

1632 actual new unique-report pair forwards,33414nonpadding tokens,maximum26
tokens, all complete. The original compact final is now exposed; this is not
independent transfer confirmation or a calibrated probability/likelihood.

| Three-seed mean final metric | Existing BCE | Subtracted control |
|---|---:|---:|
| Strict pooled AUC | .8279470 | .8226267 |
| Same-goal candidate ordering | .8541667 | .8450521 |
| Positive recall | .9687500 | .9687500 |
| Negative rejection | .3776042 | .3190104 |
| Same-report, two-goal contrast | .9179688 | .9179688 |

Every seed fails the unchanged gate. The same-report goal contrast is unchanged
because its shared control cancels exactly; it does not certify candidate ordering.
This closes this one report-salience control, not every possible calibration
method or a causal explanation of errors. Do not tune more anchors on this final.

Independent standard-library auditor verifies archived source/base/control input
identities, weight references, every subtraction, validation-only thresholds,
raw metrics, unchanged goal axis, accounting and failed gates without model/API
calls: `python -m research.audit_report_prior`. No default/P2/adoption.
