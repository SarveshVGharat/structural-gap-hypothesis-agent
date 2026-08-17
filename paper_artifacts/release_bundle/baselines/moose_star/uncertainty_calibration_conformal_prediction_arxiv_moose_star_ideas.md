# MOOSE-Star Public-Model Ideas

## moose_star_public_uncertainty_calibration_conformal_prediction_arxiv_001: MOOSE-Star hypothesis from Semi-Supervised Conformal Prediction with Unlabeled Nonconformity Scores

- Domain: uncertainty_calibration_conformal_prediction_arxiv
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: Semi-Supervised Conformal Prediction With Unlabeled Nonconformity Score

### Problem Statement

What are promising research problems in uncertainty estimation, calibration, and conformal prediction suggested by recent literature?

### Motivation

Conformal prediction methods often require extensive labeled data, which is often scarce in real-world applications. This limitation can lead to unstable coverage performance. The use of unlabeled data addresses this gap by leveraging the abundance of unlabeled data to improve the robustness and accuracy of uncertainty estimates, thereby enhancing the reliability of conformal prediction models.

### Proposed Direction

The method employs Nearest Neighbor Matching (NNM) to estimate nonconformity scores for unlabeled samples. By using the most similar pseudo-labeled counterparts during the calibration phase, the approach allows the model to adjust its prediction sets more effectively, even with limited labeled data. This results in improved coverage guarantees and more reliable uncertainty quantification.

The implementation involves several steps:
  1. Data Collection: Gather unlabeled data alongside existing labeled data.
  2. Preprocessing: Organize the data to facilitate matching between unlabeled and labeled samples.
  3. NNM Application: For each unlabeled sample, identify the most similar labeled sample using NNM to estimate the nonconformity score.
  4. Adjustment of Prediction Sets: Use the estimated nonconformity scores to refine the prediction sets, ensuring they maintain the desired coverage level.
  5. Validation: Test the adjusted prediction sets to confirm improved coverage performance and reliability.

This approach effectively integrates unlabeled data into the conformal prediction framework, enhancing its applicability and robustness in scenarios where labeled data is limited.

### Evaluation Plan

not provided

### Risks / Caveats

not provided

## moose_star_public_uncertainty_calibration_conformal_prediction_arxiv_002: MOOSE-Star hypothesis from Symmetrization of Conformity Scores for CounterfactuallyFairUncertaintyQuantification

- Domain: uncertainty_calibration_conformal_prediction_arxiv
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: Counterfactually Fair Conformal Prediction

### Problem Statement

What are promising research problems in uncertainty estimation, calibration, and conformal prediction suggested by recent literature?

### Motivation

Current conformal prediction methods lack mechanisms to ensure fairness across different demographic or sensitive attributes, which is crucial for equitable decision-making in real-world applications. The introduction of counterfactually fair conformal prediction addresses this gap by ensuring that prediction sets are fair across all groups while maintaining their accuracy and coverage properties.

### Proposed Direction

The method symmetrizes conformity scores across different attribute interventions, effectively creating multiple conformal scores for each prediction. This ensures that the prediction sets are fair by considering counterfactual scenarios where each attribute is manipulated to different values, thereby balancing the influence of each attribute on the prediction sets.

The integration involves modifying the training process of conformal predictors to include attribute interventions. For each attribute, the conformity score is computed under different scenarios (e.g., attribute values being set to their original or counterfactual values). These scores are then averaged or combined in a way that ensures fairness across all groups. This approach does not require retraining the model but instead leverages existing training data with attribute interventions to produce fair prediction sets.

### Evaluation Plan

not provided

### Risks / Caveats

not provided

## moose_star_public_uncertainty_calibration_conformal_prediction_arxiv_003: MOOSE-Star hypothesis from Selective Classification for Uncertainty Handling in Conformal Predictions

- Domain: uncertainty_calibration_conformal_prediction_arxiv
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: Uncertainty Quantification on Clinical Trial Outcome Prediction

### Problem Statement

What are promising research problems in uncertainty estimation, calibration, and conformal prediction suggested by recent literature?

### Motivation

Current methods in uncertainty estimation and conformal predictions may struggle with ambiguous or low-confidence samples, leading to poor prediction accuracy. The selective classification approach from the inspiration paper addresses this gap by enabling models to focus on uncertain samples, thereby improving overall performance and reliability in complex or ambiguous data scenarios.

### Proposed Direction

The selective classification approach involves training a model to distinguish between ambiguous and non-ambiguous samples. This is achieved by integrating a selective classifier alongside the main model, which guides predictions based on the uncertainty levels of the samples. The classifier helps the model prioritize uncertain instances, ensuring more accurate predictions in challenging cases.

To implement this, the model architecture is modified to include a selective classification component. This involves training the selective classifier using a subset of high-uncertainty data. The training process is adjusted to incorporate this new layer, allowing the model to adjust predictions dynamically based on the uncertainty levels. The integration ensures that the model can effectively handle ambiguous samples, enhancing its overall performance and reliability.

