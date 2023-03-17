import pytest

from prefect.blocks.core import Block
from prefect.utilities.templating import (
    UNSET,
    apply_values,
    find_placeholders,
    resolve_block_document_references,
)


class TestFindPlaceholders:
    def test_empty_template(self):
        template = ""
        placeholders = find_placeholders(template)
        assert len(placeholders) == 0

    def test_single_placeholder(self):
        template = "Hello {{name}}!"
        placeholders = find_placeholders(template)
        assert len(placeholders) == 1
        assert placeholders.pop().name == "name"

    def test_multiple_placeholders(self):
        template = "Hello {{first_name}} {{last_name}}!"
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"first_name", "last_name"}

    def test_nested_placeholders(self):
        template = {"greeting": "Hello {{name}}!", "message": "{{greeting}}"}
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"name", "greeting"}

    def test_mixed_template(self):
        template = "Hello {{name}}! Your balance is ${{balance}}."
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"name", "balance"}

    def test_invalid_template(self):
        template = ("{{name}}!",)
        with pytest.raises(ValueError):
            find_placeholders(template)

    def test_nested_templates(self):
        template = {"greeting": "Hello {{name}}!", "message": {"text": "{{greeting}}"}}
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"name", "greeting"}

    def test_template_with_duplicates(self):
        template = "{{x}}{{x}}"
        placeholders = find_placeholders(template)
        assert len(placeholders) == 1
        assert placeholders.pop().name == "x"

    def test_template_with_unconventional_spacing(self):
        template = "Hello {{    first_name }} {{ last_name }}!"
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"first_name", "last_name"}


class TestApplyValues:
    def test_apply_values_simple_string_with_one_placeholder(self):
        assert apply_values("Hello, {{name}}!", {"name": "Alice"}) == "Hello, Alice!"

    def test_apply_values_simple_string_with_multiple_placeholders(self):
        assert (
            apply_values(
                "Hello, {{first_name}} {{last_name}}!",
                {"first_name": "Alice", "last_name": "Smith"},
            )
            == "Hello, Alice Smith!"
        )

    def test_apply_values_dictionary_with_placeholders(self):
        template = {"name": "{{first_name}} {{last_name}}", "age": "{{age}}"}
        values = {"first_name": "Alice", "last_name": "Smith", "age": 30}
        assert apply_values(template, values) == {"name": "Alice Smith", "age": 30}

    def test_apply_values_dictionary_with_unset_value(self):
        template = {"last_name": "{{last_name}}", "age": "{{age}}"}
        values = {"first_name": "Alice", "age": 30}
        assert apply_values(template, values) == {"age": 30}

    def test_apply_values_nested_dictionary_with_placeholders(self):
        template = {
            "name": {"first_name": "{{ first_name }}", "last_name": "{{ last_name }}"},
            "age": "{{age}}",
        }
        values = {"first_name": "Alice", "last_name": "Smith", "age": 30}
        assert apply_values(template, values) == {
            "name": {"first_name": "Alice", "last_name": "Smith"},
            "age": 30,
        }

    def test_apply_values_dictionary_with_UNSET_value_removed(self):
        template = {"name": UNSET, "age": "{{age}}"}
        values = {"age": 30}
        assert apply_values(template, values) == {"age": 30}

    def test_apply_values_list_with_placeholders(self):
        template = [
            "Hello, {{first_name}} {{last_name}}!",
            {"name": "{{first_name}} {{last_name}}"},
        ]
        values = {"first_name": "Alice", "last_name": "Smith"}
        assert apply_values(template, values) == [
            "Hello, Alice Smith!",
            {"name": "Alice Smith"},
        ]

    def test_apply_values_integer_input(self):
        assert apply_values(123, {"name": "Alice"}) == 123

    def test_apply_values_float_input(self):
        assert apply_values(3.14, {"pi": 3.14}) == 3.14

    def test_apply_values_boolean_input(self):
        assert apply_values(True, {"flag": False}) is True


class TestResolveBlockDocumentReferences:
    @pytest.fixture
    async def block_document_id(self):
        class ArbitraryBlock(Block):
            a: int
            b: str

        return await ArbitraryBlock(a=1, b="hello").save(name="arbitrary-block")

    async def test_resolve_block_document_references_with_no_block_document_references(
        self,
    ):
        assert await resolve_block_document_references({"key": "value"}) == {
            "key": "value"
        }

    async def test_resolve_block_document_references_with_one_block_document_reference(
        self, orion_client, block_document_id
    ):
        assert {
            "key": {"a": 1, "b": "hello"}
        } == await resolve_block_document_references(
            {"key": {"$ref": {"block_document_id": block_document_id}}},
            client=orion_client,
        )

    async def test_resolve_block_document_references_with_nested_block_document_references(
        self, orion_client, block_document_id
    ):
        template = {
            "key": {
                "nested_key": {"$ref": {"block_document_id": block_document_id}},
                "other_nested_key": {"$ref": {"block_document_id": block_document_id}},
            }
        }
        block_document_data = {"a": 1, "b": "hello"}

        result = await resolve_block_document_references(template, client=orion_client)

        assert result == {
            "key": {
                "nested_key": block_document_data,
                "other_nested_key": block_document_data,
            }
        }

    async def test_resolve_block_document_references_with_list_of_block_document_references(
        self, orion_client, block_document_id
    ):
        # given
        template = [{"$ref": {"block_document_id": block_document_id}}]
        block_document_data = {"a": 1, "b": "hello"}

        # when
        result = await resolve_block_document_references(template, client=orion_client)

        # then
        assert result == [block_document_data]