# Respan Logging Examples (TypeScript)

This directory contains TypeScript examples for working with Respan's logging API, evaluators, and scoring functionality.

## Quick Links

- **Quickstart Guide**: https://docs.respan.ai/get-started/quickstart/logging
- **Create a Prompt**: https://docs.respan.ai/get-started/quickstart/create-a-prompt
- **Create Datasets**: https://docs.respan.ai/documentation/products/dataset
- **Evaluator Creation**: https://docs.respan.ai/api-endpoints/evaluate/evaluators/create
- **Log Scores Creation**: https://docs.respan.ai/api-endpoints/evaluate/log-scores/create

## Setup

1. **Install dependencies:**

```bash
cd example_workflows/demo_account_setup_TS
yarn install
```

2. **Configure environment variables:**

Copy the `env.template` file to `.env` and update it with your API credentials:

```bash
cp env.template .env
```

Then edit `.env` and set your API key:

```bash
RESPAN_API_KEY=your_respan_api_key_here
RESPAN_BASE_URL=https://api.respan.ai/api
```

You can also customize other settings in `.env` such as:
- Model names (DEFAULT_MODEL, DEFAULT_MODEL_MINI, DEFAULT_MODEL_CLAUDE)
- Evaluator settings (EVALUATOR_LLM_ENGINE, EVALUATOR_TEMPERATURE, EVALUATOR_MAX_TOKENS)
- Score ranges (DEFAULT_MIN_SCORE, DEFAULT_MAX_SCORE, DEFAULT_PASSING_SCORE)
- Prompt settings (PROMPT_TEMPERATURE, PROMPT_MAX_TOKENS)

## Usage

All scripts can be run using yarn:

```bash
cd example_workflows/demo_account_setup_TS
```

### 1. Basic Logging (`basic_logging.ts`)

This script demonstrates basic logging functionality with various examples:
- Simple log entry
- Log with custom identifier
- Log with span name
- Multi-turn conversation log

```bash
yarn basic-logging
```

### 2. Create Evaluator (`create_evaluator.ts`)

This script demonstrates how to create custom evaluators in Respan:
- LLM evaluator for response quality (numerical)
- Helpfulness evaluator (categorical)
- Factual accuracy evaluator (boolean)
- Overall satisfaction evaluator (1-5 scale)

```bash
yarn create-evaluator
```

### 3. Create Log Scores (`create_log_scores.ts`)

This script provides examples and documentation for creating scores on logs using evaluators. It includes:
- Single score creation
- Score with metadata
- Batch score creation
- Complete workflow examples

**Note:** This script primarily shows example code patterns. For actual execution, see `test_create_log_score.ts`.

```bash
yarn create-log-scores
```

### 4. Test Create Log Score (`test_create_log_score.ts`)

This script demonstrates the complete end-to-end workflow:
1. Creates a log entry
2. Creates an evaluator
3. Creates a score on the log using the evaluator

```bash
yarn test-create-log-score
```

### 5. Create Prompt (`create_prompt.ts`)

This script demonstrates how to create and manage prompts in Respan:
- Create a new prompt
- Create prompt versions with messages
- List all prompts
- Get a specific prompt
- List prompt versions
- Get a specific prompt version

Prompts are reusable templates for LLM conversations that can be versioned and deployed.

```bash
yarn create-prompt
```

### 6. Create Dataset (`create_dataset.ts`)

This script demonstrates how to create and manage datasets in Respan:
- Create an empty dataset
- Add dataset logs (input/output JSON)
- List dataset logs
- Bulk add logs using filters and time range
- Run evaluators on datasets
- List eval runs
- Update dataset metadata
- Delete logs from dataset
- Delete dataset

Datasets are curated collections of logs that you can evaluate, annotate, and use to power Experiments.

```bash
yarn create-dataset
```

After running any of these scripts, you can view the results on the Respan platform:
- Navigate to the **Logs** tab to see your created logs and their associated scores
- Navigate to the **Prompt Management** section to see your created prompts
- Navigate to the **Datasets** section to see your created datasets

## Additional Resources

- [Respan Documentation](https://docs.respan.ai)
- [API Reference](https://docs.respan.ai/api-endpoints)
- [Integration Guides](https://docs.respan.ai/get-started/quickstart)
