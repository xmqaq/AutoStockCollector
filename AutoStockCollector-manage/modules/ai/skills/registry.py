from typing import Any, Dict, List, Optional
from modules.ai.skills.loader import SkillLoader


class SkillRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loader = SkillLoader()
            cls._instance._loaded_skills: Dict[str, str] = {}
            cls._instance._loaded_prompts: Dict[str, str] = {}
        return cls._instance

    def list_skills(self) -> List[Dict[str, str]]:
        return self._loader.list_skills()

    def get_skill(self, skill_name: str) -> Optional[str]:
        """返回 skill 全文（含 frontmatter），供前端展示。"""
        if skill_name not in self._loaded_skills:
            content = self._loader.load_skill(skill_name)
            if content:
                self._loaded_skills[skill_name] = content
        return self._loaded_skills.get(skill_name)

    def get_skill_prompt(self, skill_name: str) -> Optional[str]:
        """返回剥离 frontmatter 后的 skill 正文，供注入 agent system_prompt。

        从第二个 ``---`` 之后截取；无 frontmatter 则原样返回。结果做进程级缓存，
        避免每轮 agent 调用重复读盘。加载失败返回 None（调用方跳过注入）。
        """
        if skill_name in self._loaded_prompts:
            return self._loaded_prompts.get(skill_name)
        content = self.get_skill(skill_name)
        if not content:
            return None
        prompt = self._strip_frontmatter(content)
        self._loaded_prompts[skill_name] = prompt
        return prompt

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        """剥离 YAML frontmatter（首个 --- ... --- 块），返回其后正文。"""
        lines = content.split("\n")
        if not lines or lines[0].strip() != "---":
            return content.strip()
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is None:
            return content.strip()
        return "\n".join(lines[end + 1:]).strip()

    def get_skill_summaries(self) -> str:
        skills = self.list_skills()
        if not skills:
            return ""
        lines = ["可用技能:"]
        for s in skills:
            lines.append(f"  - {s['name']}: {s['description']}")
        return "\n".join(lines)


skill_registry = SkillRegistry()
