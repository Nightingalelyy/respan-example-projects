#!/usr/bin/env python3
import os
from pathlib import Path

import braintrust
from braintrust import init_logger, wrap_openai
from dotenv import load_dotenv
from openai import OpenAI
from respan_exporter_braintrust import RespanBraintrustExporter

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)


def main() -> None:
    api_key = os.getenv("RESPAN_API_KEY")
    if not api_key:
        raise RuntimeError("RESPAN_API_KEY not set")

    with RespanBraintrustExporter(api_key=api_key, raise_on_error=True):
        logger = init_logger(
            project="Email Classifier",
            api_key=os.getenv("BRAINTRUST_API_KEY", braintrust.logger.TEST_API_KEY),
            async_flush=False,
            set_current=False,
        )
        
        # wrap_openai instruments the OpenAI client with braintrust
        client = wrap_openai(client=OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello from wrapped OpenAI in Braintrust"}],
        )

        logger.log(
            input={"prompt": "Hello from wrapped OpenAI in Braintrust"},
            output=response.choices[0].message.content,
        )

        logger.flush()

    print("✓ Sent wrapped OpenAI trace from Braintrust to Respan.")


if __name__ == "__main__":
    main()
