# Add Hello World Endpoint to FastAPI Server

## Status
pending

## Task
Add a simple "Hello, World!" endpoint to the FastAPI server in `src/autofram/server.py`.

Requirements:
- Add a new GET endpoint at `/hello`
- The endpoint should return a plain text response containing "Hello, World!"
- Use `PlainTextResponse` for the response class (already imported)
- Follow the existing code style and patterns in the file
- Add a test for the new endpoint in `tests/test_server.py`

The test should:
- Use the FastAPI TestClient
- Verify the endpoint returns status code 200
- Verify the response content is "Hello, World!"
- Verify the content-type is "text/plain"

## Constraints
- Only modify `src/autofram/server.py` and `tests/test_server.py`
- Do not modify any other files
- Maintain all existing functionality
- Follow existing code style

## Result
