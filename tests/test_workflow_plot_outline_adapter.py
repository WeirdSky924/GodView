import pytest

from app.models.workflow_execution import WorkflowExecution, WorkflowStatus
from app.services.workflow_adapters import plot_outline_adapter as plot_outline_adapter_module


class _FakeOutlineGenerationResult:
    def __init__(self, outline, *, suggestions=None, warnings=None):
        self.outline = outline
        self.suggestions = suggestions or []
        self.warnings = warnings or []


class _FakePlotOutlineService:
    def __init__(
        self,
        *,
        stored_outline=None,
        generated_outline=None,
        suggestions=None,
        warnings=None,
        next_chapter_number=1,
    ):
        self.stored_outline = stored_outline
        self.generated_outline = generated_outline
        self.suggestions = suggestions or []
        self.warnings = warnings or []
        self.next_chapter_number = next_chapter_number
        self.calls = {
            "get_next_chapter_number": [],
            "get_chapter_outline_for_workflow": [],
            "generate_outline": [],
        }

    async def get_next_chapter_number(self, project_id):
        self.calls["get_next_chapter_number"].append(project_id)
        return self.next_chapter_number

    async def get_chapter_outline_for_workflow(self, project_id, chapter_number):
        self.calls["get_chapter_outline_for_workflow"].append(
            {"project_id": project_id, "chapter_number": chapter_number}
        )
        return self.stored_outline

    async def generate_outline(self, **kwargs):
        self.calls["generate_outline"].append(dict(kwargs))
        return _FakeOutlineGenerationResult(
            self.generated_outline,
            suggestions=self.suggestions,
            warnings=self.warnings,
        )


