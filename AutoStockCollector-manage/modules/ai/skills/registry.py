from typing import Any, Dict, List, Optional
from modules.ai.skills.loader import SkillLoader


class SkillRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loader = SkillLoader()
            cls._instance._loaded_skills: Dict[str, str] = {}
        return cls._instance

    def list_skills(self) -> List[Dict[str, str]]:
        return self._loader.list_skills()

    def get_skill(self, skill_name: str) -> Optional[str]:
        if skill_name not in self._loaded_skills:
            content = self._loader.load_skill(skill_name)
            if content:
                self._loaded_skills[skill_name] = content
        return self._loaded_skills.get(skill_name)

    def get_skill_summaries(self) -> str:
        skills = self.list_skills()
        if not skills:
            return ""
        lines = ["可用技能:"]
        for s in skills:
            lines.append(f"  - {s['name']}: {s['description']}")
        return "\n".join(lines)


skill_registry = SkillRegistry()
