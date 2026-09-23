from importlib.metadata import version

from microsoft_agents.activity import Activity


print("microsoft-agents-activity:", version("microsoft-agents-activity"))
print("pydantic:", version("pydantic"))

payload = {
    "type": "message",
    "text": "Response containing a citation",
    "entities": [
        {
            "type": "https://schema.org/Message",
            "@type": "Message",
            "@context": "https://schema.org",
            "additionalType": ["AIGeneratedContent"],
            "citation": [
                {
                    "@type": "Claim",
                    "@id": "turn16search0",
                    "position": 1,
                    "appearance": {
                        "@type": "DigitalDocument",
                        "name": "Example citation",
                        "url": "https://example.com",
                    },
                }
            ],
        }
    ],
}

activity = Activity.model_validate(payload)

print(activity)