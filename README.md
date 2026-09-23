# Microsoft Agents SDK `ClientCitation` / `@id` Deserialization Issue

## Overview

Our project uses the Microsoft Agents SDK to communicate with Microsoft Copilot Studio agents when the user is signed in with their Microsoft account.

In this flow, our project is **not using Direct Line**. The portal obtains delegated Microsoft user credentials, and the backend uses those credentials with the Copilot Studio client to invoke the agent on behalf of that signed-in user.

The relevant SDK packages in the environment where the issue was observed are:

```text
microsoft-agents-copilotstudio-client==1.5.0
microsoft-agents-activity==1.5.0
pydantic==2.13.4
```

The Copilot Studio request itself succeeds. Conversations are created successfully and some responses are processed successfully. The failure occurs only on responses containing a citation with an `@id` field.

The resulting error is:

```text
entities.citation.0
Value error, "ClientCitation" object has no field "at_id"
```

This README explains the failure path and provides a small standalone reproduction that does not depend on our project, a Microsoft tenant, authentication, or a live Copilot Studio agent.

---

## High-level flow

The signed-in Copilot Studio path is approximately:

```text
Signed-in Microsoft user
        |
        | delegated access token
        v
microsoft-agents-copilotstudio-client
        |
        | Copilot Studio request
        v
Microsoft Copilot Studio agent
        |
        | SSE Activity response
        v
CopilotClient.post_request()
        |
        | Activity.model_validate_json(...)
        v
microsoft-agents-activity
        |
        | validates entities and citations
        v
ClientCitation
        |
        X
Pydantic error when @id is mapped to at_id
```

The important point is that this is **not an authentication failure**. The response has already been returned by Copilot Studio when the exception occurs.

---

# Failure path

## 1. Copilot Studio returns a citation containing `@id`

A failing Copilot Studio response contains a citation with the following shape:

```json
{
  "@type": "Claim",
  "@id": "turn16search0",
  "position": 1,
  "appearance": {
    "@type": "DigitalDocument",
    "name": "Example citation"
  }
}
```

The production evaluation logs show the same important field in the failing input:

```text
entities.citation.0
Value error, "ClientCitation" object has no field "at_id"
input_value={... '@id': 'turn16search0'}
```

The complete Microsoft response is larger than the example above. The JSON shown here is the minimal citation shape needed to reproduce the SDK problem.

---

## 2. `CopilotClient` passes the Activity into `microsoft-agents-activity`

The relevant class is:

```text
microsoft_agents.copilotstudio.client.copilot_client.CopilotClient
```

Package:

```text
microsoft-agents-copilotstudio-client==1.5.0
```

Inside `CopilotClient.post_request()`, the SDK reads the SSE response from Copilot Studio and extracts the raw Activity JSON:

```python
activity_data = line[5:].decode("utf-8").strip()
activity = Activity.model_validate_json(activity_data)
```

So the raw response is handed to the `Activity` model from `microsoft-agents-activity`.

The Copilot client does not sanitize the citation before validation.

---

## 3. `@id` is handled by `_SchemaMixin`

During Activity validation, known entities are converted into their concrete SDK models. The citation is therefore validated as a `ClientCitation`.

The relevant helper is:

```text
microsoft_agents.activity.entity._schema_mixin.validate_schema_model
```

Package:

```text
microsoft-agents-activity==1.5.0
```

The implementation is effectively:

```python
model = handler(data)

if "@type" in data:
    setattr(model, "at_type", data["@type"])

if "@context" in data:
    setattr(model, "at_context", data["@context"])

if "@id" in data:
    setattr(model, "at_id", data["@id"])
```

Therefore, when the incoming citation contains:

```json
"@id": "turn16search0"
```

`_SchemaMixin` attempts to do the equivalent of:

```python
client_citation.at_id = "turn16search0"
```

---

## 4. `ClientCitation` does not define `at_id`

The relevant model is:

```text
microsoft_agents.activity.entity.ai_entity.ClientCitation
```

In `microsoft-agents-activity==1.5.0`, it defines these fields:

```python
class ClientCitation(AgentsModel, _SchemaMixin):
    at_type: Literal["Claim"] = "Claim"
    position: int = 0
    appearance: ClientCitationAppearance = Field(
        default_factory=ClientCitationAppearance
    )
```

There is no:

```python
at_id: ...
```

So the sequence becomes:

```text
Copilot Studio response
        |
        | citation contains "@id"
        v
Activity.model_validate_json(...)
        |
        v
ClientCitation validation
        |
        v
_SchemaMixin sees "@id"
        |
        | setattr(model, "at_id", ...)
        v
ClientCitation has no at_id field
        |
        X
Pydantic rejects the assignment
```

The resulting exception is:

```text
Value error, "ClientCitation" object has no field "at_id"
```

---

# Why this looks like an SDK bug

The `_SchemaMixin` helper itself documents its purpose as:

```text
Custom validator to handle the aliases @type, @context, and @id
if defined in the destination type.
```

However, the implementation checks only whether the property is present in the **incoming payload**:

```python
if "@id" in data:
    setattr(model, "at_id", data["@id"])
```

It does **not** check whether the destination model actually defines `at_id` before attempting the assignment.

That distinction matters for `ClientCitation`:

