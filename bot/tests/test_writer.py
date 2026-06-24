"""Tests for the writer module — JSON atomicity, TXT append, finalization."""

import asyncio
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from captions.captions import TranscriptSegment
from output.writer import TranscriptWriter


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary output directory."""
    return str(tmp_path / "output")


@pytest.fixture
def writer(tmp_dir):
    return TranscriptWriter(output_dir=tmp_dir)


def _make_segment(speaker="Speaker_00", start=0.0, text="Hello world", timestamp="0:00:00"):
    """Helper to create a TranscriptSegment."""
    return TranscriptSegment(
        speaker=speaker,
        start=start,
        text=text,
        timestamp_human=timestamp,
    )


@pytest.mark.asyncio
async def test_append_creates_files(writer, tmp_dir):
    """Appending a segment creates transcript.json and transcript.txt."""
    seg = _make_segment(start=12.4, text="Hello world", timestamp="0:00:12")
    await writer.append(seg)

    json_path = os.path.join(tmp_dir, "transcript.json")
    txt_path = os.path.join(tmp_dir, "transcript.txt")

    assert os.path.exists(json_path)
    assert os.path.exists(txt_path)

    # Verify JSON content
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["speaker"] == "Speaker_00"
    assert data[0]["text"] == "Hello world"

    # Verify TXT content
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "[0:00:12] Speaker_00: Hello world" in content


@pytest.mark.asyncio
async def test_multiple_appends(writer, tmp_dir):
    """Multiple appends accumulate correctly."""
    for i in range(3):
        seg = _make_segment(
            speaker=f"Speaker_{i:02d}",
            start=float(i * 10),
            text=f"Segment {i}",
            timestamp=f"0:0{i}:00",
        )
        await writer.append(seg)

    json_path = os.path.join(tmp_dir, "transcript.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 3

    txt_path = os.path.join(tmp_dir, "transcript.txt")
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 3


@pytest.mark.asyncio
async def test_finalize_prints_summary(writer, tmp_dir, capsys):
    """Finalize prints a summary to stdout."""
    seg = _make_segment(start=0.0, text="Test", timestamp="0:00:00")
    await writer.append(seg)
    await writer.finalize()

    captured = capsys.readouterr()
    assert "TRANSCRIPT FINALIZED" in captured.out
    assert "Segments:   1" in captured.out
    assert "Speakers:   1" in captured.out


@pytest.mark.asyncio
async def test_finalize_idempotent(writer, tmp_dir):
    """Calling finalize twice doesn't crash."""
    await writer.finalize()
    await writer.finalize()  # should be a no-op


@pytest.mark.asyncio
async def test_json_is_valid_after_each_append(writer, tmp_dir):
    """JSON file is always valid — atomic writes prevent corruption."""
    json_path = os.path.join(tmp_dir, "transcript.json")

    for i in range(5):
        seg = _make_segment(
            start=float(i),
            text=f"Word {i}",
            timestamp=f"0:00:0{i}",
        )
        await writer.append(seg)

        # JSON should be valid after every append
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == i + 1
