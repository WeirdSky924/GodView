from uuid import uuid4

from app.services.director import DirectorSystem


def test_director_character_agent_accepts_uuid_current_region_id():
    """DB rows may return UUID objects for character region references."""
    region_id = uuid4()
    director = DirectorSystem(world_data={"id": "world-1", "name": "World"}, project_id="project-1")

    agent = director._create_character_agent({
        "id": str(uuid4()),
        "name": "区域角色",
        "project_id": str(uuid4()),
        "world_id": str(uuid4()),
        "current_region_id": region_id,
        "current_location": "观测塔",
    })

    assert agent.character.current_region_id == str(region_id)
