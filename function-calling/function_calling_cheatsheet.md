# Function Calling Code Cheat Sheet

A collection of every code example from the "Week 16 Day 2: Building a Reliable Tool-Calling Loop" notebook, with docstrings and notes, for reuse in your own projects.

## The Big Idea (read this first)

Function calling is a loop:

1. You send the user's message **and a list of tool schemas** to the model.
2. The model replies either with a final answer or with **tool call proposals** (name + JSON arguments + call ID).
3. **Your Python code** validates each proposal and runs the real function. The model never executes anything itself.
4. You send the result back as a `tool` message with the **same call ID**.
5. The model writes a final answer based on the observation.

Golden rule: **a tool call from the model is data, not permission.** Always validate before executing, and always set limits (max turns, max tool calls).

## Table of Contents

1. [Setup: connect to the model](#1-setup-connect-to-the-model)
2. [Plain request without tools](#2-plain-request-without-tools)
3. [Describing a tool with a JSON schema](#3-describing-a-tool-with-a-json-schema)
4. [Getting a tool proposal from the model](#4-getting-a-tool-proposal-from-the-model)
5. [Safe tools (calculator, catalog, ticket)](#5-safe-tools)
6. [Tool registry and validation tables](#6-tool-registry-and-validation-tables)
7. [Argument validation and the executor](#7-argument-validation-and-the-executor)
8. [Execute the model proposal and return the observation](#8-execute-the-model-proposal-and-return-the-observation)
9. [Scripted model and single-tool controller](#9-scripted-model-and-single-tool-controller-for-testing)
10. [Parallel execution of independent calls](#10-parallel-execution-of-independent-calls)
11. [Formatting tool messages](#11-formatting-tool-messages)
12. [Retry for transient read-only failures](#12-retry-for-transient-read-only-failures)
13. [Bounded loop (loop safety)](#13-bounded-loop-loop-safety)
14. [Audit logging with redaction](#14-audit-logging-with-redaction)
15. [Human approval for side effects](#15-human-approval-for-side-effects)
16. [Full live OpenRouter controller](#16-full-live-openrouter-controller)
17. [Grounded final answer and offline controller](#17-grounded-final-answer-and-offline-controller)
18. [Error taxonomy quick reference](#18-error-taxonomy-quick-reference)
19. [Common mistakes checklist](#19-common-mistakes-checklist)

---

## 1. Setup: connect to the model

Install the SDK, then create an OpenAI-compatible client. Set `LLM_URL` to the proxy **base path** (not the full `/chat/completions` URL; the SDK adds that itself).

```python
%pip install -q openai
```

```python
import os
from getpass import getpass
from openai import OpenAI

# Base URL of the OpenAI-compatible proxy (without /chat/completions).
base_url = os.getenv('LLM_URL').rstrip('/')

if not base_url:
    raise RuntimeError('Set LLM_URL to the proxy base path.')

# Read the API key from the environment, or ask for it with hidden input.
# Never print or commit the key.
api_key = os.getenv('OPENROUTER_API_KEY')
if not api_key:
    api_key = getpass('OpenRouter API key (input is hidden): ').strip()
if not api_key:
    raise RuntimeError('No OpenRouter API key was provided.')

OPENROUTER_MODEL = 'google/gemma-4-26b-a4b-it'

# max_retries=0: we control retries ourselves; timeout avoids hanging forever.
client = OpenAI(base_url=base_url, api_key=api_key, timeout=45.0, max_retries=0)
print('Client configured for', OPENROUTER_MODEL, 'through', base_url)
```

> Tip: `os.getenv('LLM_URL').rstrip('/')` crashes with an `AttributeError` if the variable is not set (because `getenv` returns `None`). A safer version is `os.getenv('LLM_URL', '').rstrip('/')`.

---

## 2. Plain request without tools

The simplest model call. No tools are passed, so the model just answers in text.

```python
preflight = client.chat.completions.create(
    model=OPENROUTER_MODEL,
    messages=[{'role': 'user', 'content': 'In one short sentence, explain what a tool-calling assistant does.'}],
    max_tokens=100,
)
print(preflight.choices[0].message.content)
```

---

## 3. Describing a tool with a JSON schema

A schema tells the model **what tools exist and what arguments they take**. It does not run anything.

```python
EARLY_TOOL_SCHEMAS = [{
    'type': 'function',
    'function': {
        'name': 'calculator',                       # must match the Python function name you register
        'description': 'Evaluate a restricted arithmetic expression for an exact calculation.',
        'parameters': {
            'type': 'object',
            'properties': {
                'expression': {
                    'type': 'string',
                    'description': 'Numbers, parentheses, and +, -, *, / only.',
                }
            },
            'required': ['expression'],             # arguments the model must provide
            'additionalProperties': False,          # no extra arguments allowed
        },
    },
}]
```

Good descriptions matter: the model uses `description` fields to decide **when** to call the tool and **how** to fill the arguments.

---

## 4. Getting a tool proposal from the model

Pass `tools=` and `tool_choice=`. Then inspect `message.tool_calls`.

```python
early_question = 'How many hours are three sessions of 80 minutes? Use the calculator tool.'

early_response = client.chat.completions.create(
    model=OPENROUTER_MODEL,
    messages=[
        {'role': 'system', 'content': 'For exact arithmetic, use the supplied calculator tool. Do not calculate mentally.'},
        {'role': 'user', 'content': early_question},
    ],
    tools=EARLY_TOOL_SCHEMAS,
    tool_choice='auto',   # 'auto' = model decides, 'required' = must call a tool, 'none' = never call a tool
    max_tokens=150,
)

early_assistant = early_response.choices[0].message
print('Model text:', early_assistant.content)          # usually None when a tool is proposed

for proposed_call in early_assistant.tool_calls or []:
    print('Proposed call:', proposed_call.model_dump(exclude_none=True))
```

Example output:

```
Proposed call: {'id': 'chatcmpl-tool-92bf...', 'function': {'arguments': '{"expression": "3 * 80 / 60"}', 'name': 'calculator'}, 'type': 'function', 'index': 0}
```

Note that `arguments` is a **JSON string**, not a dict. You must parse it.

---

## 5. Safe tools

### 5.1 Calculator (without `eval`)

Never use Python's `eval()` on model output: it can run arbitrary code. This calculator parses the expression into an AST and only allows numbers and `+ - * /`.

```python
import ast
import json
import math
import operator
import time

_BINARY_OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub,
                     ast.Mult: operator.mul, ast.Div: operator.truediv}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_arithmetic(node):
    """Recursively evaluate a whitelisted arithmetic AST node.

    Allowed: finite int/float constants, unary + and -, binary + - * /.
    Anything else (names, calls, attributes, etc.) raises ValueError.
    """
    if isinstance(node, ast.Expression):
        return _eval_arithmetic(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        if not math.isfinite(float(node.value)):
            raise ValueError('numbers must be finite')
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_eval_arithmetic(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        try:
            value = _BINARY_OPERATORS[type(node.op)](_eval_arithmetic(node.left), _eval_arithmetic(node.right))
        except ZeroDivisionError as exc:
            raise ValueError('division by zero is not allowed') from exc
        if not math.isfinite(float(value)):
            raise ValueError('result is not finite')
        return value
    raise ValueError('only numbers, parentheses, +, -, *, and / are allowed')


def calculator(expression):
    """Safely evaluate a basic arithmetic expression.

    Args:
        expression (str): e.g. "3*80/60". Max 80 characters, max 30 AST nodes.

    Returns:
        int | float: the numeric result.

    Raises:
        ValueError: empty/too long/too complex/invalid syntax/disallowed operation.
    """
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError('expression must be a non-empty string')
    expression = expression.strip()
    if len(expression) > 80:
        raise ValueError('expression is too long')
    try:
        tree = ast.parse(expression, mode='eval')
    except SyntaxError as exc:
        raise ValueError('invalid arithmetic syntax') from exc
    if sum(1 for _ in ast.walk(tree)) > 30:
        raise ValueError('expression is too complex')
    return _eval_arithmetic(tree)
```

### 5.2 Course catalog (read-only lookup)

```python
def course_catalog(topic):
    """Look up which course week covers a topic (read-only).

    Args:
        topic (str): e.g. "semantic search" (case-insensitive).

    Returns:
        str: a week label such as "Week 14", or "No matching topic".
             "No matching topic" is a normal result (an observation), not an exception.
    """
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError('topic must be non-empty')
    catalog = {'semantic search': 'Week 14', 'prompting': 'Week 15', 'function calling': 'Week 16',
               'rag': 'Week 17', 'hybrid search': 'Week 18'}
    return catalog.get(topic.strip().lower(), 'No matching topic')
```

### 5.3 Support ticket (side-effect tool)

This tool **changes state**, so it needs human approval (see sections 7 and 15).

```python
TICKET_DB = []  # in-memory fake database for the classroom


def create_support_ticket(topic, priority):
    """Create a support ticket in the in-memory store (state-changing!).

    Args:
        topic (str): short description of the problem.
        priority (str): one of 'low', 'normal', 'high'.

    Returns:
        dict: {'ticket_id': 'T-001', 'topic': ..., 'priority': ...}

    Raises:
        ValueError: empty topic or invalid priority.
    """
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError('topic must be non-empty')
    if priority not in {'low', 'normal', 'high'}:
        raise ValueError('priority must be low, normal, or high')
    ticket = {'ticket_id': f'T-{len(TICKET_DB) + 1:03d}', 'topic': topic.strip(), 'priority': priority}
    TICKET_DB.append(ticket)
    return ticket
```

---

## 6. Tool registry and validation tables

Central tables that the executor uses. Adding a new tool means adding it to every table.

```python
TOOLS = {                      # name -> Python function (the allow-list)
    'calculator': calculator,
    'course_catalog': course_catalog,
    'create_support_ticket': create_support_ticket,
}
EXPECTED = {                   # name -> exact set of argument names
    'calculator': {'expression'},
    'course_catalog': {'topic'},
    'create_support_ticket': {'topic', 'priority'},
}
ARGUMENT_TYPES = {             # name -> argument types
    'calculator': {'expression': str},
    'course_catalog': {'topic': str},
    'create_support_ticket': {'topic': str, 'priority': str},
}
READ_ONLY = {'calculator', 'course_catalog'}   # safe to auto-run and parallelize
APPROVAL_REQUIRED = {'create_support_ticket'}  # needs a human "yes"
IDEMPOTENCY_STORE = {}                         # call_id -> earlier result (prevents duplicates)
```

---

## 7. Argument validation and the executor

The executor is your **security boundary**. It always returns a dict with the same shape, so the rest of your code never has to guess.

```python
def _decode_arguments(raw):
    """Turn model arguments into a dict.

    Accepts a dict or a JSON string. Raises ValueError on malformed JSON and
    TypeError if the result is not a JSON object.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError('malformed JSON arguments') from exc
        if isinstance(value, dict):
            return value
    raise TypeError('arguments must be an object or JSON object string')


def _validate_arguments(name, raw):
    """Validate argument names, types, and business rules for tool `name`.

    Returns:
        dict: the validated arguments.

    Raises:
        ValueError / TypeError: on any violation. Nothing is executed.
    """
    args = _decode_arguments(raw)
    if set(args) != EXPECTED[name]:                 # no missing and no extra arguments
        raise ValueError('invalid argument set')
    for key, expected_type in ARGUMENT_TYPES[name].items():
        # bool is a subclass of int in Python, so reject it explicitly
        if not isinstance(args[key], expected_type) or isinstance(args[key], bool):
            raise TypeError(f'{key} must be a {expected_type.__name__}')
    # Validate ticket rules BEFORE asking a person to approve it.
    if name == 'create_support_ticket':
        if not args['topic'].strip():
            raise ValueError('topic must be non-empty')
        if args['priority'] not in {'low', 'normal', 'high'}:
            raise ValueError('priority must be low, normal, or high')
    return args


def _result(call_id, name, status, content, error_type=None):
    """Build the standard result dict used everywhere.

    Keys: call_id, tool, status, content (always a string), and optionally error_type.
    """
    output = {'call_id': call_id, 'tool': name, 'status': status, 'content': str(content)}
    if error_type:
        output['error_type'] = error_type
    return output


def execute_call(call, approved=False):
    """Validate and execute ONE tool call safely.

    Args:
        call (dict): {'id': str, 'name': str, 'arguments': dict | JSON str}
        approved (bool): True only if a HUMAN approved this call.

    Returns:
        dict with status:
            'ok'             -> tool ran successfully
            'error'          -> see error_type: parse_error, unknown_tool, validation_error,
                                business_error, execution_error
            'needs_approval' -> side-effect tool called without approval (nothing executed)
            'already_done'   -> same call ID already executed (idempotent replay)
    """
    if not isinstance(call, dict):
        return _result(None, 'unknown', 'error', 'call must be an object', 'parse_error')
    call_id = call.get('id')
    name = call.get('name', 'unknown')
    if not call_id:
        return _result(None, name, 'error', 'missing call ID', 'parse_error')
    if name not in TOOLS:
        return _result(call_id, name, 'error', 'unknown tool', 'unknown_tool')
    try:
        args = _validate_arguments(name, call.get('arguments'))
    except (KeyError, TypeError, ValueError) as exc:
        return _result(call_id, name, 'error', str(exc), 'validation_error')
    if name in APPROVAL_REQUIRED and call_id in IDEMPOTENCY_STORE:
        return _result(call_id, name, 'already_done', IDEMPOTENCY_STORE[call_id], 'idempotent_replay')
    if name in APPROVAL_REQUIRED and not approved:
        return _result(call_id, name, 'needs_approval', 'explicit approval is required', 'policy_error')
    try:
        value = TOOLS[name](**args)
        if name in APPROVAL_REQUIRED:
            IDEMPOTENCY_STORE[call_id] = value
        return _result(call_id, name, 'ok', value)
    except (ValueError, ZeroDivisionError) as exc:
        return _result(call_id, name, 'error', str(exc), 'business_error')
    except Exception:
        # Do not leak internal exception details to the model.
        return _result(call_id, name, 'error', 'tool execution failed', 'execution_error')
```

Quick test:

```python
print(execute_call({'id': 'c1', 'name': 'calculator', 'arguments': {'expression': '2.5*4'}}))
# {'call_id': 'c1', 'tool': 'calculator', 'status': 'ok', 'content': '10.0'}
```

Edge cases to try yourself:

```python
execute_call({'id': 'x1', 'name': 'hack_server', 'arguments': {}})                                   # unknown_tool
execute_call({'id': 'x2', 'name': 'calculator', 'arguments': {}})                                      # validation_error (missing arg)
execute_call({'id': 'x3', 'name': 'calculator', 'arguments': {'expression': 5}})                       # validation_error (wrong type)
execute_call({'id': 'x4', 'name': 'calculator', 'arguments': {'expression': '__import__("os")'}})     # business_error (unsafe)
execute_call({'id': 'x5', 'name': 'calculator', 'arguments': '{bad json'})                             # validation_error (malformed JSON)
execute_call({'id': 'x6', 'name': 'create_support_ticket',
              'arguments': {'topic': 'help', 'priority': 'high'}})                                     # needs_approval
```

---

## 8. Execute the model proposal and return the observation

This is the complete one-round-trip flow: model proposes → you validate/execute → you send the observation back → model answers.

```python
if not early_assistant.tool_calls:
    raise RuntimeError('The model did not return the required calculator call.')

# 1. Convert the API object into the executor's small internal format.
model_call = early_assistant.tool_calls[0]
internal_call = {
    'id': model_call.id,
    'name': model_call.function.name,
    'arguments': model_call.function.arguments,   # JSON string, decoded inside the executor
}

# 2. Validate and execute.
early_result = execute_call(internal_call)
print('Validated tool result:', early_result)

# 3. Build the follow-up conversation:
#    system -> user -> assistant (with tool_calls) -> tool (result with SAME call id)
followup_messages = [
    {'role': 'system', 'content': 'Answer using the supplied tool observation. Do not invent or change its result.'},
    {'role': 'user', 'content': early_question},
    early_assistant.model_dump(exclude_none=True),        # the assistant message that contained the tool call
    {
        'role': 'tool',
        'tool_call_id': model_call.id,                    # must match the proposal's ID
        'content': json.dumps({'status': early_result['status'], 'content': early_result['content']},
                              ensure_ascii=False),
    },
]

# 4. Ask the model for the final user-facing answer (tool_choice='none' = no more tool calls).
final_turn = client.chat.completions.create(
    model=OPENROUTER_MODEL,
    messages=followup_messages,
    tool_choice='none',
    max_tokens=120,
)
print('Model final answer:', final_turn.choices[0].message.content)
```

> Important: the assistant message containing `tool_calls` **must** be in the history before the `tool` message. Otherwise the API will reject the request.

---

## 9. Scripted model and single-tool controller (for testing)

A fake model that returns pre-written responses. Useful for testing your controller without spending API credits.

```python
scripted_responses = [
    {'tool_calls': [{'id': 'c1', 'name': 'calculator', 'arguments': {'expression': '3*80/60'}}]},
    {'final': 'Three 80-minute sessions equal 4 hours.'},
]


def scripted_model(messages, turn):
    """Fake model: returns the scripted response for this turn, or a safe fallback."""
    return scripted_responses[turn] if turn < len(scripted_responses) else {'final': 'No safe response.'}


def run_once(user_message, max_turns=3, max_tool_calls=4, approved_ids=None):
    """Run a bounded tool loop using the scripted model.

    Args:
        user_message (str): the user's question.
        max_turns (int): maximum model turns before stopping.
        max_tool_calls (int): maximum total tool calls.
        approved_ids (set[str] | None): call IDs a human has approved.

    Returns:
        list[dict]: the full message history, ending with a final assistant message.
    """
    messages = [{'role': 'user', 'content': user_message}]
    approved_ids = set(approved_ids or set())
    seen_ids = set()
    tool_count = 0
    for turn in range(max_turns):
        response = scripted_model(messages, turn)
        if not isinstance(response, dict):
            messages.append({'role': 'assistant', 'content': 'I could not parse the model response safely.'})
            return messages
        if isinstance(response.get('final'), str) and response['final'].strip():
            messages.append({'role': 'assistant', 'content': response['final']})
            return messages
        calls = response.get('tool_calls')
        if not isinstance(calls, list) or not calls:
            messages.append({'role': 'assistant', 'content': 'I could not continue safely.'})
            return messages
        messages.append({'role': 'assistant', 'tool_calls': calls})
        for call in calls:
            if tool_count >= max_tool_calls:
                messages.append({'role': 'assistant', 'content': 'Stopped at the maximum number of tool calls.'})
                return messages
            call_id = call.get('id') if isinstance(call, dict) else None
            if call_id in seen_ids:
                result = _result(call_id, call.get('name', 'unknown'), 'error', 'duplicate call ID', 'duplicate_call')
            else:
                if call_id:
                    seen_ids.add(call_id)
                result = execute_call(call, approved=call_id in approved_ids)
            tool_count += 1
            messages.append({
                'role': 'tool',
                'tool_call_id': result['call_id'],
                'name': result['tool'],
                'status': result['status'],
                'content': result['content'],
                **({'error_type': result['error_type']} if 'error_type' in result else {}),
            })
    messages.append({'role': 'assistant', 'content': 'Stopped at the maximum number of turns.'})
    return messages


for item in run_once('How long are three sessions?'):
    print(item)
```

---

## 10. Parallel execution of independent calls

Independent **read-only** calls can run at the same time. Dependent calls (e.g. look up an account, *then* refund) must wait for the first result.

```python
from concurrent.futures import ThreadPoolExecutor


def execute_independent_calls(calls, max_tool_calls=4, max_workers=4):
    """Run a batch of independent, read-only tool calls in parallel.

    Args:
        calls (list[dict]): tool calls in the internal format.
        max_tool_calls (int): batch-size budget.
        max_workers (int): number of threads.

    Returns:
        list[dict]: result dicts in the same order as `calls`.

    Raises:
        ValueError: budget exceeded, non-read-only tool in the batch, or duplicate call IDs.
    """
    calls = list(calls)

    if len(calls) > max_tool_calls:
        raise ValueError("Tool-call budget exceeded.")
    if not calls:
        return []
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1.")

    # Only parallelize tools explicitly marked as read-only.
    if any(not isinstance(call, dict) or call.get("name") not in READ_ONLY for call in calls):
        raise ValueError("Parallel batches may contain read-only tools only.")

    call_ids = [call.get("id") for call in calls]
    if len(call_ids) != len(set(call_ids)):
        raise ValueError("Duplicate call IDs in the batch.")

    with ThreadPoolExecutor(max_workers=min(max_workers, len(calls))) as pool:
        # execute_call still validates each tool name and its arguments.
        return list(pool.map(execute_call, calls))


multi_call_response = {'tool_calls': [
    {'id': 'a', 'name': 'course_catalog', 'arguments': {'topic': 'semantic search'}},
    {'id': 'b', 'name': 'calculator', 'arguments': {'expression': '3*80/60'}},
]}
results = execute_independent_calls(multi_call_response['tool_calls'])
for result in results:
    print(result)
```

---

## 11. Formatting tool messages

Converts an executor result into a message for the conversation history. The `tool_call_id` links the result to the original request.

```python
def tool_message(result):
    """Convert an executor result dict into a 'tool' role message.

    The tool_call_id MUST equal the ID of the model's original call, otherwise
    the model may attach the result to the wrong action.
    """
    message = {
        'role': 'tool',
        'tool_call_id': result['call_id'],
        'name': result['tool'],
        'status': result['status'],
        'content': result['content'],
    }
    if 'error_type' in result:
        message['error_type'] = result['error_type']
    return message


for result in results:
    print(tool_message(result))
```

> Note: when sending messages to a real OpenAI-compatible API, the safest tool message has only `role`, `tool_call_id`, and `content` (a string). The live controller in section 16 packs `status` and `error_type` into a JSON string inside `content`.

---

## 12. Retry for transient read-only failures

Retry only temporary failures, and only for **read-only** tools. Never auto-retry validation, policy, or side-effect errors.

```python
def retry_read_only(call, attempts=2, executor=execute_call):
    """Retry a read-only call only when the error is 'transient_error'.

    Args:
        call (dict): the tool call.
        attempts (int): maximum attempts (including the first).
        executor (callable): function that runs the call (replaceable for tests).

    Returns:
        dict: the last result.
    """
    for attempt in range(1, attempts + 1):
        result = executor(call)
        print('attempt', attempt, result)
        if result['status'] != 'error' or result.get('error_type') != 'transient_error':
            return result
    return result


# A fake executor that fails once, then works.
flaky_state = {'remaining': 1}


def flaky_executor(call):
    if flaky_state['remaining']:
        flaky_state['remaining'] -= 1
        return _result(call.get('id'), call.get('name'), 'error', 'temporary catalog outage', 'transient_error')
    return execute_call(call)


retry_read_only({'id': 'r1', 'name': 'course_catalog', 'arguments': {'topic': 'semantic search'}},
                executor=flaky_executor)
```

> In real projects add a short **backoff** (e.g. `time.sleep(0.5 * attempt)`) between attempts.

---

## 13. Bounded loop (loop safety)

Always limit turns and tool calls, and detect duplicate call IDs. Raising the limit is **not** a fix for a looping model.

```python
def bounded_loop(responses, max_turns=3, max_tool_calls=4):
    """Simulate a tool loop over a list of model responses and return a trace.

    Stops on: final answer, turn limit, tool-call limit, duplicate call ID,
    malformed response, or a response with neither text nor tool calls.

    Returns:
        list[tuple]: events like ('model', response), ('tool', result), ('stop', reason).
    """
    trace = []
    seen_ids = set()
    tool_count = 0
    for turn, response in enumerate(responses):
        if turn >= max_turns:
            trace.append(('stop', 'turn limit'))
            break
        if not isinstance(response, dict):
            trace.append(('stop', 'malformed model response'))
            break
        trace.append(('model', response))
        if isinstance(response.get('final'), str) and response['final'].strip():
            break
        calls = response.get('tool_calls')
        if not isinstance(calls, list) or not calls:
            trace.append(('stop', 'no final text or tool calls'))
            break
        for call in calls:
            if tool_count >= max_tool_calls:
                trace.append(('stop', 'tool-call limit'))
                return trace
            call_id = call.get('id') if isinstance(call, dict) else None
            if call_id in seen_ids:
                trace.append(('stop', 'duplicate call ID'))
                return trace
            if call_id:
                seen_ids.add(call_id)
            trace.append(('tool', execute_call(call)))
            tool_count += 1
    return trace


looping = [{'tool_calls': [{'id': str(i), 'name': 'course_catalog', 'arguments': {'topic': 'prompting'}}]}
           for i in range(5)]
for event in bounded_loop(looping, max_turns=3, max_tool_calls=4):
    print(event)
```

---

## 14. Audit logging with redaction

Log what happened without leaking secrets.

```python
def redact_preview(content, limit=60):
    """Return a short, redacted preview of tool output for logs.

    Replaces obvious secret words and truncates to `limit` characters.
    (This is a simple classroom version; production redaction needs
    regexes/allow-lists for emails, tokens, card numbers, etc.)
    """
    text = str(content).replace('api_key', '[REDACTED]').replace('password', '[REDACTED]')
    return text[:limit]


def audit_event(result, request_id='req-001', turn=0, latency_ms=0, approval='not_required'):
    """Build a structured, redacted audit record for one tool call.

    Args:
        result (dict): result from execute_call.
        request_id (str): ID shared by the whole user request.
        turn (int): model turn number.
        latency_ms (float): execution time.
        approval (str): 'not_required', 'approved', 'rejected', 'pending'.

    Returns:
        dict: safe-to-log event.
    """
    return {
        'request_id': request_id,
        'turn': turn,
        'call_id': result['call_id'],
        'tool': result['tool'],
        'status': result['status'],
        'error_type': result.get('error_type'),
        'approval': approval,
        'latency_ms': latency_ms,
        'content_preview': redact_preview(result['content']),
    }


print(audit_event(execute_call({'id': 'log1', 'name': 'calculator', 'arguments': {'expression': '10/2'}})))
```

Never log: API keys, passwords, full payment data, sensitive documents.

---

## 15. Human approval for side effects

The **human** approves, never the model. The prompt shows the exact validated arguments.

```python
def ask_for_ticket_approval(call):
    """Ask a human to approve a ticket creation.

    Returns:
        'approved' | 'rejected' | 'pending' | 'invalid'
        Approval is never inferred from model text.
    """
    try:
        args = _validate_arguments(call['name'], call['arguments'])
    except (KeyError, TypeError, ValueError):
        return 'invalid'  # execute_call will return the validation error without mutation

    print('Ticket proposed by the model:')
    print('  Topic:', args['topic'])
    print('  Priority:', args['priority'])
    try:
        answer = input("Type APPROVE to create this in-memory ticket, REJECT to decline, or press Enter to leave it pending: ")
    except EOFError:
        return 'pending'
    answer = answer.strip().upper()
    if answer == 'APPROVE':
        return 'approved'
    if answer == 'REJECT':
        return 'rejected'
    return 'pending'
```

Example confirmation message for a refund (state target, amount, reason, and irreversibility):

> You are about to refund **$42.50** to **customer account ending 3814** for **transaction TX-7821**, because the customer was charged twice. **Once submitted, this refund cannot be canceled.** To proceed, type `REFUND TX-7821 $42.50`.

If a request times out, retry with the **same idempotency key**, so the service doesn't perform the action twice.

---

## 16. Full live OpenRouter controller

### 16.1 Tool schemas for all three tools

```python
OPENROUTER_TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name': 'calculator',
            'description': 'Evaluate a restricted arithmetic expression for an exact calculation.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'expression': {'type': 'string', 'description': 'Numbers, parentheses, and +, -, *, / only.'}
                },
                'required': ['expression'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'course_catalog',
            'description': 'Find which course week covers a topic. Use the official course catalog rather than guessing.',
            'parameters': {
                'type': 'object',
                'properties': {'topic': {'type': 'string', 'description': 'The course topic to look up.'}},
                'required': ['topic'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'create_support_ticket',
            'description': 'Prepare a course-support ticket. This changes state and requires explicit human approval.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'topic': {'type': 'string', 'description': 'Short description of the support request.'},
                    'priority': {'type': 'string', 'enum': ['low', 'normal', 'high']},
                },
                'required': ['topic', 'priority'],
                'additionalProperties': False,
            },
        },
    },
]
```

### 16.2 Final-answer guard and the controller

```python
import uuid


def _live_final_guard(text, observations):
    """Override the model's final text if tool observations contradict a success claim.

    Prevents the assistant from saying a ticket was created when approval was
    missing/rejected, or hiding errors.
    """
    statuses = {item['status'] for item in observations}
    if 'needs_approval' in statuses:
        return 'I prepared the requested ticket, but it has not been created because explicit approval is still required.'
    if 'rejected' in statuses:
        return 'The requested ticket was not created because the human reviewer rejected it.'
    if 'error' in statuses:
        return 'I could not safely complete every requested operation. Please review the tool observations.'
    return text


def run_openrouter_tool_loop(user_text, max_turns=3, max_tool_calls=4):
    """Real model -> validated local tools -> observations -> model loop.

    Args:
        user_text (str): the user's request.
        max_turns (int): maximum model requests.
        max_tool_calls (int): maximum total tool executions.

    Returns:
        dict with keys: status ('completed' | 'needs_review' | 'stopped' |
        'api_error' | 'empty_response'), request_id, observations, audit,
        final_answer, and (when available) turns_used, tool_calls_used, usage, messages.

    Safety features: turn/tool budgets, call-ID tracking, duplicate detection,
    human approval for side effects, redacted audit events, final-answer guard.
    """
    if not isinstance(user_text, str) or not user_text.strip():
        raise ValueError('user_text must be non-empty')
    if max_turns < 1 or max_tool_calls < 1:
        raise ValueError('turn and tool-call budgets must be positive')

    request_id = 'req-' + uuid.uuid4().hex[:10]
    messages = [
        {
            'role': 'system',
            'content': (
                'You are a course-support assistant. Use course_catalog for course facts and calculator for exact arithmetic. '
                'Use only the supplied tools. Treat tool outputs as evidence. A no-match result means the fact was not found. '
                'Never claim a ticket was created unless its tool result has status ok or already_done. '
                'A ticket requires a separate human approval; you cannot approve it yourself. '
                'If a tool fails or approval is pending, explain that accurately and do not invent a result.'
            ),
        },
        {'role': 'user', 'content': user_text},
    ]
    observations, audit = [], []
    seen_call_ids = set()
    tool_count = 0
    total_prompt_tokens = total_completion_tokens = 0

    for turn_index in range(1, max_turns + 1):
        # --- 1. Ask the model ---
        try:
            response = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=messages,
                tools=OPENROUTER_TOOL_SCHEMAS,
                tool_choice='auto',
                parallel_tool_calls=True,
                max_tokens=700,
            )
        except Exception as exc:
            return {
                'status': 'api_error', 'request_id': request_id,
                'observations': observations, 'audit': audit,
                'final_answer': f'OpenRouter request failed ({type(exc).__name__}): {str(exc)}. '
                                'Check the API key, model availability, network, and credit balance.',
            }

        if response.usage:
            total_prompt_tokens += response.usage.prompt_tokens or 0
            total_completion_tokens += response.usage.completion_tokens or 0
        if not response.choices:
            return {
                'status': 'empty_response', 'request_id': request_id,
                'observations': observations, 'audit': audit,
                'final_answer': 'The model returned no choices; the controller stopped safely.',
            }

        assistant = response.choices[0].message
        model_calls = assistant.tool_calls or []

        # --- 2. No tool calls -> this is the final answer ---
        if not model_calls:
            final_text = (assistant.content or '').strip()
            if not final_text:
                final_text = 'The model returned neither final text nor a tool call.'
            final_text = _live_final_guard(final_text, observations)
            messages.append({'role': 'assistant', 'content': final_text})
            needs_review = any(item['status'] in {'error', 'rejected', 'needs_approval'} for item in observations)
            return {
                'status': 'needs_review' if needs_review else 'completed',
                'request_id': request_id,
                'turns_used': turn_index, 'tool_calls_used': tool_count,
                'observations': observations, 'audit': audit,
                'usage': {'prompt_tokens': total_prompt_tokens, 'completion_tokens': total_completion_tokens},
                'final_answer': final_text,
                'messages': messages,
            }

        # --- 3. Enforce the tool-call budget BEFORE executing anything ---
        if tool_count + len(model_calls) > max_tool_calls:
            return {
                'status': 'stopped', 'request_id': request_id,
                'turns_used': turn_index, 'tool_calls_used': tool_count,
                'observations': observations, 'audit': audit,
                'usage': {'prompt_tokens': total_prompt_tokens, 'completion_tokens': total_completion_tokens},
                'final_answer': f'The request exceeded the limit of {max_tool_calls} tool calls; the new batch was not executed.',
            }

        # --- 4. Keep the assistant's tool-call message in the history ---
        messages.append({
            'role': 'assistant',
            'content': assistant.content,
            'tool_calls': [call.model_dump(exclude_none=True) for call in model_calls],
        })

        # --- 5. Validate + execute each call, append observations ---
        for model_call in model_calls:
            call_id = model_call.id
            tool_name = model_call.function.name
            call = {'id': call_id, 'name': tool_name, 'arguments': model_call.function.arguments}
            if not call_id:
                return {
                    'status': 'stopped', 'request_id': request_id,
                    'observations': observations, 'audit': audit,
                    'final_answer': 'A model tool call had no call ID; execution stopped safely.',
                }

            started = time.perf_counter()
            approval_state = 'not_required'
            if call_id in seen_call_ids:
                result = _result(call_id, tool_name, 'error', 'duplicate call ID; not executed twice', 'duplicate_call')
            else:
                seen_call_ids.add(call_id)
                if tool_name in APPROVAL_REQUIRED and call_id not in IDEMPOTENCY_STORE:
                    decision = ask_for_ticket_approval(call)
                    approval_state = decision
                    if decision == 'rejected':
                        result = _result(call_id, tool_name, 'rejected', 'human reviewer declined the ticket', 'policy_error')
                    else:
                        result = execute_call(call, approved=(decision == 'approved'))
                else:
                    result = execute_call(call, approved=False)

            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            observations.append(result)
            audit.append(audit_event(result, request_id=request_id, turn=turn_index,
                                     latency_ms=elapsed_ms, approval=approval_state))
            tool_count += 1
            tool_payload = {
                'status': result['status'],
                'content': result['content'],
                'error_type': result.get('error_type'),
            }
            messages.append({
                'role': 'tool',
                'tool_call_id': call_id,
                'content': json.dumps(tool_payload, ensure_ascii=False, default=str),
            })

    # Ran out of turns without a final answer.
    return {
        'status': 'stopped', 'request_id': request_id,
        'turns_used': max_turns, 'tool_calls_used': tool_count,
        'observations': observations, 'audit': audit,
        'usage': {'prompt_tokens': total_prompt_tokens, 'completion_tokens': total_completion_tokens},
        'final_answer': f'The controller reached its {max_turns}-turn limit before receiving final text.',
    }
```

### 16.3 Using it

```python
live_run = run_openrouter_tool_loop(
    'Which week covers semantic search, and how many hours are three sessions of 80 minutes?',
    max_turns=3,
    max_tool_calls=4,
)

print('STATUS:', live_run['status'])
print('OBSERVATIONS:')
for observation in live_run['observations']:
    print(observation)
print('FINAL ANSWER:', live_run['final_answer'])
print('TOKEN USAGE:', live_run.get('usage'))
print('AUDIT EVENTS:')
for event in live_run['audit']:
    print(event)
```

---

## 17. Grounded final answer and offline controller

A deterministic controller (no model) that is handy for unit tests of your executor and policies.

```python
def grounded_final_answer(question, observations):
    """Build a final answer ONLY from tool observations (no invented facts)."""
    if any(item['status'] == 'needs_approval' for item in observations):
        return 'I prepared the requested action, but I need explicit confirmation before changing anything.'
    if any(item['status'] == 'error' for item in observations):
        return 'I could not safely complete every requested operation; rejected calls were not executed.'
    evidence = '; '.join(item['content'] for item in observations)
    return f'{question} Evidence from approved tools: {evidence}'


def course_controller(question, calls=None, approvals=None, max_turns=3, max_tool_calls=4):
    """Run a fixed list of tool calls through the executor and build a grounded answer.

    Args:
        question (str): user question.
        calls (list[dict] | None): tool calls; defaults to catalog + calculator.
        approvals (set[str] | None): call IDs that a human approved.

    Returns:
        dict with status ('completed' | 'needs_review' | 'stopped'),
        observations (tool messages), audit events, and final_answer.
    """
    calls = calls or [
        {'id': 'p1', 'name': 'course_catalog', 'arguments': {'topic': 'semantic search'}},
        {'id': 'p2', 'name': 'calculator', 'arguments': {'expression': '3*80/60'}},
    ]
    approvals = set(approvals or set())
    if len(calls) > max_tool_calls:
        return {'status': 'stopped', 'reason': 'tool-call limit', 'observations': [],
                'final_answer': 'The request exceeded the tool budget.'}
    observations = []
    audit = []
    seen = set()
    for call in calls:
        call_id = call.get('id') if isinstance(call, dict) else None
        if call_id in seen:
            result = _result(call_id, call.get('name', 'unknown'), 'error', 'duplicate call ID', 'duplicate_call')
        else:
            if call_id:
                seen.add(call_id)
            started = time.perf_counter()
            result = execute_call(call, approved=call_id in approvals)
            elapsed = round((time.perf_counter() - started) * 1000, 3)
            audit.append(audit_event(result, turn=0, latency_ms=elapsed,
                                     approval='approved' if call_id in approvals else 'not_required'))
        observations.append(result)
    status = 'completed' if all(item['status'] in {'ok', 'already_done'} for item in observations) else 'needs_review'
    return {
        'status': status,
        'question': question,
        'observations': [tool_message(item) for item in observations],
        'audit': audit,
        'final_answer': grounded_final_answer(question, observations),
    }
```

Tests (these use `assert`, so silence means success):

```python
happy = course_controller('Which week covers semantic search and how long are three sessions?')
assert happy['status'] == 'completed'
assert 'Week 14' in happy['final_answer'] and '4.0' in happy['final_answer']

no_match = course_controller('Find an unknown topic.',
    [{'id': 'n1', 'name': 'course_catalog', 'arguments': {'topic': 'quantum gardening'}}])
assert no_match['status'] == 'completed' and 'No matching topic' in no_match['final_answer']

blocked = course_controller('Open a ticket.',
    [{'id': 't1', 'name': 'create_support_ticket', 'arguments': {'topic': 'office hours', 'priority': 'normal'}}])
assert blocked['status'] == 'needs_review' and len(TICKET_DB) == 0

approved = course_controller('Open a ticket.',
    [{'id': 't1', 'name': 'create_support_ticket', 'arguments': {'topic': 'office hours', 'priority': 'normal'}}],
    approvals={'t1'})
replay = course_controller('Retry the same ticket.',
    [{'id': 't1', 'name': 'create_support_ticket', 'arguments': {'topic': 'office hours', 'priority': 'normal'}}],
    approvals={'t1'})
assert approved['observations'][0]['status'] == 'ok'
assert replay['observations'][0]['status'] == 'already_done'
assert len(TICKET_DB) == 1
```

---

## 18. Error taxonomy quick reference

| Category | Example | Safe default |
|---|---|---|
| Parse | malformed JSON, missing call ID | reject; optionally request one correction |
| Validation | missing field, wrong type, unknown tool | do not execute; explain the contract |
| Business | no catalog match, division by zero | report the observation; do not invent a result |
| Policy | side effect without approval | pause and request confirmation |
| Infrastructure | timeout, rate limit, database down | bounded retry with backoff (read-only/idempotent only) |
| Loop | repeated calls, budget exceeded | stop and return a safe fallback |

Retry rules of thumb:

| Situation | Retry? |
|---|---|
| Transient failure of a read-only tool | Yes, up to 2 attempts |
| Validation / parse error | No automatic retry; ask for one corrected proposal at most |
| "No match" result | No, it is a valid result, not a failure |
| Policy block (no approval) | No, wait for human approval |
| Refund / email / delete with uncertain outcome | Only with the **same** idempotency key |

---

## 19. Common mistakes checklist

- Using `eval()` on model-provided expressions.
- Executing a tool call without validating the name, argument set, and types.
- Forgetting to include the assistant's `tool_calls` message before the `tool` message.
- Using a `tool_call_id` that does not match the model's call ID.
- Treating `function.arguments` as a dict (it is a JSON string).
- Having no limit on turns or tool calls.
- Letting the model "approve" side effects; only a human can.
- Retrying side-effect actions with a new ID or key.
- Logging secrets, or trusting the model's final text when a tool failed.
- Calling a tool for every question; a direct answer is fine when no tool is needed.

**Mental model to remember:** the model suggests → the executor validates → tools observe or act → the controller limits, authorizes, logs, and recovers → the model communicates.
