from datetime import datetime


class FakeAgentResponse:
    def __init__(self, structured_data, *, success=True, error=None, contract_id=None, schema_name=None, metadata=None):
        self.success = success
        self.error = error
        self.structured_data = structured_data
        self.text_output = None
        self.data = structured_data
        self.contract_id = contract_id
        self.schema_name = schema_name
        self.schema_version = None
        self.metadata = metadata or {}
        self.mode = None


class FakeDiscussionDB:
    def __init__(self):
        self.hooks = []
        self.lores = []
        self.regions = []
        self.characters = []
        self.executions = []
        self.existing_characters = {}
        self.regions_by_id = {}
        self.hooks_by_id = {}
        self.state_changes = {}
        self.chapters = []
        self.outlines = {}
        self.outline_status_events = []

    async def save_hook(self, hook_data):
        saved = dict(hook_data)
        hook_id = saved.get("id") or f"hook-{len(self.hooks_by_id) + 1}"
        saved["id"] = hook_id
        self.hooks.append(saved)
        self.hooks_by_id[hook_id] = saved
        return hook_id

    async def update_hook_status(self, hook_id, status):
        hook = self.hooks_by_id.get(hook_id)
        if hook:
            hook["status"] = status
        return True

    async def get_hook(self, hook_id):
        hook = self.hooks_by_id.get(hook_id)
        return dict(hook) if hook else None

    async def execute_write(self, query, params):
        if "lore_entries" in query:
            self.lores.append(dict(params))
        if "UPDATE chapter_outlines" in query and "status = 'completed'" in query:
            outline = self.outlines.get(params.get("id"))
            if outline:
                outline["status"] = "completed"
                self.outline_status_events.append(dict(params))
        return None

    async def execute_query(self, query, params=None):
        if "lore_entries" in query:
            return list(self.lores)
        if "FROM chapter_outlines" in query:
            outline = self.outlines.get((params or {}).get("id"))
            return [dict(outline)] if outline else []
        return []

    async def save_chapter(self, chapter_data):
        self.chapters.append(dict(chapter_data))
        return chapter_data.get("id")

    async def save_region(self, region_data):
        saved = dict(region_data)
        region_id = saved.get("id") or f"region-{len(self.regions_by_id) + 1}"
        saved["id"] = region_id
        self.regions.append(saved)
        self.regions_by_id[region_id] = saved
        return region_id

    async def get_character_by_project_and_name(self, project_id, name):
        for character in self.existing_characters.values():
            if character.get("project_id") == project_id and character.get("name", "").lower() == name.lower():
                return dict(character)
        return None

    async def get_character(self, character_id):
        character = self.existing_characters.get(character_id)
        return dict(character) if character else None

    async def get_all_characters(self, project_id=None, role=None, limit=100):
        characters = list(self.existing_characters.values())
        if project_id:
            characters = [character for character in characters if character.get("project_id") == project_id]
        return [dict(character) for character in characters[:limit]]

    async def get_region(self, region_id):
        region = self.regions_by_id.get(region_id)
        return dict(region) if region else None

    async def save_character(self, character_data):
        saved = dict(character_data)
        self.characters.append(saved)
        if saved.get("id"):
            self.existing_characters[saved["id"]] = saved
        return saved.get("id")

    async def save_narrative_state_change(self, change_data):
        fingerprint = change_data.get("fingerprint")
        if fingerprint:
            existing = await self.get_state_change_by_fingerprint(change_data.get("project_id"), fingerprint)
            if existing:
                return existing["id"]
        saved = dict(change_data)
        change_id = saved.get("id") or f"state-change-{len(self.state_changes) + 1}"
        saved["id"] = change_id
        self.state_changes[change_id] = saved
        return change_id

    async def get_narrative_state_change(self, change_id):
        change = self.state_changes.get(change_id)
        return dict(change) if change else None

    async def get_state_change_by_fingerprint(self, project_id, fingerprint):
        for change in self.state_changes.values():
            if change.get("project_id") == project_id and change.get("fingerprint") == fingerprint:
                return dict(change)
        return None

    async def list_narrative_state_changes(
        self,
        project_id,
        entity_type=None,
        entity_id=None,
        status=None,
        change_type=None,
        chapter_id=None,
        world_id=None,
        workflow_execution_id=None,
        limit=100,
    ):
        changes = [change for change in self.state_changes.values() if change.get("project_id") == project_id]
        if entity_type:
            changes = [change for change in changes if change.get("entity_type") == entity_type]
        if entity_id:
            changes = [change for change in changes if change.get("entity_id") == entity_id]
        if status:
            changes = [change for change in changes if change.get("status") == status]
        if change_type:
            changes = [change for change in changes if change.get("change_type") == change_type]
        if chapter_id:
            changes = [change for change in changes if change.get("chapter_id") == chapter_id]
        if world_id:
            changes = [change for change in changes if change.get("world_id") == world_id]
        if workflow_execution_id:
            changes = [change for change in changes if change.get("workflow_execution_id") == workflow_execution_id]
        return [dict(change) for change in changes[:limit]]

    async def update_narrative_state_change_status(self, change_id, status, timestamp_field=None):
        change = self.state_changes.get(change_id)
        if not change:
            return False
        change["status"] = status
        if timestamp_field:
            change[timestamp_field] = datetime.utcnow().isoformat()
        return True

    async def mark_narrative_state_change_applied(self, change_id):
        return await self.update_narrative_state_change_status(change_id, "applied", "applied_at")

    async def get_chapters_by_project(self, project_id, status=None, limit=100):
        chapters = [chapter for chapter in self.chapters if chapter.get("project_id") == project_id]
        if status:
            chapters = [chapter for chapter in chapters if chapter.get("status") == status]
        return [dict(chapter) for chapter in chapters[:limit]]