class TestPlotOutlineWorkflowAdapter:
    def setup_method(self):
        self.adapter = plot_outline_adapter_module.PlotOutlineWorkflowAdapter()

    def _make_execution(self, *, context=None):
        return WorkflowExecution(
            workflow_id="test-wf",
            project_id="test-project",
            status=WorkflowStatus.RUNNING,
            context=context or {},
            node_states={},
        )

    @staticmethod
    def _assert_output_shape(result):
        assert set(result.keys()) == {
            "chapter_number",
            "chapter_title",
            "chapter_outline",
            "chapter_summary",
            "chapter_goals",
            "scene_directions",
            "outline_id",
            "saved_outline",
            "suggestions",
            "warnings",
            "outline_source",
        }
        assert result["saved_outline"] == result["chapter_outline"]
        assert result["scene_directions"]["chapter_number"] == result["chapter_number"]
        assert result["scene_directions"]["chapter_title"] == result["chapter_title"]
        assert result["scene_directions"]["plot_focus"] == result["chapter_summary"]
        assert result["scene_directions"]["chapter_goals"] == result["chapter_goals"]
        assert result["scene_directions"]["scenes"] == result["chapter_outline"]["scenes"]

    @pytest.mark.asyncio
    async def test_execute_prefers_context_outline_without_querying_or_generating(self, monkeypatch):
        context_outline = {
            "id": "outline-context-1",
            "chapter_number": 7,
            "title": "潮汐裂隙",
            "summary": "主角进入潮汐裂隙核心区。",
            "chapter_goals": ["确认裂隙来源", "保护洛澜"],
            "scenes": [
                {
                    "title": "裂隙入口",
                    "participating_characters": ["林砚", "洛澜"],
                }
            ],
        }
        service = _FakePlotOutlineService(generated_outline={"id": "generated-ignored"})
        monkeypatch.setattr(plot_outline_adapter_module, "get_plot_outline_service", lambda: service)

        result = await self.adapter.execute(
            node=None,
            execution=self._make_execution(
                context={
                    "chapter_num": 7,
                    "chapter_outline": context_outline,
                }
            ),
            db=None,
        )

        self._assert_output_shape(result)
        assert result["chapter_number"] == 7
        assert result["chapter_title"] == "潮汐裂隙"
        assert result["chapter_summary"] == "主角进入潮汐裂隙核心区。"
        assert result["chapter_goals"] == ["确认裂隙来源", "保护洛澜"]
        assert result["outline_id"] == "outline-context-1"
        assert result["outline_source"] == "context"
        assert result["suggestions"] == []
        assert result["warnings"] == []
        assert result["scene_directions"]["selected_characters"] == ["林砚", "洛澜"]
        assert service.calls["get_chapter_outline_for_workflow"] == []
        assert service.calls["generate_outline"] == []

    @pytest.mark.asyncio
    async def test_execute_reads_stored_outline_before_generation(self, monkeypatch):
        stored_outline = {
            "id": "outline-db-2",
            "chapter_number": 8,
            "title": "雾港余烬",
            "summary": "众人在废墟中寻找残留线索。",
            "chapter_goals": ["确认幸存者", "回收地图残片"],
            "scenes": [
                {
                    "title": "废墟搜寻",
                    "participating_characters": ["沈夜"],
                }
            ],
        }
        service = _FakePlotOutlineService(
            stored_outline=stored_outline,
            generated_outline={"id": "generated-ignored"},
        )
        monkeypatch.setattr(plot_outline_adapter_module, "get_plot_outline_service", lambda: service)

        result = await self.adapter.execute(
            node=None,
            execution=self._make_execution(context={"chapter_num": 8}),
            db=None,
        )

        self._assert_output_shape(result)
        assert result["chapter_number"] == 8
        assert result["chapter_title"] == "雾港余烬"
        assert result["outline_id"] == "outline-db-2"
        assert result["outline_source"] == "database"
        assert result["suggestions"] == []
        assert result["warnings"] == []
        assert service.calls["get_chapter_outline_for_workflow"] == [
            {"project_id": "test-project", "chapter_number": 8}
        ]
        assert service.calls["generate_outline"] == []

    @pytest.mark.asyncio
    async def test_execute_falls_back_to_generate_when_outline_missing(self, monkeypatch):
        generated_outline = {
            "id": "outline-generated-3",
            "title": "裂钟回响",
            "summary": "守夜人从回响中拼出真相。",
            "chapter_goals": "阻止裂钟再次鸣响",
            "scenes": [
                {
                    "title": "钟楼顶层",
                    "participating_characters": ["守夜人", "洛澜", "守夜人"],
                }
            ],
        }
        service = _FakePlotOutlineService(
            stored_outline=None,
            generated_outline=generated_outline,
            suggestions=["补充钟楼结构细节"],
            warnings=["上一章摘要缺失，已按有限上下文生成"],
        )
        monkeypatch.setattr(plot_outline_adapter_module, "get_plot_outline_service", lambda: service)

        result = await self.adapter.execute(
            node=None,
            execution=self._make_execution(
                context={
                    "chapter_num": 9,
                    "chapter_title": "预设标题",
                    "chapter_summary": "预设摘要",
                    "previous_chapters": [
                        {"chapter_num": 7, "title": "潮汐裂隙", "summary": "进入裂隙"},
                        {"chapter_num": 8, "title": "雾港余烬", "summary": "搜寻残片"},
                    ],
                }
            ),
            db=None,
        )

        self._assert_output_shape(result)
        assert result["chapter_number"] == 9
        assert result["chapter_title"] == "裂钟回响"
        assert result["chapter_summary"] == "守夜人从回响中拼出真相。"
        assert result["chapter_goals"] == ["阻止裂钟再次鸣响"]
        assert result["outline_id"] == "outline-generated-3"
        assert result["outline_source"] == "generated"
        assert result["suggestions"] == ["补充钟楼结构细节"]
        assert result["warnings"] == ["上一章摘要缺失，已按有限上下文生成"]
        assert result["scene_directions"]["selected_characters"] == ["守夜人", "洛澜"]
        assert service.calls["get_chapter_outline_for_workflow"] == [
            {"project_id": "test-project", "chapter_number": 9}
        ]
        assert len(service.calls["generate_outline"]) == 1
        generate_call = service.calls["generate_outline"][0]
        assert generate_call["project_id"] == "test-project"
        assert generate_call["chapter_number"] == 9
        assert "当前工作流目标章节：第9章" in generate_call["context"]
        assert "第7章《潮汐裂隙》：进入裂隙" in generate_call["previous_events"]
        assert "第8章《雾港余烬》：搜寻残片" in generate_call["previous_events"]