### Evaluation Plan

not provided

### Risks / Caveats

not provided

## moose_star_public_uncertainty_calibration_conformal_prediction_arxiv_004: MOOSE-Star hypothesis from Integration of optimization algorithms (GWO, BO, PSO) and uncertainty-aware loss function into Monte Carlo Dropout (MCD) for enhanced uncertainty quantification.

- Domain: uncertainty_calibration_conformal_prediction_arxiv
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: Enhancing Monte Carlo Dropout Performance for Uncertainty Quantification

### Problem Statement

What are promising research problems in uncertainty estimation, calibration, and conformal prediction suggested by recent literature?

### Motivation

Current MCD methods struggle with providing well-calibrated uncertainty estimates, which is crucial for high-stakes applications. By integrating optimization algorithms and a loss function, we aim to improve both the accuracy and calibration of uncertainty estimates, addressing a significant gap in existing methods.

### Proposed Direction

The integration involves using GWO, BO, and PSO to optimize dropout parameters during the MCD process. These optimizers adjust dropout rates to better reflect uncertainty, while the uncertainty-aware loss function guides the model to learn accurate uncertainty estimates. The loss function penalizes poor uncertainty estimates, encouraging the model to improve calibration.

1. Select a backbone model (e.g., ResNet50) and apply MCD as the base method.
  2. Incorporate GWO, BO, and PSO to optimize dropout parameters iteratively.
  3. Define an uncertainty-aware loss function that includes both prediction accuracy and uncertainty calibration.
  4. During training, after each epoch, the optimizer adjusts dropout rates based on the loss function, which includes penalties for poor uncertainty estimates.
  5. This iterative process enhances the model's ability to provide reliable uncertainty estimates without compromising prediction accuracy.

This approach ensures that the uncertainty estimates are both accurate and well-calibrated, improving the trustworthiness of deep learning models in safety-critical applications.

### Evaluation Plan

not provided

### Risks / Caveats

not provided

## moose_star_public_uncertainty_calibration_conformal_prediction_arxiv_005: MOOSE-Star hypothesis from Conditional generative models for efficient uncertainty quantification and model calibration

- Domain: uncertainty_calibration_conformal_prediction_arxiv
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: GenAI4UQ: A Software for Inverse Uncertainty Quantification Using Conditional Generative Models

### Problem Statement

What are promising research problems in uncertainty estimation, calibration, and conformal prediction suggested by recent literature?

### Motivation

Current methods for uncertainty estimation and calibration are computationally intensive and lack scalability, particularly for complex models. GenAI4UQ's approach using conditional generative models addresses these limitations by providing a more efficient and user-friendly solution, enabling rapid parameter estimation and prediction generation.

### Proposed Direction

The conditional generative model maps observations to parameter distributions and predictions, replacing traditional iterative methods. This mechanism allows for direct, learned mappings that enhance efficiency and scalability.

1. Develop a conditional generative model trained on existing data to map observations to parameter distributions and predictions.
  2. Integrate this model into a conformal prediction framework to provide uncertainty estimates.
  3. Validate the model's performance through testing on diverse datasets to ensure robustness and scalability.

### Evaluation Plan

not provided

### Risks / Caveats

not provided

## moose_star_public_uncertainty_calibration_conformal_prediction_arxiv_006: MOOSE-Star hypothesis from Adversarial Training and Conformal Prediction for Robust Uncertainty Quantification in Collaborative Object Detection

- Domain: uncertainty_calibration_conformal_prediction_arxiv
- Method: MOOSE_STAR_PUBLIC_MODEL
- Model: ZonglinY/MOOSE-Star-HC-R1D-7B
- Inference mode: HC_ONLY
- Inspiration papers: Uncertainty Quantification for Collaborative Object Detection Under Adversarial Attacks

### Problem Statement

What are promising research problems in uncertainty estimation, calibration, and conformal prediction suggested by recent literature?

### Motivation

Current methods struggle with adversarial attacks and providing reliable uncertainty estimates in collaborative object detection, particularly in dynamic environments like autonomous vehicles. The TUQCP framework addresses these gaps by integrating adversarial training to enhance robustness and conformal prediction for uncertainty quantification, offering a comprehensive solution to these challenges.

### Proposed Direction

The framework employs adversarial training to perturb shared information during collaboration, making models more resilient to adversarial attacks. It then uses conformal prediction to estimate and calibrate uncertainty, ensuring accurate and reliable outputs under various attack scenarios.

The implementation involves modifying the model architecture to incorporate adversarial training during collaboration, adding a perturbation step to shared information, and integrating conformal prediction modules for uncertainty estimation and calibration. This approach is tested on datasets such as V2X-Sim to evaluate its effectiveness in enhancing robustness and uncertainty quantification.

### Evaluation Plan

not provided

### Risks / Caveats

not provided
