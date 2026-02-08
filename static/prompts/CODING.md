# Coding Standards

## Two-Pass Process

Every code generation goes through two passes. The first pass writes the code and gets it working. The second pass reviews and revises for reuse and clarity. Both passes are essential.

## Keep it Simple

Program close to the requirements. Solve the specific problem first.

## Guard Conditions

Use guard conditions liberally to exit logic flows early and reduce nesting. Test for bad cases before happy path.

## Granular Functions

Favor tight, granular functions over inlining and deep nesting.

## Shallow Call Chains

Use shallow call chains and pass returned artifacts from call to call.

## No Defaults, No Optionals

Do not provide default values for parameters. Avoid optional parameters. The signature should be the signature. Fail fast on missing values.

## Testing

Write unit tests in the tests/ directory for any testable code. Run with `uv run pytest`.
