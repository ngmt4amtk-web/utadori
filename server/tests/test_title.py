import json
import os
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

os.environ["UTADORI_DATA"] = tempfile.mkdtemp()
sys.path.insert(0, ".")
from utadori import server

client = TestClient(server.app)


@pytest.fixture
def job():
    i = uuid.uuid4().hex[:12]
    d = server.DATA / i
    d.mkdir()
    files = {
        "meta.json": dict(id=i, title="元の題名", created=123),
        "status.json": dict(state="done", step="完了"),
        "score.json": dict(
            meter=4, tempo=120, tpb=12, grid=3,
            key=dict(tonic=0, mode="major"),
            notes=[dict(id=f"n{n}", on=n * 12, dur=12, p=p)
                   for n, p in enumerate((60, 62, 64))],
        ),
    }
    for name, data in files.items():
        (d / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return i, d


def put_title(job, title):
    return client.put(f"/api/jobs/{job[0]}/title", json={"title": title})


def musicxml(job):
    return client.get(f"/api/jobs/{job[0]}/musicxml")


def filename(response):
    return unquote(response.headers["Content-Disposition"].split("UTF-8''", 1)[1])


def test_update_title(job):
    _, d = job
    unchanged = {name: (d / name).read_bytes() for name in ("score.json", "status.json")}
    response = put_title(job, "新しい題名")
    assert response.status_code == 200
    assert response.json() == dict(ok=True, title="新しい題名")
    assert json.loads((d / "meta.json").read_text(encoding="utf-8")) == dict(
        id=job[0], title="新しい題名", created=123,
    )
    assert not (d / "meta.tmp").exists()
    for name, data in unchanged.items():
        assert (d / name).read_bytes() == data
    assert client.get(f"/api/jobs/{job[0]}").json()["title"] == "新しい題名"


def test_clean_title(job):
    response = put_title(job, "  新しい\x00\t 題名\x7f\n ")
    assert response.status_code == 200
    assert response.json()["title"] == "新しい 題名"


@pytest.mark.parametrize("title", ["", " \t\n\x00\x7f ", None, 123, [], {}])
def test_empty_or_non_string_title(job, title):
    response = put_title(job, title)
    assert response.status_code == 400
    assert response.json()["detail"] == "題名を入れてください"


def test_title_length(job):
    assert put_title(job, "あ" * 200).status_code == 200
    response = put_title(job, "あ" * 201)
    assert response.status_code == 400
    assert response.json()["detail"] == "題名は200文字までです"


def test_invalid_id():
    response = client.put("/api/jobs/not-an-id/title", json={"title": "題名"})
    assert response.status_code == 404


def test_musicxml_title_and_filename(job):
    assert put_title(job, "新しい題名").status_code == 200
    response = musicxml(job)
    assert response.status_code == 200
    assert ET.fromstring(response.content).findtext("work/work-title") == "新しい題名"
    assert filename(response) == "新しい題名.musicxml"


def test_safe_filename(job):
    assert put_title(job, "a/b:c").status_code == 200
    name = filename(musicxml(job))
    assert name == "a_b_c.musicxml"
    assert "/" not in name and ":" not in name


def test_script_title_is_xml_text(job):
    title = '<script>alert("題名")</script> & 音楽'
    assert put_title(job, title).status_code == 200
    response = musicxml(job)
    assert response.status_code == 200
    root = ET.fromstring(response.content)
    assert root.findtext("work/work-title") == title
    assert root.find(".//script") is None


def test_broken_json(job):
    response = client.put(f"/api/jobs/{job[0]}/title", content=b"{",
                          headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert response.json()["detail"] == "題名を入れてください"
