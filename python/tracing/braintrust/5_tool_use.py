#!/usr/bin/env python3
import os
import json
from pathlib import Path

import braintrust
from braintrust import init_logger, wrap_openai
from dotenv import load_dotenv
from openai import OpenAI
from respan_exporter_braintrust import RespanBraintrustExporter

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)


def get_weather(location: str) -> str:
    """Mock weather tool."""
    return json.dumps({"location": location, "temperature": "72F", "condition": "Sunny"})


def main() -> None:
    api_key = os.getenv("RESPAN_API_KEY")
    if not api_key:
        raise RuntimeError("RESPAN_API_KEY not set")

    with RespanBraintrustExporter(api_key=api_key, raise_on_error=True):
        logger = init_logger(
            project="Respan Tool Use Example",
            project_id="respan-braintrust-tool-use",
            api_key=os.getenv("BRAINTRUST_API_KEY", braintrust.logger.TEST_API_KEY),
            async_flush=False,
            set_current=True,
        )
        
        client = wrap_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

        with logger.start_span(name="tool-use-workflow") as span:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get the current weather in a given location",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {
                                    "type": "string",
                                    "description": "The city and state, e.g. San Francisco, CA",
                                }
                            },
                            "required": ["location"],
                        },
                    },
                }
            ]

            messages = [{"role": "user", "content": "What's the weather like in San Francisco?"}]

            # Step 1: Call LLM with tool
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )

            response_message = response.choices[0].message
            messages.append(response_message)

            # Step 2: Handle tool call
            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    if tool_call.function.name == "get_weather":
                        args = json.loads(tool_call.function.arguments)
                        
                        with span.start_span(name="get_weather_tool", type="tool") as tool_span:
                            weather_info = get_weather(args.get("location"))
                            tool_span.log(input=args, output=weather_info)
                        
                        messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": "get_weather",
                                "content": weather_info,
                            }
                        )

                # Step 3: Get final response
                final_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                )
                print("Final Answer:", final_response.choices[0].message.content)

        logger.flush()

    print("✓ Sent Tool Use OpenAI trace from Braintrust to Respan.")


if __name__ == "__main__":
    main()
