#!/usr/bin/env python3
import os
import time
from pathlib import Path

import braintrust
from dotenv import load_dotenv
from respan_exporter_braintrust import RespanBraintrustExporter

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)


def main() -> None:
    api_key = os.getenv("RESPAN_API_KEY")
    if not api_key:
        raise RuntimeError("RESPAN_API_KEY not set")

    exporter = RespanBraintrustExporter(api_key=api_key, raise_on_error=True)
    with exporter:
        logger = braintrust.init_logger(
            project="Respan Tracing Example",
            project_id="respan-braintrust-tracing",
            api_key=os.getenv("BRAINTRUST_API_KEY", braintrust.logger.TEST_API_KEY),
            async_flush=False,
            set_current=False,
        )

        with logger.start_span(name="workflow-parent", type="task") as root_span:
            with root_span.start_span(name="task-child-1", type="tool") as child_span_1:
                time.sleep(0.1)
                child_span_1.log(input="Task 1 input", output="Task 1 output")
                
            with root_span.start_span(name="task-child-2", type="chat") as child_span_2:
                time.sleep(0.1)
                child_span_2.log(
                    input=[{"role": "user", "content": "Task 2 input"}],
                    output="Task 2 output",
                    metrics={"prompt_tokens": 10, "completion_tokens": 20},
                    metadata={"model": "gpt-4o-mini"},
                )

        logger.flush()

    print("✓ Sent Tracing Braintrust trace to Respan.")


if __name__ == "__main__":
    main()
