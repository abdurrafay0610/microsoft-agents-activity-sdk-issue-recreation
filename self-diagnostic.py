import inspect
from importlib.metadata import version

from microsoft_agents.activity import ClientCitation
from microsoft_agents.activity.entity._schema_mixin import validate_schema_model


print("=== Versions ===")
print("microsoft-agents-activity:", version("microsoft-agents-activity"))
print("pydantic:", version("pydantic"))

print("\n=== Installed source ===")
print("ClientCitation:", inspect.getfile(ClientCitation))
print("validate_schema_model:", inspect.getfile(validate_schema_model))

print("\n=== ClientCitation fields ===")
print(list(ClientCitation.model_fields))

payload = {
    "@type": "Claim",
    "@id": "turn16search0",
    "position": 1,
    "appearance": {
        "@type": "DigitalDocument",
        "name": "Example",
    },
}

print("\n=== Input ===")
print(payload)

print("\n=== Validation ===")
ClientCitation.model_validate(payload)