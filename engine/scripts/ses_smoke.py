"""Live SES smoke test: send one complaint-style email through SESEmailChannel.

Self-addressed send (verified sender -> same verified address) which is
allowed in SES sandbox mode.

Run: PYTHONPATH=engine .venv/bin/python engine/scripts/ses_smoke.py [to_address]
Defaults to the verified identity tebakiapp@gmail.com.
"""

import sys

from app.channels import SESEmailChannel


def main() -> int:
    to = sys.argv[1] if len(sys.argv) > 1 else "tebakiapp@gmail.com"
    channel = SESEmailChannel(
        to_address=to,
        from_address="tebakiapp@gmail.com",
    )
    result = channel.file(
        {
            "category": "waste",
            "lat": 9.0100,
            "lon": 38.7600,
            "subject": "Tebaki test: waste issue in Arada (1 report)",
            "text": (
                "Residents report a waste issue at approximate location "
                "(9.0100, 38.7600) in Arada sub-city.\n"
                "Number of resident reports: 1.\n"
                "Details: garbage pile on sidewalk for two weeks.\n"
                "We request acknowledgment and a resolution timeline as required "
                "by the applicable regulations."
            ),
            "cite": "Solid Waste Management Proclamation No. 513/2007",
        }
    )
    print(f"ok={result.ok} channel={result.channel}")
    print(result.detail)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
