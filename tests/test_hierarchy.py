import uuid
from app.db.repository import ChapterRepository

def test_hierarchy_flow():
    repo = ChapterRepository()
    
    # 1. Create Project
    project_id = str(uuid.uuid4())
    project = repo.create_project(project_id, "测试项目", "这是一个测试项目描述")
    print(f"✅ Project created: {project.name} ({project.id})")
    
    # 2. Create Novel
    novel_id = str(uuid.uuid4())
    novel = repo.create_novel(novel_id, project_id, "测试小说", "测试作者")
    print(f"✅ Novel created: {novel.title} under project {project.name}")
    
    # 3. Create Volume
    volume_id = str(uuid.uuid4())
    volume = repo.create_volume(volume_id, novel_id, "第一卷：启程", 0)
    print(f"✅ Volume created: {volume.title}")
    
    # 4. Save Chapter
    repo.save_chapter(
        session_id="test_session",
        index=1,
        title="第一章：觉醒",
        content="这是第一章的内容...",
        volume_id=volume_id
    )
    print(f"✅ Chapter saved with volume_id: {volume_id}")
    
    # 5. Query Back
    chapters = repo.get_chapters_by_volume(volume_id)
    assert len(chapters) == 1
    assert chapters[0].title == "第一章：觉醒"
    print(f"✅ Verification success: Found {len(chapters)} chapters in volume.")

    # 6. Novel Query
    n = repo.get_novel(novel_id)
    assert n.title == "测试小说"
    print(f"✅ Novel query success.")

    # 7. List Novels in Project
    novels = repo.get_novels(project_id)
    assert len(novels) == 1
    print(f"✅ List novels success: {novels[0].title}")

if __name__ == "__main__":
    try:
        test_hierarchy_flow()
        print("\n✨ ALL HIERARCHY TESTS PASSED ✨")
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
