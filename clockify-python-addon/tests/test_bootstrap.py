import pytest
from sqlalchemy import select
from app.db.models import BootstrapJob, WorkspaceData
from app.bootstrap import BootstrapService
from app.schemas.api_call import OpenAPIEndpoint
from types import SimpleNamespace


@pytest.mark.asyncio
async def test_bootstrap_job_creation(db_session, sample_workspace_id):
    """Test creating a bootstrap job."""
    
    job = BootstrapJob(
        workspace_id=sample_workspace_id,
        status="PENDING",
        total_endpoints=0,
        completed_endpoints=0,
        failed_endpoints=0
    )
    
    db_session.add(job)
    await db_session.commit()
    
    # Verify job was created
    result = await db_session.execute(
        select(BootstrapJob).where(
            BootstrapJob.workspace_id == sample_workspace_id
        )
    )
    stored_job = result.scalar_one_or_none()
    
    assert stored_job is not None
    assert stored_job.status == "PENDING"
    assert stored_job.workspace_id == sample_workspace_id


@pytest.mark.asyncio
async def test_bootstrap_job_status_update(db_session, sample_workspace_id):
    """Test updating bootstrap job status."""
    
    # Create job
    job = BootstrapJob(
        workspace_id=sample_workspace_id,
        status="PENDING"
    )
    db_session.add(job)
    await db_session.commit()
    job_id = job.id
    
    # Update to RUNNING
    result = await db_session.execute(
        select(BootstrapJob).where(BootstrapJob.id == job_id)
    )
    job = result.scalar_one()
    job.status = "RUNNING"
    job.total_endpoints = 10
    await db_session.commit()
    
    # Verify update
    result = await db_session.execute(
        select(BootstrapJob).where(BootstrapJob.id == job_id)
    )
    updated_job = result.scalar_one()
    assert updated_job.status == "RUNNING"
    assert updated_job.total_endpoints == 10


@pytest.mark.asyncio
async def test_workspace_data_storage(db_session, sample_workspace_id):
    """Test storing workspace data."""
    
    data = {
        "id": "project-123",
        "name": "Test Project",
        "clientId": "client-123"
    }
    
    workspace_data = WorkspaceData(
        workspace_id=sample_workspace_id,
        entity_type="projects",
        entity_id="project-123",
        data=data,
        source_endpoint="/v1/workspaces/{workspaceId}/projects"
    )
    
    db_session.add(workspace_data)
    await db_session.commit()
    
    # Verify storage
    result = await db_session.execute(
        select(WorkspaceData).where(
            WorkspaceData.workspace_id == sample_workspace_id,
            WorkspaceData.entity_type == "projects"
        )
    )
    stored_data = result.scalar_one_or_none()
    
    assert stored_data is not None
    assert stored_data.entity_id == "project-123"
    assert stored_data.data == data


@pytest.mark.asyncio
async def test_bootstrap_progress_tracking(db_session, sample_workspace_id):
    """Test tracking bootstrap progress."""
    
    job = BootstrapJob(
        workspace_id=sample_workspace_id,
        status="RUNNING",
        total_endpoints=5,
        completed_endpoints=0,
        failed_endpoints=0
    )
    db_session.add(job)
    await db_session.commit()
    job_id = job.id
    
    # Simulate progress
    for i in range(5):
        result = await db_session.execute(
            select(BootstrapJob).where(BootstrapJob.id == job_id)
        )
        job = result.scalar_one()
        
        if i < 4:
            job.completed_endpoints += 1
        else:
            job.failed_endpoints += 1
        
        await db_session.commit()
    
    # Verify final state
    result = await db_session.execute(
        select(BootstrapJob).where(BootstrapJob.id == job_id)
    )
    final_job = result.scalar_one()
    
    assert final_job.completed_endpoints == 4
    assert final_job.failed_endpoints == 1


@pytest.mark.asyncio
async def test_workspace_data_query_by_type(db_session, sample_workspace_id):
    """Test querying workspace data by entity type."""
    
    # Store multiple entities
    for i in range(3):
        data = WorkspaceData(
            workspace_id=sample_workspace_id,
            entity_type="projects",
            entity_id=f"project-{i}",
            data={"name": f"Project {i}"},
            source_endpoint="/v1/workspaces/{workspaceId}/projects"
        )
        db_session.add(data)
    
    await db_session.commit()
    
    # Query by type
    result = await db_session.execute(
        select(WorkspaceData).where(
            WorkspaceData.workspace_id == sample_workspace_id,
            WorkspaceData.entity_type == "projects"
        )
    )
    projects = result.scalars().all()
    
    assert len(projects) == 3


@pytest.mark.asyncio
async def test_bootstrap_paginates_beyond_ten_pages(monkeypatch):
    """Bootstrap should continue fetching until data is exhausted."""
    service = BootstrapService()
    endpoint = OpenAPIEndpoint(
        path="/v1/workspaces/{workspaceId}/projects",
        method="GET",
        parameters=[{"name": "workspaceId", "in": "path", "required": True}],
    )

    page_calls = []

    async def fake_execute(workspace_id, request):
        page = request.query.get("page", 1)
        page_calls.append(page)
        if len(page_calls) <= 11:
            payload = [{"id": f"p-{len(page_calls)}-{i}"} for i in range(50)]
        else:
            payload = [{"id": "final"}]
        return SimpleNamespace(success=True, response_body=payload, error_message=None)

    async def fake_store(self, workspace_id, endpoint, data):
        return None

    monkeypatch.setattr("app.bootstrap.execute_api_call", fake_execute)
    monkeypatch.setattr(BootstrapService, "_store_workspace_data", fake_store)
    monkeypatch.setattr("app.bootstrap.settings.bootstrap_max_pages", 50)

    results = await service._fetch_endpoint_data("workspace-1", endpoint)

    assert len(page_calls) == 12
    assert len(results) == 551
