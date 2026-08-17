# MOOSE-Star Public-Model Ideas

## moose_star_public_reasoning_models_test_time_compute_001: MOOSE-Star hypothesis from Integration of symbolic reasoning with large language models (LLMs) to enhance their performance on first-order combinatorial reasoning problems.

- Domain: reasoning_models_test_time_compute
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: FCoReBench: Can Large Language Models Solve Challenging First-Order Combinatorial Reasoning Problems?

### Problem Statement

What are promising research problems in reasoning models and test-time computation suggested by recent literature?

### Motivation

Current methods struggle with solving NP-hard first-order reasoning problems, even when augmented with symbolic solvers. This gap limits the effectiveness of reasoning models in handling complex tasks that require multiple reasoning steps and structural understanding.

### Proposed Direction

The approach combines LLMs with symbolic solvers and program interpreters to guide the reasoning process. This integration allows the LLM to leverage the structured insights from symbolic reasoning, enhancing its ability to solve complex problems more effectively.

The methodology involves modifying the inference engine to accept symbolic constraints and use them to inform the LLM's reasoning. This system will handle both symbolic and generative tasks, ensuring that the LLM's reasoning is guided without requiring additional calls during test-time. This approach is robust and efficient, addressing the gap by providing a more effective way to handle complex reasoning tasks.

### Evaluation Plan

not provided

### Risks / Caveats

not provided
