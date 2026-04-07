"""Monolith parser — identify content blocks in uploaded docs.

See spec.md §3 (Monolith extraction flow).
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContentBlock:
    """A distinct content block extracted from a monolith document."""
    block_id: int
    heading: str
    content: str
    source_line: int = 0
    word_count: int = 0

    def __post_init__(self):
        self.word_count = len(self.content.split())


_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


def parse_document(content: str) -> list[ContentBlock]:
    """Split a monolith document into content blocks.

    Splits by heading (semantic break). Each heading starts a new block.
    Paragraphs without headings are grouped into the current block.

    Args:
        content: Full document text.

    Returns:
        Ordered list of ContentBlock objects.
    """
    blocks: list[ContentBlock] = []
    headings = list(_HEADING_RE.finditer(content))

    if not headings:
        # No headings — treat entire doc as one block
        if content.strip():
            blocks.append(ContentBlock(
                block_id=1,
                heading="(no heading)",
                content=content.strip(),
                source_line=1,
            ))
        return blocks

    # Content before first heading
    pre_content = content[:headings[0].start()].strip()
    if pre_content:
        blocks.append(ContentBlock(
            block_id=1,
            heading="(preamble)",
            content=pre_content,
            source_line=1,
        ))

    for i, match in enumerate(headings):
        title = match.group(2).strip()
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
        block_content = content[start:end].strip()

        line_num = content[:match.start()].count("\n") + 1

        blocks.append(ContentBlock(
            block_id=len(blocks) + 1,
            heading=title,
            content=block_content,
            source_line=line_num,
        ))

    return blocks
