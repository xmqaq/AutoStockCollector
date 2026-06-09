import os
from pathlib import Path
from typing import Dict, List, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class SkillLoader:
    def __init__(self):
        self._bundled_dir = Path(__file__).parent / "defaults"
        self._user_dir = Path.home() / ".autostockcollector" / "skills" / "user"

    def list_skills(self) -> List[Dict[str, str]]:
        skills = []
        for skill_dir in [self._bundled_dir, self._user_dir]:
            if not skill_dir.exists():
                continue
            for entry in sorted(skill_dir.iterdir()):
                if entry.is_dir():
                    skill_file = entry / "SKILL.md"
                    if skill_file.exists():
                        meta = self._parse_metadata(skill_file)
                        if meta:
                            skills.append(meta)
        return skills

    def load_skill(self, skill_name: str) -> Optional[str]:
        for skill_dir in [self._bundled_dir, self._user_dir]:
            candidate = skill_dir / skill_name / "SKILL.md"
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")

        logger.warning(f"Skill '{skill_name}' not found")
        return None

    def _parse_metadata(self, path: Path) -> Optional[Dict[str, str]]:
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        meta = {}
        in_frontmatter = False
        for line in lines:
            if line.strip() == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                    continue
                else:
                    break
            if in_frontmatter and ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()
        if "name" not in meta:
            return None
        return {
            "name": meta.get("name", path.parent.name),
            "description": meta.get("description", "暂无描述"),
            "category": meta.get("category", "general"),
            "tools": meta.get("tools", ""),
            "skill_name": path.parent.name,
        }
