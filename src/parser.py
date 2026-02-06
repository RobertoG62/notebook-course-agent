"""Phase 2a: Parse raw NotebookLM answers into structured sections."""

import re
from dataclasses import dataclass, field


@dataclass
class Section:
    """A parsed content section."""
    type: str  # h3, paragraph, bullet_list, sub_list, tip_box, numbered_list
    content: str
    items: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)


class ContentParser:
    """Parse NotebookLM markdown-style text into structured sections."""

    # Regex patterns matching NotebookLM output format
    RE_NUMBERED_HEADER = re.compile(r"^\d+\.\s+(.+?)[\s]*$")
    RE_BULLET = re.compile(r"^[•●]\s+(.+)$")
    RE_SUB_BULLET = re.compile(r"^\s+[◦○]\s+(.+)$")
    RE_PHONE = re.compile(r"(05[0-9]-?\d{3}-?\d{4})")
    RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
    RE_FOOTNOTE = re.compile(r"\d{1,2}(?:,\d{1,2})*\.?(?:\.\.\.\.|\.{0,3})(?=\s|$|[,)])")

    # Tip box triggers (Hebrew)
    TIP_TRIGGERS = {
        "pro": ["טיפ", "הטיפ של", "טיפ מקצועי", "טיפ של"],
        "warning": ["אזהרה", "זהירות", "שימו לב"],
        "danger": ["סכנה", "סכנת חיים", "חוק ברזל"],
        "info": ["הערה", "חשוב", "מידע"],
    }

    def parse(self, raw_text: str) -> list[Section]:
        """Parse raw answer text into a list of Sections."""
        lines = raw_text.strip().split("\n")
        sections = []
        current_bullets = []
        current_sub_bullets = []
        in_bullet_list = False

        for line in lines:
            stripped = line.strip()

            # Skip empty lines (flush current list)
            if not stripped:
                if in_bullet_list:
                    self._flush_bullets(sections, current_bullets, current_sub_bullets)
                    current_bullets = []
                    current_sub_bullets = []
                    in_bullet_list = False
                continue

            # Check for numbered header (e.g., "1. הבית על הגב 🏠")
            m = self.RE_NUMBERED_HEADER.match(stripped)
            if m and self._has_emoji(stripped):
                if in_bullet_list:
                    self._flush_bullets(sections, current_bullets, current_sub_bullets)
                    current_bullets = []
                    current_sub_bullets = []
                    in_bullet_list = False
                sections.append(Section(type="h3", content=self._clean_text(m.group(1))))
                continue

            # Check for sub-bullet (must check before bullet)
            m = self.RE_SUB_BULLET.match(line)  # Use original line (needs indent)
            if m:
                current_sub_bullets.append(self._clean_text(m.group(1)))
                in_bullet_list = True
                continue

            # Check for bullet
            m = self.RE_BULLET.match(stripped)
            if m:
                # Flush sub-bullets into previous bullet
                if current_sub_bullets and current_bullets:
                    current_bullets[-1] = (current_bullets[-1], list(current_sub_bullets))
                    current_sub_bullets = []
                current_bullets.append(self._clean_text(m.group(1)))
                in_bullet_list = True
                continue

            # Check for tip box trigger
            tip_type = self._detect_tip_type(stripped)
            if tip_type:
                if in_bullet_list:
                    self._flush_bullets(sections, current_bullets, current_sub_bullets)
                    current_bullets = []
                    current_sub_bullets = []
                    in_bullet_list = False
                sections.append(Section(
                    type="tip_box",
                    content=self._clean_text(stripped),
                    meta={"variant": tip_type}
                ))
                continue

            # Default: paragraph
            if in_bullet_list:
                self._flush_bullets(sections, current_bullets, current_sub_bullets)
                current_bullets = []
                current_sub_bullets = []
                in_bullet_list = False

            sections.append(Section(type="paragraph", content=self._clean_text(stripped)))

        # Flush remaining bullets
        if in_bullet_list:
            self._flush_bullets(sections, current_bullets, current_sub_bullets)

        return sections

    def _flush_bullets(self, sections: list, bullets: list, sub_bullets: list):
        """Add accumulated bullets as a list section."""
        if sub_bullets and bullets:
            # Attach remaining sub-bullets to last bullet
            last = bullets[-1]
            if isinstance(last, str):
                bullets[-1] = (last, list(sub_bullets))

        if bullets:
            sections.append(Section(type="bullet_list", content="", items=list(bullets)))

    def _detect_tip_type(self, text: str) -> str | None:
        """Check if line starts with a tip box trigger word."""
        for variant, triggers in self.TIP_TRIGGERS.items():
            for trigger in triggers:
                if text.startswith(trigger + ":") or text.startswith(trigger + " "):
                    return variant
        return None

    def _has_emoji(self, text: str) -> bool:
        """Check if text contains emoji characters."""
        for ch in text:
            if ord(ch) > 0x1F000:
                return True
        return False

    def _clean_text(self, text: str) -> str:
        """Clean footnote markers from text."""
        return self.RE_FOOTNOTE.sub("", text).strip()
