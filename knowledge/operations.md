# Operations and evaluation notes

Evaluate retrieval separately from generation. First check whether the relevant passage appears in the returned top k. Then compare each answer claim with its cited passage. Also test missing facts and unavailable actions. A successful HTTP response or a valid source identifier does not prove that the generated answer is supported by the source.

Model APIs can fail because of missing permissions, unsupported model locations, quota limits or incomplete output. The controller records public step timings and call counts, returns an explicit failure and does not automatically retry. Logging metadata helps diagnose a request without copying private prompts, model reasoning or credentials into logs.

The demo limits generated output, the number of tool and model calls, and Cloud Run concurrency and instances. These limits reduce uncontrolled work but are not a fixed spending cap. Model inference, embedding requests, builds and stored images can incur charges. Delete the dedicated service after the exercise and review remaining build and image storage with the project administrator.
