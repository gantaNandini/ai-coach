import asyncio, sys
sys.path.insert(0, ".")
from app.core import startup as s
s.startup_status.update(pgvector="not_installed", database="ok", ollama="ok", embeddings="ok", ready=True)

async def main():
    from app.database.unit_of_work import UnitOfWork
    from app.models.module import CoachingModule, ModuleVersion
    from sqlalchemy import select

    async with UnitOfWork() as uow:
        mods = (await uow.session.execute(select(CoachingModule).where(CoachingModule.status=="published"))).scalars().all()
        for m in mods:
            print(f"Module: {m.name} ({m.key}) id={m.id}")
            mv = await uow.module_versions.get_current_version_with_definition(m.id)
            if mv:
                print(f"  Version: v{mv.version_number} framework={mv.framework_name}")
                print(f"  intake_schema: {len(mv.intake_schema or [])} fields")
                print(f"  scoring_rubric dims: {len((mv.scoring_rubric or {}).get('dimensions', []))}")
                print(f"  framework_steps: {len(mv.framework_steps or [])}")
                print(f"  prompt_templates: {len(mv.prompt_templates or [])}")
                print(f"  personas: {len(mv.personas or [])}")
                if mv.intake_schema:
                    for f in mv.intake_schema:
                        print(f"    field: {f.get('label')} ({f.get('field_key')})")
            else:
                print("  NO CURRENT VERSION FOUND!")
            print()

asyncio.run(main())
