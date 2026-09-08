"""Worker wiring: enqueue path + task entrypoint, with Redis/RQ mocked out."""


def test_enqueue_pipeline_uses_queue(monkeypatch):
    from app.workers import queue as q

    captured = {}

    class FakeQueue:
        def enqueue(self, fn, *args, **kw):
            captured["fn"] = fn
            captured["args"] = args
            return type("Job", (), {"id": "rq-1"})()

    monkeypatch.setattr(q, "get_queue", lambda: FakeQueue())
    job = q.enqueue_pipeline(123)
    assert job.id == "rq-1"
    assert captured["args"] == (123,)
    assert captured["fn"].__name__ == "run_pipeline_task"


def test_run_pipeline_task_invokes_pipeline(monkeypatch):
    from app.workers import tasks

    seen = {}

    class FakeJob:
        status = type("S", (), {"value": "COMPLETED"})()
        current_stage = type("S", (), {"value": "COMPLETE"})()

    def fake_run(db, job_id):
        seen["job_id"] = job_id
        return FakeJob()

    monkeypatch.setattr(tasks, "run_pipeline", fake_run)
    out = tasks.run_pipeline_task(77)
    assert seen["job_id"] == 77
    assert out["status"] == "COMPLETED"
