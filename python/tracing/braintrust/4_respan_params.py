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
            project="Respan Params Example",
            project_id="respan-braintrust-params",
            api_key=os.getenv("BRAINTRUST_API_KEY", braintrust.logger.TEST_API_KEY),
            async_flush=False,
            set_current=False,
        )

        with logger.start_span(name="respan-params-span", type="task") as span:
            time.sleep(0.1)
            span.log(
                input=[{"role": "user", "content": "Testing Respan params"}],
                output="Success!",
                metadata={
                    "customer_identifier": "customer_12345",
                    "custom_tags": ["test", "braintrust", "respan"],
                    "environment": "production",
                    "session_id": "session_abc123"
                },
            )

        logger.flush()

    print("✓ Sent Respan Params Braintrust trace to Respan.")


if __name__ == "__main__":
    main()
