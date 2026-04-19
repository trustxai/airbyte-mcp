# Rich Tool Docstrings

The tool docstring is the **only** context an LLM receives when
deciding which tool to call and how to call it. Shallow docstrings
like `"List items with pagination"` force the LLM to guess.

## Template: List Tool

```python
async def {service}_list_{resources}(params: ListInput) -> str:
    """List {resources} configured in {Service}.

    {Resources} represent {brief domain explanation — what they are,
    why they exist, how they relate to other concepts}. Each {resource}
    is linked to a {parent} and can be {relationship to other entities}.

    When to Use:
        - Discover which {resources} exist and get their UUIDs.
        - Find a {resource} by name to use its ID in other calls.
        - Audit {resources} across one or more {parents}.

    When NOT to Use:
        - If you already have a {resource} ID, use
          {service}_get_{resource} for full details.
        - To see {related activity}, use {service}_list_{related}
          instead.

    Returns:
        Paginated list of {resources}. Each entry includes:
        - name, {resource}Id (UUID), {type field}, {parent}Id,
          createdAt.

        Markdown format shows a heading per {resource} with bullet
        fields. JSON format returns the raw API response array.

    Pagination:
        Use limit (1–100, default 20) and offset (default 0).

    Examples:
        List all {resources} in a {parent}:
            params = { "{parent}_ids": ["uuid-..."] }
        List first 5 {resources}:
            params = { "limit": 5 }
        Include soft-deleted {resources}:
            params = { "include_deleted": true }
        Get raw JSON for scripting:
            params = { "response_format": "json" }
    """
```

## Template: Get Tool

```python
async def {service}_get_{resource}(params: GetInput) -> str:
    """Get full details of a single {resource} by its UUID.

    Returns the {resource} name, type (e.g. {example_types}),
    {parent}, creation date, and configuration. {Any masking note}.

    When to Use:
        - Inspect a specific {resource}'s configuration or type.
        - Verify a {resource} ID is valid.
        - Check when a {resource} was created or which {parent}
          owns it.

    When NOT to Use:
        - If you need to browse {resources}, use
          {service}_list_{resources}.
        - To see {related activity}, use {service}_list_{related}
          filtered by the relevant {link entity}.

    Returns:
        {Resource} details including: name, {resource}Id, {type},
        {parent}Id, createdAt, and configuration.

        Markdown format renders a heading with bullet-point fields.
        JSON format returns the full API response object.

    Examples:
        Get {resource} by ID:
            params = { "{resource}_id": "uuid-..." }
        Get raw JSON:
            params = { "{resource}_id": "uuid-...", "response_format": "json" }

    Error Handling:
        Returns a 404 message if the {resource} ID does not exist.
        Returns a 403 message if credentials lack access.
    """
```

## Template: Health Check Tool

```python
async def {service}_health_check() -> str:
    """Check whether the {Service} API is reachable and healthy.

    Sends a lightweight GET /health request to verify connectivity
    and authentication. Use this as the first call to confirm the
    {Service} instance is running before making other requests.

    When to Use:
        - Verify the {Service} instance is up and reachable.
        - Diagnose connection or authentication errors.
        - Confirm credentials are valid after initial setup.

    Returns:
        "OK – {Service} API is healthy." on success.
        On failure, returns a human-readable error with the root
        cause (e.g. connection refused, 401 unauthorized, timeout).

    Examples:
        Call with no parameters: {service}_health_check()

    Related Tools:
        After confirming health, use {service}_list_{first_resource}
        to discover available {first resources}.
    """
```

## Template: Filtered List Tool (e.g. Jobs)

For tools with many filter parameters, add a **Filters** section:

```python
    """List {resources} with rich filtering options.

    {Resources} represent {domain explanation}.

    When to Use:
        - {scenario 1}
        - {scenario 2}

    Filters:
        All filters are optional and combinable:
        - {parent}_id: restrict to one {parent entity}.
        - {type}: "{value_a}" or "{value_b}".
        - status: {list of valid statuses}.
        - created_at_start / created_at_end: ISO-8601 date range.
        - order_by: sort field, e.g. "createdAt|DESC".

    Returns:
        ...

    Examples:
        Recent failed {resources} for a {parent}:
            params = { "{parent}_id": "uuid-...", "status": "failed", "limit": 5 }
        All {type_a} {resources} in the last 7 days:
            params = { "{type}": "{value_a}", "created_at_start": "2024-06-01T00:00:00Z" }
    """
```

## Key Principles

1. **Domain context** — explain _what_ the resource is, not just
   _what the tool does_. The LLM doesn't know your API's domain
   model.
2. **When to Use / NOT to Use** — prevents the LLM from calling the
   wrong tool and having to backtrack.
3. **Concrete examples** — use realistic parameter objects, not
   abstract descriptions.
4. **Return shape** — list the fields so the LLM knows what to
   expect and can plan follow-up calls.
5. **Error guidance** — mention the common error codes so the LLM
   can self-diagnose instead of retrying blindly.
