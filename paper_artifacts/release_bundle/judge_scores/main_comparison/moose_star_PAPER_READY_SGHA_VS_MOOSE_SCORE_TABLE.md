# Paper-Ready SGHA vs MOOSE-Star Formulation-Only Score Table

Scores are descriptive OpenRouter LLM-judge formulation-only assessments on a 0-10 rubric. No external novelty check, weighted composite, or pairwise preference is used.

| judge model | SGHA overall formulation quality | MOOSE-Star overall formulation quality | SGHA - MOOSE | criteria won by SGHA | criteria won by MOOSE | ties |
|---|---:|---:|---:|---:|---:|---:|
| anthropic/claude-sonnet-4 | 5.6 | 2.0 | 3.6 | 10 | 0 | 0 |
| openai/gpt-5.6-sol-pro | 5.2667 | 2.0 | 3.2667 | 10 | 0 | 0 |
| x-ai/grok-4.5 | 5.5333 | 2.3333 | 3.2 | 10 | 0 | 0 |
| moonshotai/kimi-k3 | 5.6667 | 2.4667 | 3.2 | 10 | 0 | 0 |
| google/gemini-3.6-flash | 5.6667 | 1.2 | 4.4667 | 10 | 0 | 0 |

## Across-Judge Aggregate

| method | candidate-judge scores | mean overall formulation quality | mean source-grounded specificity | mean formalizability |
|---|---:|---:|---:|---:|
| SGHA_FULL | 75 | 5.5467 | 5.2667 | 5.08 |
| MOOSE_STAR_PUBLIC_MODEL | 75 | 2.0 | 3.7467 | 1.5067 |
