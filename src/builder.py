"""Phase 2b: Convert parsed sections into HTML components and assemble chapters."""

import re
from pathlib import Path
from .parser import Section, ContentParser

RE_PHONE = re.compile(r"(05[0-9]-?\d{3}-?\d{4})")
RE_BOLD_MARKERS = re.compile(r"\*\*(.+?)\*\*")


def _enhance_text(text: str) -> str:
    """Add HTML enhancements: bold, phone links."""
    text = RE_BOLD_MARKERS.sub(r"<strong>\1</strong>", text)
    text = RE_PHONE.sub(r'<a href="tel:\1">\1</a>', text)
    return text


class HTMLBuilder:
    """Build HTML from chapter files or parsed sections, assembled into template."""

    TIP_CONFIG = {
        "pro":     {"icon": "💡", "label": "טיפ מקצועי", "css": "pro"},
        "info":    {"icon": "ℹ️", "label": "מידע",       "css": "info"},
        "warning": {"icon": "⚡", "label": "אזהרה",      "css": "warning"},
        "danger":  {"icon": "🛑", "label": "סכנה",       "css": "danger"},
    }

    def __init__(self, template_path: Path, config: dict):
        self.template = template_path.read_text(encoding="utf-8")
        self.template_dir = template_path.parent
        self.config = config
        self.parser = ContentParser()

    def build(self, raw_dir: Path, output_path: Path):
        """Build the full HTML from chapter files (preferred) or raw answers."""
        html = self.template
        chapters_dir = self.template_dir / "chapters"

        chapters = self.config["chapters"]
        for ch in chapters:
            ch_id = ch["id"]

            print(f"  Building Chapter {ch_id}: {ch['title']}")

            # Priority 1: Pre-built rich chapter HTML
            ch_file = chapters_dir / f"ch{ch_id}.html"
            if ch_file.exists():
                content = ch_file.read_text(encoding="utf-8")
                print(f"    Using rich template: {ch_file.name}")
            else:
                # Priority 2: Generate from raw data (basic fallback)
                print(f"    Generating from raw data (fallback)...")
                content = self._generate_from_raw(ch, raw_dir)

            placeholder = f"{{{{CHAPTER_{ch_id}_CONTENT}}}}"
            html = html.replace(placeholder, content)

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        # Verify no remaining placeholders
        remaining = re.findall(r"\{\{CHAPTER_\d+_CONTENT\}\}", html)
        if remaining:
            print(f"  WARNING: unfilled placeholders: {remaining}")

        return len(html)

    def _generate_from_raw(self, ch: dict, raw_dir: Path) -> str:
        """Fallback: generate basic HTML from raw answer files."""
        q_ids = ch["questions"]
        parts = []

        for q_id in q_ids:
            raw_file = raw_dir / f"{q_id}.txt"
            if raw_file.exists():
                raw_text = raw_file.read_text(encoding="utf-8")
                sections = self.parser.parse(raw_text)
                chapter_html = self._sections_to_html(sections)
                parts.append(chapter_html)
            else:
                print(f"    Missing: {raw_file.name}")

        return "\n<hr class='chapter-divider'>\n".join(parts) if parts else "<p>תוכן בקרוב...</p>"

    def _sections_to_html(self, sections: list[Section]) -> str:
        """Convert a list of parsed sections to HTML string."""
        parts = []
        for sec in sections:
            if sec.type == "h3":
                parts.append(f"<h3>{_enhance_text(sec.content)}</h3>")
            elif sec.type == "paragraph":
                parts.append(f"<p>{_enhance_text(sec.content)}</p>")
            elif sec.type == "bullet_list":
                parts.append(self._build_list(sec.items))
            elif sec.type == "tip_box":
                variant = sec.meta.get("variant", "info")
                parts.append(self._build_tip_box(sec.content, variant))
        return "\n".join(parts)

    def _build_list(self, items: list) -> str:
        """Build <ul> with optional nested sub-lists."""
        html = "<ul>\n"
        for item in items:
            if isinstance(item, tuple):
                text, subs = item
                html += f"<li>{_enhance_text(text)}\n<ul>\n"
                for sub in subs:
                    html += f"<li>{_enhance_text(sub)}</li>\n"
                html += "</ul>\n</li>\n"
            else:
                html += f"<li>{_enhance_text(item)}</li>\n"
        html += "</ul>"
        return html

    def _build_tip_box(self, content: str, variant: str) -> str:
        """Build a tip-box div."""
        cfg = self.TIP_CONFIG.get(variant, self.TIP_CONFIG["info"])
        return (
            f'<div class="tip-box {cfg["css"]}">\n'
            f'<div class="tip-label"><span class="tip-icon">{cfg["icon"]}</span> {cfg["label"]}</div>\n'
            f"<p>{_enhance_text(content)}</p>\n"
            f"</div>"
        )
