# MOOSE-Star Public-Model Ideas

## moose_star_public_in_context_learning_001: MOOSE-Star hypothesis from Synthetic Noise Injection for In-Context Reinforcement Learning (ICRL)

- Domain: in_context_learning
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: Emergence of In-Context Reinforcement Learning from Noise Distillation

### Problem Statement

What are promising research problems in in-context learning suggested by recent literature?

### Motivation

Current in-context learning (ICL) methods require strict data generation from optimal policies or RL agents, limiting their applicability. AD^Îµ addresses this by enabling ICRL with synthetic noise, allowing for data acquisition without these strict requirements, thus enhancing flexibility and applicability.

### Proposed Direction

Synthetic noise is injected into training data to create a curriculum. This noise mimics real-world variations, helping the model learn robust features and improve generalization, especially under distribution shifts.

Modify the data acquisition process to include synthetic noise. Design noise to reflect real-world variations, then use these noisy examples to train the model, enhancing its in-context learning capabilities.

### Evaluation Plan

not provided

### Risks / Caveats

not provided

## moose_star_public_in_context_learning_002: MOOSE-Star hypothesis from Task-Inherent Attribute Guidelines (LongGuide) for Enhanced Long-form Generation

- Domain: in_context_learning
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: Beyond In-Context Learning: Enhancing Long-form Generation of Large Language Models via Task-Inherent Attribute Guidelines

### Problem Statement

What are promising research problems in in-context learning suggested by recent literature?

### Motivation

Existing in-context learning (ICL) methods lack explicit task guidelines, leading to suboptimal performance in long-form tasks like summarization. LongGuide provides structured instructions to improve model output quality and relevance.

### Proposed Direction

LongGuide consists of two types of guidelines:
  1. Metric Guidelines (MGs): Instruct the model to optimize specific metrics (e.g., accuracy, coherence) during generation.
  2. Output Constraint Guidelines (OCGs): Set constraints on token and sentence levels to ensure outputs meet task requirements.

1. Modify prompt engineering to include explicit task guidelines.
  2. Use tags or markers in prompts to signal the inclusion of MGs and OCGs.
  3. Integrate these guidelines with existing in-context learning mechanisms, such as prompt tuning, to enhance robustness and accuracy.

### Evaluation Plan

not provided

### Risks / Caveats

not provided

## moose_star_public_in_context_learning_003: MOOSE-Star hypothesis from Linear Attention Mechanism for Efficient In-Context Learning

- Domain: in_context_learning
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: TabFlex: Scaling Tabular Learning to Millions with Linear Attention

### Problem Statement

What are promising research problems in in-context learning suggested by recent literature?

### Motivation

Current in-context learning models suffer from quadratic computational complexity in attention mechanisms, which hinders scalability for large datasets. Linear attention addresses this inefficiency by reducing complexity from O(nÂ²) to O(n), enabling faster processing of large context data.

### Proposed Direction

The linear attention mechanism replaces the quadratic attention layers with linear transformations, optimizing the computation of attention scores. This approach preserves the effectiveness of attention while significantly improving efficiency.

The implementation involves identifying and replacing quadratic attention layers in the model with linear attention layers. This includes optimizing matrix multiplications and leveraging parallel processing to handle large feature and class sizes efficiently. Experiments will compare the new model's performance against existing ones using metrics like inference time and accuracy on large datasets.

### Evaluation Plan

not provided

### Risks / Caveats

not provided

## moose_star_public_in_context_learning_004: MOOSE-Star hypothesis from State-space models (SSMs) with gradient accumulation mechanism

- Domain: in_context_learning
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: State-space models can learn in-context by gradient descent

### Problem Statement

What are promising research problems in in-context learning suggested by recent literature?

### Motivation

This addresses the gap in existing methods by providing an efficient and effective way to learn from context, particularly in few-shot learning scenarios, and enhances robustness against distribution shifts.

### Proposed Direction

The SSM layer with local self-attention acts as a gradient accumulator, enabling the model to dynamically update parameters based on context, leading to better generalization and robustness.

Integrate the SSM layer into the existing in-context learning framework. Modify the model architecture to include this layer, train it using a least squares loss function, and validate its performance on various in-context tasks, focusing on few-shot learning and distribution shift scenarios.

### Evaluation Plan

not provided

### Risks / Caveats

not provided
