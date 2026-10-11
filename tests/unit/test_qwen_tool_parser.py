"""Unit tests for the Qwen `<<{...}>>` tool-call parser (SOC fine-tune)."""

from __future__ import annotations

from forensics.inference.qwen_tool_parser import (
    parse_qwen_tool_calls,
    strip_tool_blocks,
)


def test_parse_primary_double_angle_block():
    text = '<<{"name": "query_logs", "arguments": {"host": "web-01", "minutes": 30}}>>'
    calls = parse_qwen_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].tool_name == "query_logs"
    assert calls[0].arguments == {"host": "web-01", "minutes": 30}


def test_parse_multiple_blocks_and_dedupe():
    text = (
        'Prose intro.\n'
        '<<{"name": "list_processes", "arguments": {}}>>\n'
        'middle\n'
        '<<{"name": "list_processes", "arguments": {}}>>\n'
        '<<{"name": "query_logs", "arguments": {"host": "db-01"}}>>\n'
    )
    calls = parse_qwen_tool_calls(text)
    assert [c.tool_name for c in calls] == ["list_processes", "query_logs"]


def test_parse_multiline_json_in_block():
    text = '<<{\n  "name": "t",\n  "arguments": {"a": [1, 2]}\n}>>'
    calls = parse_qwen_tool_calls(text)
    assert calls[0].arguments == {"a": [1, 2]}


def test_parse_string_arguments_are_decoded():
    text = '<<{"name": "t", "arguments": "{\\"host\\": \\"web-01\\"}"}>>'
    calls = parse_qwen_tool_calls(text)
    assert calls[0].arguments == {"host": "web-01"}


def test_parse_qwen_double_bracket_list_fallback():
    text = '[[{"name": "t", "arguments": {"a": 1}}]]'
    calls = parse_qwen_tool_calls(text)
    assert len(calls) == 1 and calls[0].tool_name == "t"
    multi = '[[{"name": "a", "arguments": {}}, {"name": "b", "arguments": {}}]]'
    assert [c.tool_name for c in parse_qwen_tool_calls(multi)] == ["a", "b"]


def test_parse_bare_json_array_last_resort():
    text = '[{"name": "t", "arguments": {"a": 1}}]'
    calls = parse_qwen_tool_calls(text)
    assert len(calls) == 1 and calls[0].tool_name == "t"


def test_prose_yields_no_calls():
    assert parse_qwen_tool_calls("The host looks compromised based on the logs.") == []


def test_invalid_blocks_are_skipped_not_fatal():
    text = '<<{broken json}>> <<{"name": "t", "arguments": {}}>>'
    calls = parse_qwen_tool_calls(text)
    assert [c.tool_name for c in calls] == ["t"]


def test_block_without_name_is_ignored():
    assert parse_qwen_tool_calls('<<{"arguments": {"a": 1}}>>') == []


def test_parameters_key_accepted_as_arguments():
    text = '<<{"name": "t", "parameters": {"a": 1}}>>'
    assert parse_qwen_tool_calls(text)[0].arguments == {"a": 1}


def test_strip_tool_blocks():
    text = (
        'Analysis before.\n'
        '<<{"name": "t", "arguments": {}}>>\n'
        '[[{"name": "u", "arguments": {}}]]\n'
        'Analysis after.'
    )
    stripped = strip_tool_blocks(text)
    assert "<<" not in stripped and "[[" not in stripped
    assert "Analysis before." in stripped and "Analysis after." in stripped