```text
Incoming property    Destination property    ClientCitation defines it?
-----------------    --------------------    --------------------------
@type                at_type                 Yes
@context             at_context              No
@id                  at_id                   No
```

`@type` works because `ClientCitation` defines `at_type`.

`@id` fails because the response contains `@id`, causing the helper to assign `at_id`, but `ClientCitation` does not define that field.

`@context` would have the same structural problem if a `ClientCitation` payload containing `@context` reached this code path.

The mismatch is therefore between the helper's stated behavior—handle these properties **if defined in the destination type**—and its actual behavior, which attempts to assign them whenever they are present in the input.

---

# Standalone reproduction

Three files are included with this reproduction:

```text
requirements.txt
repro.py
repro_activity.py
```

The reproduction does not require:

- Our project
- Microsoft authentication
- a Microsoft tenant
- a Copilot Studio agent
- Direct Line
- network access to Copilot Studio

It only exercises the Microsoft SDK models with the same citation shape that causes the production failure.

## Setup

Create and activate a Python virtual environment if desired, then install the attached requirements using `pip`:

```bash
pip install -r requirements.txt
```

The important dependencies are:

```text
microsoft-agents-activity==1.5.0
pydantic==2.13.4
```

The production environment also uses:

```text
microsoft-agents-copilotstudio-client==1.5.0
```

but the Copilot Studio client is not required to reproduce the underlying `ClientCitation` failure.

---

## Reproduction 1: `ClientCitation` directly

Run:

```bash
python repro.py
```

This script creates a citation payload containing:

```json
"@id": "turn16search0"
```

and gives it directly to:

```python
ClientCitation.model_validate(payload)
```

Expected result:

```text
Value error, "ClientCitation" object has no field "at_id"
```

This is the smallest reproduction of the underlying model problem.

---

## Reproduction 2: full `Activity` validation

Run:

```bash
python repro_activity.py
```

This script places the same citation inside an Activity/AI entity, closer to the structure received from Copilot Studio, and then calls:

```python
Activity.model_validate(payload)
```

The validation path is approximately:

```text
Activity
  -> AIEntity
      -> citation[]
          -> ClientCitation
              -> _SchemaMixin
                  -> attempts to assign at_id
                      -> Pydantic exception
```

This demonstrates that the same issue occurs through the higher-level Activity deserialization path used by the Copilot Studio client.

---

# Why Direct Line does not show the same exception

Our project previously communicated with the same Copilot Studio agent through Microsoft Direct Line using a Direct Line secret. That evaluation path succeeds.

However, Direct Line and the signed-in Microsoft flow use different transports and different response parsing paths.

The signed-in flow explicitly passes the Copilot Studio SSE Activity through:

```python
Activity.model_validate_json(...)
```

from `microsoft-agents-activity`, which is the path where `ClientCitation` fails.

The existing Direct Line evaluation logs do not contain the raw Direct Line Activity JSON, so they do not prove whether Direct Line removes `@id` or simply processes the field without using this `ClientCitation` validation path.

Therefore, the confirmed statement is:

> The failure is specific to the Microsoft Agents SDK Activity/ClientCitation deserialization path used by the signed-in Copilot Studio integration. We have not yet established whether the Direct Line wire payload itself contains the same `@id` property.

---

# Affected SDK locations

## Copilot Studio response entry point

Package:

```text
microsoft-agents-copilotstudio-client==1.5.0
```

File:

```text
microsoft_agents/copilotstudio/client/copilot_client.py
```

Relevant method:

```text
CopilotClient.post_request()
```

Relevant operation:

```python
Activity.model_validate_json(activity_data)
```

## Schema property mapping

Package:

```text
microsoft-agents-activity==1.5.0
```

File:

```text
microsoft_agents/activity/entity/_schema_mixin.py
```

Relevant function:

```text
validate_schema_model(...)
```

Problematic operation:

```python
if "@id" in data:
    setattr(model, "at_id", data["@id"])
```

## Citation model

Package:

```text
microsoft-agents-activity==1.5.0
```

File:

```text
microsoft_agents/activity/entity/ai_entity.py
```

Relevant class:

```text
ClientCitation
```

Defined fields:

```text
at_type
position
appearance
```

Missing field involved in the exception:

```text
at_id
```

---

# Current conclusion

The signed-in Microsoft credentials are working and Copilot Studio is successfully returning responses.

The failure occurs after the response reaches the Python Microsoft Agents SDK:

```text
Copilot Studio returns citation with @id
        -> CopilotClient passes Activity JSON to microsoft-agents-activity
        -> citation is deserialized as ClientCitation
        -> _SchemaMixin attempts @id -> at_id
        -> ClientCitation does not define at_id
        -> Pydantic raises an exception
```

## Microsoft source references

- Microsoft Agents for Python repository: https://github.com/microsoft/Agents-for-python
- `CopilotClient` source: `libraries/microsoft-agents-copilotstudio-client/microsoft_agents/copilotstudio/client/copilot_client.py`
- `_SchemaMixin` source: `libraries/microsoft-agents-activity/microsoft_agents/activity/entity/_schema_mixin.py`
- `ClientCitation` source: `libraries/microsoft-agents-activity/microsoft_agents/activity/entity/ai_entity.py`