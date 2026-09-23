from importlib.metadata import version

from microsoft_agents.activity import ClientCitation


print("microsoft-agents-activity:", version("microsoft-agents-activity"))
print("pydantic:", version("pydantic"))
print("ClientCitation fields:", list(ClientCitation.model_fields))

payload = {
    "@type": "Claim",
    "@id": "turn16search0",
    "position": 1,
    "appearance": {
        "@type": "DigitalDocument",
        "name": "Example citation",
        "url": "https://example.com",
    },
}

print("Input:", payload)

citation = ClientCitation.model_validate(payload)

print("Parsed:", citation)