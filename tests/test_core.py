import unittest
from types import SimpleNamespace

from pharmacheck_core import AzureConfigurationError, extract_fields, resolve_azure_config


def pair(key, value):
    return SimpleNamespace(
        key=None if key is None else SimpleNamespace(content=key),
        value=None if value is None else SimpleNamespace(content=value),
    )


class ConfigurationTests(unittest.TestCase):
    def test_missing_configuration_names_only(self):
        with self.assertRaises(AzureConfigurationError) as caught:
            resolve_azure_config({})
        self.assertIn("AZURE_ENDPOINT", str(caught.exception))
        self.assertIn("AZURE_KEY", str(caught.exception))

    def test_environment_wins_without_reading_secrets(self):
        def unavailable_secrets(name):
            raise AssertionError("Environment should avoid a secrets read")
        config = resolve_azure_config(
            {"AZURE_ENDPOINT": " https://example.cognitiveservices.azure.com/ ", "AZURE_KEY": " env-test-value "},
            unavailable_secrets,
        )
        self.assertEqual(config.endpoint, "https://example.cognitiveservices.azure.com/")
        self.assertEqual(config.key, "env-test-value")
        self.assertNotIn("env-test-value", repr(config))
        self.assertNotIn("example", repr(config))

    def test_local_secrets_fallback(self):
        secrets = {"AZURE_ENDPOINT": "https://example.cognitiveservices.azure.com/", "AZURE_KEY": "local-test-value"}
        config = resolve_azure_config({"AZURE_KEY": " "}, secrets.__getitem__)
        self.assertEqual(config.key, "local-test-value")

    def test_missing_secrets_file_has_no_raw_error(self):
        def absent(name):
            raise FileNotFoundError("PRIVATE_FILE_PATH_OR_VALUE")
        with self.assertRaises(AzureConfigurationError) as caught:
            resolve_azure_config({}, absent)
        self.assertNotIn("PRIVATE_FILE_PATH_OR_VALUE", str(caught.exception))

    def test_malformed_secrets_have_no_raw_error(self):
        def malformed(name):
            raise ValueError("PRIVATE_MALFORMED_VALUE")
        with self.assertRaises(AzureConfigurationError) as caught:
            resolve_azure_config({}, malformed)
        self.assertNotIn("PRIVATE_MALFORMED_VALUE", str(caught.exception))

    def test_invalid_endpoint_rejected_without_echoing_value(self):
        for endpoint in ("http://example.test", "not-a-url", "https://name:PRIVATE@example.test", "https://example.test?key=PRIVATE", "https://example.test:bad"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(AzureConfigurationError) as caught:
                    resolve_azure_config({"AZURE_ENDPOINT": endpoint, "AZURE_KEY": "PRIVATE"})
                self.assertNotIn(endpoint, str(caught.exception))
                self.assertNotIn("PRIVATE", str(caught.exception))


class ExtractionTests(unittest.TestCase):
    def test_primary_fields_case_colon_and_other_fields(self):
        fields, other = extract_fields([
            pair(" Batch No: ", "B-001"), pair("Kadaluarsa:", "2028-01"),
            pair("PRODUCT NAME", "Synthetic material"), pair("Supplier:", "Example"),
        ])
        self.assertEqual(fields, {"Batch Number": "B-001", "Expire Date": "2028-01", "Material Name": "Synthetic material"})
        self.assertEqual(other, {"Supplier:": "Example"})

    def test_no_pairs_preserves_placeholders(self):
        for pairs in (None, []):
            self.assertEqual(extract_fields(pairs), ({"Batch Number": "-", "Expire Date": "-", "Material Name": "-"}, {}))

    def test_missing_key_is_ignored_and_missing_value_is_empty(self):
        fields, other = extract_fields([pair(None, "ignored"), pair("Lot No", None), pair("Supplier", None)])
        self.assertEqual(fields["Batch Number"], "")
        self.assertEqual(other, {"Supplier": ""})

    def test_last_match_wins_like_original(self):
        fields, other = extract_fields([pair("Batch", "first"), pair("Lot", "last"), pair("Supplier", "A"), pair("Supplier", "B")])
        self.assertEqual(fields["Batch Number"], "last")
        self.assertEqual(other, {"Supplier": "B"})

    def test_batch_priority_when_key_matches_multiple_groups(self):
        fields, _ = extract_fields([pair("Batch expiration product", "preserved-order")])
        self.assertEqual(fields["Batch Number"], "preserved-order")
        self.assertEqual(fields["Expire Date"], "-")

    def test_historical_ed_substring_behavior_is_preserved(self):
        # Known broad keyword collision; changing it would be an extraction redesign.
        fields, _ = extract_fields([pair("Prepared by", "Example")])
        self.assertEqual(fields["Expire Date"], "Example")


if __name__ == "__main__":
    unittest.main()
