import json
import unittest
from unittest.mock import patch

from adcheck.semantic import review


class SemanticTests(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_ark_responses_payload_contains_text_and_image(self, mock_openai):
        client = mock_openai.return_value
        client.responses.create.return_value.output_text = json.dumps({"findings": []})

        result = review(
            "OCR文字",
            "ark-test-key",
            "doubao-test-model",
            base_url="https://ark.example/api/v3",
            images=[(b"png", "image/png")],
        )

        self.assertEqual(result, [])
        mock_openai.assert_called_once_with(
            api_key="ark-test-key",
            base_url="https://ark.example/api/v3",
        )
        request = client.responses.create.call_args.kwargs
        self.assertEqual(request["model"], "doubao-test-model")
        content = request["input"][0]["content"]
        self.assertEqual(content[0]["type"], "input_text")
        self.assertEqual(content[1]["type"], "input_image")
        self.assertTrue(content[1]["image_url"].startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
